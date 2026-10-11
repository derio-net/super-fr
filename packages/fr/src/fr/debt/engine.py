"""Compute a `DebtReport` (spec 2026-10-11-debt-engine §A).

Pure core: the repo is read, the forge and the clock are passed in. Nothing
here writes, and nothing here shells out except read-only `git log`.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import yaml

from fr.acceptance.model import AcceptanceError, Matrix, latest_passing_walk_at, load_matrix
from fr.archive import MergeEvidence, merge_evidence
from fr.closeout import plan_sweep
from fr.debt.model import (
    AcceptanceDebt,
    ArchivablePlan,
    DebtReport,
    DebtRow,
    ManualOpenPlan,
    OwedItem,
    PlanDebt,
    SourceStatus,
    StalePlan,
)

DEFAULT_STALE_DAYS = 14
CONFIG_REL = Path(".fr/debt.yaml")
MATRIX_REL = Path("docs/acceptance/matrix.yaml")
PLANS_REL = "docs/superpowers/plans"
RUNS_REL = Path("docs/superpowers/runs")
OWED_MARKER = re.compile(r"<!--\s*fr-owed:(\S+?)\s*-->")
_CONFIG_KEYS = frozenset({"stale_days"})


class DebtConfigError(ValueError):
    """`.fr/debt.yaml` (or `--stale-days`) could not be honoured."""


class DebtForge(Protocol):
    """What the engine asks of a forge (adapters land in a later phase)."""

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        """`{"state", "url", "mergedAt", "updatedAt"}` or None."""
        ...

    def owed_issues(self) -> list[dict[str, Any]]:
        """Open `fr:owed` / `fr:awaiting-live` issues: `ref`, `title`, `body`, `labels`."""
        ...


def load_stale_days(repo_root: Path, override: int | None) -> int:
    """`--stale-days` over `.fr/debt.yaml` over 14; an unknown key is refused."""
    if override is not None:
        if override < 1:
            raise DebtConfigError("--stale-days must be a positive number of days")
        return override
    path = repo_root / CONFIG_REL
    if not path.is_file():
        return DEFAULT_STALE_DAYS
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise DebtConfigError(f"{CONFIG_REL} is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise DebtConfigError(f"{CONFIG_REL} must be a mapping")
    unknown = sorted(set(data) - _CONFIG_KEYS)
    if unknown:
        raise DebtConfigError(
            f"{CONFIG_REL}: unknown key(s) {', '.join(unknown)} (known: stale_days)"
        )
    days = data.get("stale_days", DEFAULT_STALE_DAYS)
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise DebtConfigError(f"{CONFIG_REL}: stale_days must be a positive integer")
    return int(days)


# --- owed folding (R23) -------------------------------------------------------


@dataclass(frozen=True)
class OwedSources:
    """Owed items by source. `journal` is filled by the journal-entry source."""

    journal: Iterable[OwedItem] = field(default_factory=tuple)
    rows: Iterable[OwedItem] = field(default_factory=tuple)
    plans: Iterable[OwedItem] = field(default_factory=tuple)
    issues: Iterable[OwedItem] = field(default_factory=tuple)


OWED_PRECEDENCE: tuple[str, ...] = ("journal", "rows", "plans", "issues")
"""Which source wins a shared key, first first (spec §A: the journal entry or
the row). A new source is one field on `OwedSources` and one name here."""


def fold_owed(sources: OwedSources) -> tuple[OwedItem, ...]:
    """One item per key, the highest-precedence source's, sorted by key."""
    seen: dict[str, OwedItem] = {}
    for name in OWED_PRECEDENCE:
        for item in getattr(sources, name):
            seen.setdefault(item.key, item)
    return tuple(seen[k] for k in sorted(seen))


def _row_owed(matrix: Matrix | None) -> list[OwedItem]:
    if matrix is None:
        return []
    return [
        OwedItem(
            key=f"row:{r.id}",
            source="row",
            title=r.acceptance,
            how=f"walk row {r.id} (fr verification walk), then fr acceptance set-status",
        )
        for r in matrix.rows
        if r.status == "walk-owed"
    ]


def _plan_owed(manual_open: Iterable[ManualOpenPlan]) -> list[OwedItem]:
    return [
        OwedItem(
            key=f"plan:{m.name}#p{n}",
            source="plan",
            title=f"{m.name}: manual phase {n} is not ticked",
            how=f"do phase {n}, tick it, then fr archive {PLANS_REL}/{m.name}",
        )
        for m in manual_open
        for n in m.phases
    ]


def _issue_owed(issues: Iterable[dict[str, Any]]) -> list[OwedItem]:
    out = []
    for i in issues:
        ref = str(i.get("ref", ""))
        m = OWED_MARKER.search(str(i.get("body") or ""))
        out.append(
            OwedItem(
                key=m.group(1) if m else f"issue:{ref}",
                source="issue",
                title=str(i.get("title", "")),
                how=f"complete it, then close {ref}",
                ref=ref,
            )
        )
    return out


# --- git ----------------------------------------------------------------------


def _last_commit(
    repo_root: Path, ref: str, rel: str | None, *, exclude: str | None = None
) -> datetime | None:
    """Committer time of the newest commit on *ref* touching *rel* (any path
    when None), leaving out what *exclude* already holds; None when there is none."""
    argv = ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", ref]
    if exclude:
        argv.append(f"^{exclude}")
    if rel:
        argv += ["--", rel]
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return _parse(done.stdout.strip()) if done.returncode == 0 else None


