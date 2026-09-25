"""The pre-filled record a step is handed (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.C.3): the template IS the
interface, so no agent needs `--help` mid-run.

`fr pickup` and `fr run advance`'s dispatch brief both carry one — run, step
and item set, only the sections the step's `emits:` allows, and the plan's
step ids listed where ticks are allowed. When a record for the unit already
exists (a session died mid-step), both show it as in progress instead, so a
fresh session continues it rather than starting over.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fr.record.model import (
    RecordError,
    StepRecord,
    allowed_sections,
    load_record,
    record_path,
)

if TYPE_CHECKING:
    from fr.run.model import RunState
    from fr.workflow.model import Step

__all__ = ["RecordBrief", "in_progress_summary", "record_brief", "render_template"]

_DERIVED = frozenset({"findings", "proportionality"})
_EMITTED_NAMES = ("spec", "plan", "pr")


def render_template(
    *,
    run: str,
    step: str,
    item: str | None,
    allowed: frozenset[str],
    tick_ids: list[str],
    refactor_tasks: list[str],
    evidence: list[str],
    emitted: list[str],
    resolve: str,
) -> str:
    """The YAML text of an empty record for one unit — valid as it stands."""
    lines = [
        "# Step record. Fill it as you work and commit it with your work; then",
        f"#   {resolve}",
        "# applies all of it in one commit (spec 2026-09-25 §5.C).",
        "schema_version: 1",
        f"run: {run}",
        f"step: {step}",
    ]
    if item is not None:
        lines.append(f"item: {item}")
    lines.append("outcome: done            # done | failed | blocked")
    if "ticks" in allowed:
        lines.append("ticks: []                # step ids you completed, e.g. [P1.T1.S1]")
        if tick_ids:
            lines.append(f"#   this phase: {', '.join(tick_ids)}")
    if "refactor" in allowed:
        lines.append('refactor: {}             # P<n>.T<m>: "why there was nothing to clean"')
        if refactor_tasks:
            lines.append(f"#   owed by tasks with no refactor step: {', '.join(refactor_tasks)}")
    if "journal" in allowed:
        lines.append("journal: []")
        lines.append(
            "#   - {kind: decision|discovery|finding, id: <id>, title: <line>, body: <md>}"
        )
        lines.append("#     a finding also takes review_scope: in|out (state defaults to open)")
    if "resolves" in allowed:
        lines.append("resolves: []")
        lines.append(
            "#   - {id: <finding>, state: fixed|refuted|deferred|out-of-scope, body: <why>}"
        )
    if "acceptance" in allowed:
        lines.append("acceptance: []")
        lines.append(
            "#   - {id: <row>, capability: <c>, acceptance: <statement>, "
            "origin: [<repo>:<path>], status: not-implemented}"
        )
    if emitted:
        lines.append("emitted: {}")
        lines.append(f"#   {', '.join(f'{n}: <path or url>' for n in emitted)}")
    owed = [n for n in evidence if n not in _DERIVED]
    lines.append("evidence: {}")
    if owed:
        lines.append(f"#   owed: {', '.join(f'{n}: <id>' for n in owed)}")
    return "\n".join(lines) + "\n"


def in_progress_summary(record: StepRecord) -> str:
    """`N ticks, M decisions, …` — what a resumed session is told it has."""
    parts = [f"{len(record.ticks)} ticks"]
    kinds = Counter(e.kind for e in record.journal)
    parts += [f"{n} {kind}s" for kind, n in sorted(kinds.items())]
    if not kinds:
        parts.append("0 decisions")
    if record.resolves:
        parts.append(f"{len(record.resolves)} resolutions")
    if record.acceptance:
        parts.append(f"{len(record.acceptance)} rows")
    return ", ".join(parts)


@dataclass(frozen=True)
class RecordBrief:
    path: str
    """Repo-relative path the record lives at."""
    template: str
    in_progress: str | None
    """`record in progress: …` when the file already exists, else None."""

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "template": self.template, "in_progress": self.in_progress}


def _phase_steps(
    repo_root: Path, plan_rel: str | None, phase: int | None
) -> tuple[list[str], list[str]]:
    if plan_rel is None or phase is None:
        return [], []
    from fr.parser import PlanSchemaError, parse
    from fr.record.gates import refactor_gaps

    try:
        plan = parse(repo_root / plan_rel)
    except PlanSchemaError:
        return [], []
    ph = next((p for p in plan.phases if p.phase.number == phase), None)
    if ph is None:
        return [], []
    ids = [s.id for t in ph.tasks for s in t.steps]
    return ids, refactor_gaps(plan, phase)


def record_brief(
    repo_root: Path,
    state: RunState,
    step: Step,
    group: Step | None = None,
    item: str | None = None,
) -> RecordBrief:
    """The record a unit of `state` is handed, or its in-progress form."""
    path = record_path(repo_root, state.run, step.id, item)
    rel = path.relative_to(repo_root).as_posix()
    plan_rel = next(
        (r.emitted["plan"] for r in state.steps.values() if r.emitted and "plan" in r.emitted),
        None,
    )
    phase = None
    if item is not None:
        head, _, tail = item.partition("/")
        phase = int(tail) if head == "phase" and tail.isdigit() else None
    allowed = allowed_sections(step, group)
    ticks, gaps = _phase_steps(repo_root, plan_rel, phase) if "ticks" in allowed else ([], [])
    emits = tuple(step.emits) or (tuple(group.emits) if group is not None else ())
    resolve = f"fr run resolve {state.run} --step {step.id}"
    if item is not None:
        resolve += f" --item {item}"
    resolve += f" --record {rel}"
    template = render_template(
        run=state.run,
        step=step.id,
        item=item,
        allowed=allowed,
        tick_ids=ticks,
        refactor_tasks=gaps,
        evidence=list(step.evidence),
        emitted=[n for n in _EMITTED_NAMES if n in emits],
        resolve=resolve,
    )
    progress: str | None = None
    if path.is_file():
        try:
            progress = f"record in progress: {in_progress_summary(load_record(path))} — {rel}"
        except RecordError as e:
            progress = f"record in progress but unreadable ({e}) — {rel}"
    return RecordBrief(path=rel, template=template, in_progress=progress)
