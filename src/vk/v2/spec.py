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
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vk.v2.parser import PlanSchemaError, parse

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
    state: Literal["Not Started", "In Progress", "Complete", "Missing", "Unreachable"]
    phases_complete: int
    phases_total: int
    steps_ticked: int
    steps_total: int


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

    Cross-repo / manual-action rows return None — those need cross-repo
    gh-API resolution which is out of scope for Phase 3.
    """
    if not plan_ref.file or plan_ref.file in ("—", "-"):
        return None
    candidate = repo_root / plan_ref.file
    if candidate.is_dir():
        return candidate
    # Trailing slash variant
    if str(candidate).endswith("/"):
        return None
    return candidate if candidate.exists() else None


def compute_status(spec: SpecMeta, repo_root: Path) -> SpecStatus:
    """Aggregate plan statuses for the spec. Local-fs only at this layer.

    Cross-repo plans (where `repo` != current repo's owner/repo or the
    file path doesn't resolve locally) are reported as `Unreachable`.
    The GHA / future cross-repo wiring will reach into them via the
    gh contents API.
    """
    plan_statuses: list[PlanStatus] = []
    warnings: list[str] = []
    plans_complete = 0
    total_steps_ticked = 0
    total_steps_total = 0

    for ref in spec.plans:
        local = _resolve_local_plan_dir(ref, repo_root)
        if local is None:
            # Either manual-action row (file == "—") or cross-repo
            if ref.file in ("—", "-", ""):
                state: Literal[
                    "Not Started", "In Progress", "Complete", "Missing", "Unreachable"
                ] = "Not Started"  # placeholder for manual rows
                plan_statuses.append(
                    PlanStatus(
                        plan_ref=ref,
                        state=state,
                        phases_complete=0,
                        phases_total=0,
                        steps_ticked=0,
                        steps_total=0,
                    )
                )
                continue
            warnings.append(
                f"plan {ref.name!r}: file {ref.file!r} not resolvable locally "
                f"(cross-repo lookup not implemented in Phase 3)."
            )
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Unreachable",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                )
            )
            continue

        if not local.is_dir():
            warnings.append(f"plan {ref.name!r}: file {ref.file!r} does not exist as a folder.")
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Missing",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                )
            )
            continue

        try:
            plan = parse(local)
        except PlanSchemaError as e:
            warnings.append(f"plan {ref.name!r}: parse error: {e}")
            plan_statuses.append(
                PlanStatus(
                    plan_ref=ref,
                    state="Missing",
                    phases_complete=0,
                    phases_total=0,
                    steps_ticked=0,
                    steps_total=0,
                )
            )
            continue

        steps_total = sum(len(t.steps) for p in plan.phases for t in p.tasks)
        steps_ticked = sum(
            1 for p in plan.phases for ss in p.state.steps.values() if ss.state in ("x", "-")
        )
        # Phase-level: complete iff completion.at set, OR all steps ticked
        # (mirror render's _phase_complete WITHOUT the merged-PR requirement
        # since spec status doesn't observe gh — it's a local roll-up only)
        phases_complete = 0
        for p in plan.phases:
            if p.state.completion.at is not None:
                phases_complete += 1
                continue
            steps = p.state.steps
            if steps and all(s.state in ("x", "-") for s in steps.values()):
                phases_complete += 1
        phases_total = len(plan.phases)

        if steps_total == 0:
            state = "Not Started"
        elif phases_complete == phases_total:
            state = "Complete"
            plans_complete += 1
        elif steps_ticked > 0 or phases_complete > 0:
            state = "In Progress"
        else:
            state = "Not Started"

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