def _parse(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _run_branches(repo_root: Path) -> dict[str, str]:
    """plan name -> run branch, from every run cursor that emitted the plan."""
    out: dict[str, str] = {}
    runs = repo_root / RUNS_REL
    for path in sorted(runs.glob("*.yaml")) if runs.is_dir() else []:
        try:
            data = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("branch"), str):
            continue
        for step in (data.get("steps") or {}).values():
            emitted = step.get("emitted") if isinstance(step, dict) else None
            plan = emitted.get("plan") if isinstance(emitted, dict) else None
            if isinstance(plan, str):
                out[Path(plan).name] = data["branch"]
    return out


# --- sections -----------------------------------------------------------------


def acceptance_from_matrix(matrix: Matrix) -> AcceptanceDebt:
    """The Acceptance section of a matrix already in hand (the digest's seam)."""
    by_status: dict[str, int] = {}
    for r in matrix.rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    rows = tuple(
        DebtRow(
            id=r.id,
            status=r.status,
            acceptance=r.acceptance,
            notes=r.notes,
            walked_at=latest_passing_walk_at(r) if r.status == "walked" else None,
        )
        for r in matrix.rows
        if r.status in {"not-implemented", "unwired", "walk-owed", "failing", "walked", "manual"}
    )
    return AcceptanceDebt(by_status=by_status, rows=rows, available=True)


def acceptance_debt(repo_root: Path) -> tuple[AcceptanceDebt, Matrix | None, SourceStatus]:
    """The Acceptance section; an unreadable matrix is unavailable, never zero."""
    path = repo_root / MATRIX_REL
    try:
        matrix = load_matrix(path)
    except (AcceptanceError, OSError) as e:
        why = " ".join(str(e).split())
        return AcceptanceDebt(available=False), None, SourceStatus(state="unavailable", why=why)
    return acceptance_from_matrix(matrix), matrix, SourceStatus(state="read")


def compute(
    repo_root: Path,
    *,
    forge: DebtForge | None,
    now: datetime,
    stale_days: int | None = None,
    evidence: MergeEvidence | None = None,
    fetch: bool = False,
) -> DebtReport:
    """The repo's debt as one report. *forge* None means offline (R4)."""
    days = load_stale_days(repo_root, stale_days)
    ev = evidence if evidence is not None else merge_evidence(repo_root, fetch=fetch)
    sources: dict[str, SourceStatus] = {}

    acc, matrix, sources["matrix"] = acceptance_debt(repo_root)

    sweep = plan_sweep(repo_root, ev)
    if ev.ref is None:
        sources["git"] = SourceStatus(
            state="unavailable", why=ev.ref_error or "default branch unknown"
        )
    else:
        sources["git"] = SourceStatus(state="read")
    ref = ev.ref.ref if ev.ref else None

    archivable = []
    for name in sweep.archivable:
        merged = _last_commit(repo_root, ref, f"{PLANS_REL}/{name}") if ref else None
        archivable.append(
            ArchivablePlan(
                name=name,
                command=f"fr archive {PLANS_REL}/{name}",
                merged_at=merged.isoformat() if merged else None,
                age_days=(now - merged).days if merged else None,
            )
        )

    forge_ok = forge is not None
    forge_why = "offline: staleness comes from git alone" if forge is None else ""
    branches = _run_branches(repo_root)
    stale = []
    for name in [*sweep.in_progress, *sweep.complete_unmerged]:
        rel = f"{PLANS_REL}/{name}"
        times: list[datetime | None] = []
        if ref:
            times.append(_last_commit(repo_root, ref, rel))
        branch = branches.get(name)
        if branch:
            for b in (f"origin/{branch}", branch):
                times.append(_last_commit(repo_root, b, rel))
                times.append(_last_commit(repo_root, b, None, exclude=ref))
        basis = "git"
        if forge is not None and forge_ok and branch:
            try:
                pr = forge.pr_for_branch(branch)
            except Exception as e:  # a forge failure degrades the report, never fails it
                forge_ok, forge_why = False, f"{type(e).__name__}: {e}"
                pr = None
            basis = "git+forge"
            if pr:
                times.append(_parse(pr.get("updatedAt")))
        elif forge is not None:
            basis = "git+forge"
        seen = [t for t in times if t is not None]
        if not seen:
            continue
        last = max(seen)
        if now - last > timedelta(days=days):
            stale.append(
                StalePlan(
                    name=name,
                    last_activity=last.isoformat(),
                    idle_days=(now - last).days,
                    basis=basis,
                )
            )

    manual_open = tuple(
        ManualOpenPlan(name=n, phases=tuple(ph)) for n, ph in sweep.merged_manual_open
    )

    issues: list[dict[str, Any]] = []
    if forge is not None and forge_ok:
        try:
            issues = forge.owed_issues()
        except Exception as e:
            forge_ok, forge_why = False, f"{type(e).__name__}: {e}"
    sources["forge"] = (
        SourceStatus(state="read")
        if forge_ok and forge is not None
        else SourceStatus(state="unavailable", why=forge_why)
    )

    owed = fold_owed(
        OwedSources(
            rows=_row_owed(matrix),
            plans=_plan_owed(manual_open),
            issues=_issue_owed(issues),
        )
    )
    return DebtReport(
        acceptance=acc,
        plans=PlanDebt(archivable=tuple(archivable), stale=tuple(stale), manual_open=manual_open),
        owed=owed,
        stale_days=days,
        sources=sources,
        generated_at=now.isoformat(),
    )
