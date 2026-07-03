"""Spec parsing + status aggregation.

Parses the `## Implementation Plans` table out of a spec markdown file
(now 4 columns: Plan | Repo | File | Depends on; no Status column),
walks each referenced plan folder, and aggregates step/phase
completion across them.

Status is computed on demand — the spec file itself never carries
state. This is the v2 design rule: "if it can be derived, don't
store it."
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml

from fr import refs
from fr.parser import _PHASE_FILE_RE, PlanSchemaError, parse
from fr.render import plan_locally_complete
from fr.types import PhaseDoc

if TYPE_CHECKING:
    from fr.ghclient import GhClient

# Reused by PlanStatus.state and the shared `_status_counts` helper.
PlanState = Literal["Not Started", "In Progress", "Complete", "Missing", "Unreachable"]

_TABLE_HEADER_RE = re.compile(r"^## Implementation Plans\s*$", re.MULTILINE)
# A row is `| col1 | col2 | col3 | col4 |`. We strip backticks for path matching.
_ROW_RE = re.compile(r"^\|(.+)\|\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PlanRef:
    name: str
    repo: str  # may be "—" or "(operator action across ...)" for manual rows
    file: str  # may be "—" for manual rows
    depends_on: str  # free-form text from the table cell


@dataclass(frozen=True)
class SpecMeta:
    path: Path
    title: str
    plans: tuple[PlanRef, ...]


@dataclass(frozen=True)
class PlanStatus:
    plan_ref: PlanRef
    state: PlanState
    phases_complete: int
    phases_total: int
    steps_ticked: int
    steps_total: int
    # Per-plan diagnostic — populated for non-OK states (Missing,
    # Unreachable, parse failures). `None` for healthy plans. Lets
    # consumers display the reason inline instead of cross-referencing
    # the top-level `warnings` list.
    note: str | None = None


@dataclass(frozen=True)
class SpecAggregate:
    plans_complete: int
    plans_total: int
    steps_ticked: int
    steps_total: int
    percent_complete: float


@dataclass(frozen=True)
class SpecStatus:
    spec: SpecMeta
    plans: tuple[PlanStatus, ...]
    aggregate: SpecAggregate
    warnings: tuple[str, ...]


def _strip_cell(cell: str) -> str:
    """Strip whitespace + outer backticks from a markdown table cell."""
    s = cell.strip()
    if len(s) >= 2 and s.startswith("`") and s.endswith("`"):
        return s[1:-1]
    return s


def parse_spec(spec_path: Path) -> SpecMeta:
    """Parse a spec file's `## Implementation Plans` table into PlanRefs."""
    text = spec_path.read_text()
    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else spec_path.stem

    section_m = _TABLE_HEADER_RE.search(text)
    if not section_m:
        return SpecMeta(path=spec_path, title=title, plans=())

    after = text[section_m.end() :]
    rows: list[PlanRef] = []
    saw_pipe = False
    for line in after.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            saw_pipe = True
            cells = [_strip_cell(c) for c in stripped.strip("|").split("|")]
            if len(cells) != 4:
                continue
            # Skip header row + separator row
            if cells[0].lower() == "plan" or set(cells[0]) <= {"-", " "}:
                continue
            rows.append(
                PlanRef(
                    name=cells[0],
                    repo=cells[1],
                    file=cells[2],
                    depends_on=cells[3],
                )
            )
        elif saw_pipe and stripped == "":
            break
    return SpecMeta(path=spec_path, title=title, plans=tuple(rows))


def _resolve_local_plan_dir(plan_ref: PlanRef, repo_root: Path) -> Path | None:
    """Resolve the plan's File cell to a local directory, if same-repo.

    Delegates to `vk.refs.resolve_plan_ref` (2026-06-06 spec-path-repair
    design): the cell may be a bare slug (canonical), an active /
    `implemented/` / legacy `archived-plans/` path, or a backticked
    annotated cell — every form resolves against every lifecycle root,
    active first. An exact on-disk path wins before normalization.

    Cross-repo / manual-action rows return None here — a cross-repo plan is
    resolved remotely by `compute_status` via the gh contents API (when a
    GhClient is supplied); a manual row has no plan file to resolve.
    """
    if not plan_ref.file or plan_ref.file in ("—", "-"):
        return None
    candidate = repo_root / plan_ref.file
    if candidate.is_dir():
        return candidate
    res = refs.resolve_plan_ref(plan_ref.file, repo_root)
    if res.path is not None:
        return res.path
    # v1 flat-plan refs (.md files) and other exact file refs still resolve.
    if str(candidate).endswith("/"):
        return None
    return candidate if candidate.exists() else None


