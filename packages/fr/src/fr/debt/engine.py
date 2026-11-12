"""Compute a `DebtReport` (spec 2026-10-11-debt-engine §A).

Pure core: the repo is read, the forge and the clock are passed in. Nothing
here writes, and nothing here shells out except read-only `git log`.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import yaml

from fr.acceptance.check import _age_key
from fr.acceptance.model import (
    DEBT_STATUSES,
    LISTED_STATUSES,
    AcceptanceError,
    Matrix,
    Row,
    is_debt,
    latest_passing_walk_at,
)
from fr.archive import MergeEvidence, merge_evidence
from fr.artifacts.paths import KIND_DIRS, artifact_root
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
PLANS_REL = KIND_DIRS["plan"]
SPECS_REL = KIND_DIRS["spec"]
RUNS_REL = Path(KIND_DIRS["run"])
OWED_MARKER = re.compile(r"<!--\s*fr-owed:(\S+?)\s*-->")
_CONFIG_KEYS = frozenset({"stale_days"})


class DebtConfigError(ValueError):
    """`.fr/debt.yaml` (or `--stale-days`) could not be honoured."""


class PartialIssuesError(Exception):
    """`owed_issues` raises this when its list may be incomplete (a cap was hit);
    `items` is what it did read, and the report says the source is partial."""

    def __init__(self, items: list[dict[str, Any]], why: str) -> None:
        super().__init__(why)
        self.items = items


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


def spec_heading_problems(repo_root: Path) -> list[str]:
    """One line per live spec whose Test Plan heading is a near-miss of `## Test Plan`
    (super-fr#1315): its steps cannot be read, so what they owe is unknown — never
    zero. Archived specs are frozen and not read."""
    from fr.spec import find_test_plan_heading, near_miss_message

    specs = artifact_root(repo_root) / SPECS_REL
    out: list[str] = []
    for spec in sorted(specs.glob("*.md")) if specs.is_dir() else []:
        try:
            heading = find_test_plan_heading(spec.read_text())
        except (OSError, ValueError):
            continue
        if heading is not None and not heading.exact:
            out.append(near_miss_message(heading, f"{SPECS_REL}/{spec.name}"))
    return out


if TYPE_CHECKING:
    from fr.journal.model import JournalEntry


@dataclass(frozen=True)
class JournalsRead:
    """Every journal of a checkout, parsed once: what a caller reading several things from them
    hands on, so no file is parsed twice in one run."""

    entries: dict[Path, list[JournalEntry]]
    unreadable: tuple[str, ...]


def read_journals(repo_root: Path) -> JournalsRead:
    """Every journal, live and archived (`implemented/`); one that cannot be parsed is named."""
    from fr.journal.model import (
        IMPLEMENTED_JOURNALS_REL,
        JOURNALS_REL,
        JournalParseError,
        parse_journal,
    )

    entries: dict[Path, list[JournalEntry]] = {}
    unreadable: list[str] = []
    for base in (JOURNALS_REL, IMPLEMENTED_JOURNALS_REL):
        root = repo_root / base
        if not root.is_dir():
            continue
        for path in sorted(root.glob("**/*.md")):
            try:
                entries[path] = parse_journal(path.read_text())
            except (JournalParseError, OSError, UnicodeDecodeError):
                unreadable.append(path.relative_to(repo_root).as_posix())
    return JournalsRead(entries, tuple(unreadable))


def journal_owed(
    repo_root: Path, *, journals: JournalsRead | None = None
) -> tuple[list[OwedItem], set[str], list[str]]:
    """The journal-entry owed source (R23): every unresolved `owed` entry of
    every journal, live and archived (`implemented/`), one item per key.

    Returns `(items, discharged keys, unreadable journals)`. A discharged key
    is one whose entry was resolved `fixed` and that no journal still owes —
    the fold drops a still-open issue carrying it, so a discharge whose issue
    could not be closed does not linger as debt.
    """
    from fr.journal.model import open_owed_ids, owed_fields, owed_filed_as, owed_key

    read = journals if journals is not None else read_journals(repo_root)
    items: dict[str, OwedItem] = {}
    discharged: set[str] = set()
    for entries in read.entries.values():
        still = set(open_owed_ids(entries))
        filed = owed_filed_as(entries)
        for e in entries:
            key = owed_key(e) if e.kind == "owed" else None
            if key is None:
                continue
            if e.id not in still:
                discharged.add(key)
                continue
            items.setdefault(
                key,
                OwedItem(
                    key=key,
                    source="journal",
                    title=e.title,
                    how=owed_fields(e).get("how", ""),
                    ref=filed.get(e.id, ""),
                ),
            )
    return list(items.values()), discharged - set(items), list(read.unreadable)


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
    argv = ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", "--end-of-options", ref]
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


def _safe_branch(repo_root: Path, branch: str) -> bool:
    """A branch name from a run cursor is untrusted input: it reaches `git log`
    and the forge CLI, so one that is an option or not a valid ref name is dropped."""
    if not branch or branch.startswith("-"):
        return False
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "check-ref-format", "--branch", branch],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def _run_branches(repo_root: Path) -> dict[str, str]:
    """plan name -> run branch, from every run cursor that emitted the plan."""
    out: dict[str, str] = {}
    runs = artifact_root(repo_root) / RUNS_REL
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
            if isinstance(plan, str) and _safe_branch(repo_root, data["branch"]):
                out[Path(plan).name] = data["branch"]
    return out


# --- sections -----------------------------------------------------------------


def acceptance_from_matrix(
    matrix: Matrix,
    contested: frozenset[str] = frozenset(),
    retired: Sequence[Row] = (),
) -> AcceptanceDebt:
    """The Acceptance section of a matrix already in hand (the digest's seam);
    *contested* is the fold's contested rows (spec 2026-11-04 R17), debt whatever
    their status, and a *retired* row among them is debt too, listed as retired
    (`open_rows` is the same definition)."""
    by_status: dict[str, int] = {}
    for r in matrix.rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    def debt(r: Row) -> bool:
        return is_debt(r.status, contested=r.id in contested)

    gone = [r for r in retired if r.id in contested]
    gone_ids = {r.id for r in gone}
    listed = [r for r in matrix.rows if r.status in LISTED_STATUSES or r.id in contested]
    listed += gone
    # Debt rows oldest origin first, as `open_rows` orders the nag; the rest keep matrix order.
    ordered = sorted((r for r in listed if debt(r)), key=_age_key) + [
        r for r in listed if not debt(r)
    ]
    rows = tuple(
        DebtRow(
            id=r.id,
            status=r.status,
            acceptance=r.acceptance,
            notes=r.notes,
            walked_at=latest_passing_walk_at(r) if r.status == "walked" else None,
            contested=r.id in contested,
            retired=r.id in gone_ids,
        )
        for r in ordered
    )
    extra = len(gone)
    extra += sum(1 for r in matrix.rows if r.id in contested and r.status not in DEBT_STATUSES)
    return AcceptanceDebt(by_status=by_status, rows=rows, available=True, contested=extra)


def acceptance_debt(repo_root: Path) -> tuple[AcceptanceDebt, Matrix | None, SourceStatus]:
    """The Acceptance section; an unreadable matrix is unavailable, never zero."""
    from fr.settings import DISABLED, disabled

    if disabled(repo_root, "acceptance"):
        return AcceptanceDebt(available=False), None, SourceStatus(state="read", why=DISABLED)
    from fr.acceptance.fold import effective, has_fragments
    from fr.acceptance.fragment import FRAGMENTS_DIR

    try:
        if not has_fragments(repo_root) and not (artifact_root(repo_root) / FRAGMENTS_DIR).is_dir():
            raise AcceptanceError(f"no acceptance fragments under {FRAGMENTS_DIR}/")
        folded = effective(repo_root)
    except (AcceptanceError, OSError) as e:
        why = " ".join(str(e).split())
        return AcceptanceDebt(available=False), None, SourceStatus(state="unavailable", why=why)
    matrix = folded.matrix
    debt = acceptance_from_matrix(matrix, folded.contested, folded.retired)
    return debt, matrix, SourceStatus(state="read")


def compute(
    repo_root: Path,
    *,
    forge: DebtForge | None,
    now: datetime,
    stale_days: int | None = None,
    evidence: MergeEvidence | None = None,
    fetch: bool = False,
    forge_why: str = "",
    journals: JournalsRead | None = None,
) -> DebtReport:
    """The repo's debt as one report. *forge* None means no forge was used (R4);
    *forge_why* says why (offline, tracking none, no remote), else "offline".
    *journals*: already read, so a caller reading them too parses each once."""
    days = load_stale_days(repo_root, stale_days)
    ev = evidence if evidence is not None else merge_evidence(repo_root, fetch=fetch)
    sources: dict[str, SourceStatus] = {}

    acc, matrix, sources["matrix"] = acceptance_debt(repo_root)

    sweep = plan_sweep(repo_root, ev)
    if ev.ref is None:
        sources["git"] = SourceStatus(
            state="unavailable", why=ev.ref_error or "default branch unknown"
        )
    elif ev.fetch_error:
        sources["git"] = SourceStatus(
            state="read", why=f"local ref; fetch failed: {ev.fetch_error}"
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
    forge_why = f"{forge_why or 'offline'}: staleness comes from git alone" if forge is None else ""
    forge_note = ""
    branches = _run_branches(repo_root)
    stale = []
    for name in [*sweep.in_progress, *sweep.complete_unmerged]:
        rel = f"{PLANS_REL}/{name}"
        times: list[datetime | None] = []
        if ref:
            times.append(_last_commit(repo_root, ref, rel))
        else:
            times.append(_last_commit(repo_root, "HEAD", rel))
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
            else:
                basis = "git+forge"
                if pr:
                    times.append(_parse(pr.get("updatedAt")))
        seen = [t for t in times if t is not None]
        if not seen:
            # No readable activity is not "active": list it, with the age unknown.
            stale.append(StalePlan(name=name, last_activity=None, idle_days=None, basis=basis))
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
        except PartialIssuesError as e:
            issues, forge_note = e.items, str(e)
        except Exception as e:
            forge_ok, forge_why = False, f"{type(e).__name__}: {e}"
    sources["forge"] = (
        SourceStatus(state="read", why=forge_note)
        if forge_ok and forge is not None
        else SourceStatus(state="unavailable", why=forge_why)
    )

    near_misses = spec_heading_problems(repo_root)
    sources["specs"] = (
        SourceStatus(
            state="unavailable",
            why="Test Plan steps unreadable, what they owe is unknown: " + "; ".join(near_misses),
        )
        if near_misses
        else SourceStatus(state="read")
    )

    journal_items, discharged, unreadable = journal_owed(repo_root, journals=journals)
    sources["journals"] = SourceStatus(
        state="read",
        why=f"unreadable, skipped: {', '.join(unreadable)}" if unreadable else "",
    )
    owed = fold_owed(
        OwedSources(
            journal=journal_items,
            rows=_row_owed(matrix),
            plans=_plan_owed(manual_open),
            issues=[i for i in _issue_owed(issues) if i.key not in discharged],
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