def _status_counts(phases: Sequence[PhaseDoc]) -> tuple[PlanState, int, int, int, int]:
    """(state, phases_complete, phases_total, steps_ticked, steps_total).

    The per-plan status arithmetic shared by compute_status's local and
    cross-repo branches, so the two can't diverge. `plan_locally_complete`
    is the same phase-completion predicate the dispatch guard and the
    archive gate use.
    """
    steps_total = sum(len(t.steps) for p in phases for t in p.tasks)
    steps_ticked = sum(1 for p in phases for ss in p.state.steps.values() if ss.state in ("x", "-"))
    phases_complete = sum(1 for p in phases if plan_locally_complete(p))
    phases_total = len(phases)
    state: PlanState
    if steps_total == 0:
        state = "Not Started"
    elif phases_complete == phases_total:
        state = "Complete"
    elif steps_ticked > 0 or phases_complete > 0:
        state = "In Progress"
    else:
        state = "Not Started"
    return state, phases_complete, phases_total, steps_ticked, steps_total


def _resolve_remote_plan_phases(
    gh: GhClient,
    repo: str,
    file_cell: str,
    cache: dict[tuple[str, str], list[PhaseDoc] | None],
) -> list[PhaseDoc] | None:
    """Resolve a cross-repo plan's phases via the gh contents API, or None.

    Probes the active / implemented / legacy path variants (active first, per
    `refs.PLAN_ROOTS`) and returns the parsed phases of the first folder that
    looks like a v2 plan (contains `_meta.yaml`). A merged-but-not-yet-archived
    plan is read from `plans/` (current progress); an archived one from
    `implemented/plans/` (its final, complete state).

    `_meta.yaml` itself is never fetched — status needs only the phase docs,
    and skipping it avoids coupling remote resolution to the parser's
    `fr_version` gate. Memoized per run on `(repo, slug)`, negatives included.
    Returns None for a non-`owner/repo` cell or when no variant resolves;
    gh/parse errors propagate to the caller, which degrades the row.
    """
    from fr.migrate import _archive_path_variants

    if "/" not in repo:
        return None
    slug = refs.plan_slug(file_cell)
    if not slug:
        return None
    key = (repo, slug)
    if key in cache:
        return cache[key]

    result: list[PhaseDoc] | None = None
    for path in _archive_path_variants(file_cell):
        if path is None:
            continue
        names = gh.list_dir(repo, path)
        if "_meta.yaml" not in names:
            continue
        phases: list[PhaseDoc] = []
        for name in sorted(n for n in names if _PHASE_FILE_RE.match(n)):
            raw = gh.read_file(repo, f"{path}/{name}")
            phases.append(PhaseDoc.model_validate(yaml.safe_load(raw)))
        result = phases
        break

    cache[key] = result
    return result


def compute_status(spec: SpecMeta, repo_root: Path, gh: GhClient | None = None) -> SpecStatus:
    """Aggregate plan statuses for the spec.

    Same-repo plans resolve on the local filesystem. A plan whose folder
    doesn't resolve locally (the normal multi-repo shape) is resolved via the
    gh contents API when `gh` is supplied — its remote `NN.yaml` files are read
    and given the exact same phase/step arithmetic as a local plan, so it
    counts toward `plans_complete` and the aggregate. When `gh` is absent
    (`--no-gh` / offline) or the remote read fails, the row degrades to
    `Unreachable` — never a silent pass. Contents-API results are memoized per
    call, keyed on `(repo, slug)`.
    """
    plan_statuses: list[PlanStatus] = []
    warnings: list[str] = []
    plans_complete = 0
    total_steps_ticked = 0
    total_steps_total = 0
    remote_cache: dict[tuple[str, str], list[PhaseDoc] | None] = {}

    for ref in spec.plans:
        local = _resolve_local_plan_dir(ref, repo_root)
        if local is None:
            # Either manual-action row (file == "—") or cross-repo
            if ref.file in ("—", "-", ""):
                plan_statuses.append(
                    PlanStatus(
                        plan_ref=ref,
                        state="Not Started",  # placeholder for manual rows
                        phases_complete=0,
                        phases_total=0,
                        steps_ticked=0,
                        steps_total=0,
                        note="manual / informational row (no plan file)",
                    )
                )
                continue

            # Cross-repo: resolve via the gh contents API when a client is
            # given (same capability `fr archive` uses); degrade to Unreachable
            # when absent / offline / not found / read failure.
            remote_phases: list[PhaseDoc] | None = None
            fail_note: str | None = None
            if gh is not None:
                try:
                    remote_phases = _resolve_remote_plan_phases(
                        gh, ref.repo, ref.file, remote_cache
                    )
                except Exception as e:  # noqa: BLE001 — any gh/parse failure degrades the row
                    fail_note = f"cross-repo read of {ref.repo} failed: {e}"

            if remote_phases is not None:
                state, phases_complete, phases_total, steps_ticked, steps_total = _status_counts(
                    remote_phases
                )
                if state == "Complete":
                    plans_complete += 1
                total_steps_ticked += steps_ticked
                total_steps_total += steps_total
                plan_statuses.append(
                    PlanStatus(
                        plan_ref=ref,
                        state=state,
                        phases_complete=phases_complete,
                        phases_total=phases_total,
                        steps_ticked=steps_ticked,
                        steps_total=steps_total,
                        note=f"resolved via gh contents API ({ref.repo})",
                    )
                )
                continue

            if gh is None:
                note = (
                    f"file {ref.file!r} is cross-repo ({ref.repo}); "
                    f"run without --no-gh to resolve it via the gh contents API"
                )
            elif fail_note is not None:
                note = fail_note
            else:
                note = f"plan {ref.file!r} not found in {ref.repo} via the gh contents API"
            warnings.append(f"plan {ref.name!r}: {note}.")
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Unreachable",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                    note=note,
                )
            )
            continue

        if not local.is_dir():
            note = f"file {ref.file!r} does not exist as a folder (resolved to {local})"
            warnings.append(f"plan {ref.name!r}: {note}.")
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Missing",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                    note=note,
                )
            )
            continue

        try:
            plan = parse(local)
        except PlanSchemaError as e:
            note = f"parse error: {e}"
            warnings.append(f"plan {ref.name!r}: {note}")
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Missing",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                    note=note,
                )
            )
            continue

        state, phases_complete, phases_total, steps_ticked, steps_total = _status_counts(
            plan.phases
        )
        if state == "Complete":
            plans_complete += 1
        total_steps_ticked += steps_ticked
        total_steps_total += steps_total

        plan_statuses.append(
            PlanStatus(
                plan_ref=ref,
                state=state,
                phases_complete=phases_complete,
                phases_total=phases_total,
                steps_ticked=steps_ticked,
                steps_total=steps_total,
            )
        )

    pct = (total_steps_ticked / total_steps_total * 100.0) if total_steps_total else 0.0
    aggregate = SpecAggregate(
        plans_complete=plans_complete,
        plans_total=len(spec.plans),
        steps_ticked=total_steps_ticked,
        steps_total=total_steps_total,
        percent_complete=round(pct, 1),
    )
    return SpecStatus(
        spec=spec,
        plans=tuple(plan_statuses),
        aggregate=aggregate,
        warnings=tuple(warnings),
    )


_STATE_ICON = {
    "Not Started": "⚪",
    "In Progress": "🟡",
    "Complete": "✅",
    "Missing": "❌",
    "Unreachable": "🔒",
}


def render_status_md(status: SpecStatus) -> str:
    """Format SpecStatus as the markdown body for the GHA comment."""
    spec_rel = status.spec.path
    lines: list[str] = []
    lines.append(f"**Spec progress** — `{spec_rel}`")
    lines.append("")
    lines.append("| Plan | Repo | Status |")
    lines.append("|---|---|---|")
    for ps in status.plans:
        icon = _STATE_ICON.get(ps.state, "?")
        if ps.state == "In Progress":
            stat = (
                f"{icon} {ps.state} ({ps.phases_complete}/{ps.phases_total} phases, "
                f"{ps.steps_ticked}/{ps.steps_total} steps)"
            )
        elif ps.state == "Complete":
            stat = f"{icon} {ps.state} ({ps.phases_total}/{ps.phases_total} phases)"
        else:
            stat = f"{icon} {ps.state}"
        lines.append(f"| {ps.plan_ref.name} | {ps.plan_ref.repo} | {stat} |")
    lines.append("")
    agg = status.aggregate
    lines.append(
        f"**Spec aggregate:** {agg.plans_complete}/{agg.plans_total} plans complete "
        f"({agg.percent_complete}% of total steps)."
    )
    if status.warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for w in status.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)
