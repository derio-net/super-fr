"""Plan format converter — flat <-> phased conversions.

Five modes:
- to_flat: Phased -> flat (refuses tracking comments without force)
- to_phased_single: Flat -> single phase
- to_phased_one_per_task: Flat -> one phase per task
- to_phased_group_by_tag: Flat -> phases grouped by consecutive tag
- add_deps: Migrate phased plan by adding **Depends on:** lines
"""

from __future__ import annotations

import re
from collections import Counter
from itertools import groupby
from pathlib import Path
from typing import Literal, cast

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Task

_TagType = Literal["manual", "agentic"]


class MixedPlanError(ValueError):
    """Raised when some phases have **Depends on:** and others do not."""


_DEPENDS_LINE_RE = re.compile(r"^\*\*Depends on:\*\*", re.MULTILINE)
_PHASE_HEADER_RE = re.compile(r"^## Phase (\d+):.*\[(manual|agentic)\][ \t]*$", re.MULTILINE)


def add_deps(plan_path: Path) -> None:
    """Migrate a phased plan by adding **Depends on:** lines.

    Phase 1 gets '—'; phase N (N>=2) gets 'Phase {N-1}'. Idempotent: phases
    that already have the line are left alone. If some phases have the line
    and others do not, raise MixedPlanError without writing.
    """
    text = plan_path.read_text()
    headers = list(_PHASE_HEADER_RE.finditer(text))
    if not headers:
        return  # nothing to do; not a phased plan

    # Determine which phases already have the line.
    slices: list[tuple[int, int]] = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        slices.append((match.end(), end))
    has_line = [bool(_DEPENDS_LINE_RE.search(text[s:e])) for s, e in slices]

    if any(has_line) and not all(has_line):
        offenders_with = [
            str(int(h.group(1))) for h, flag in zip(headers, has_line, strict=True) if flag
        ]
        offenders_without = [
            str(int(h.group(1))) for h, flag in zip(headers, has_line, strict=True) if not flag
        ]
        raise MixedPlanError(
            f"Phases {', '.join(offenders_with)} have **Depends on:** but phases "
            f"{', '.join(offenders_without)} do not — "
            f"declare both or neither (auto-inference is disabled)."
        )
    if all(has_line):
        return  # idempotent no-op

    # Insert the line immediately after the header (skipping any tracking comment).
    new_parts: list[str] = []
    cursor = 0
    for i, match in enumerate(headers):
        phase_num = int(match.group(1))
        dep_line = (
            "**Depends on:** —" if phase_num == 1 else f"**Depends on:** Phase {phase_num - 1}"
        )
        header_end = match.end()
        # Look for a tracking comment immediately after the header.
        tail = text[header_end : slices[i][1]]
        tail_lines = tail.split("\n")
        insert_at = header_end
        if len(tail_lines) >= 2 and tail_lines[1].startswith("<!-- Tracking:"):
            insert_at = header_end + len("\n" + tail_lines[1])

        new_parts.append(text[cursor:insert_at])
        new_parts.append(f"\n{dep_line}")
        cursor = insert_at
    new_parts.append(text[cursor:])
    plan_path.write_text("".join(new_parts))


def to_flat(plan: Plan, *, force: bool = False) -> Plan:
    """Convert a phased plan to flat format.

    Task numbering resets globally (1, 2, 3...).
    Each task inherits its parent phase's tag.
    Refuses if plan has tracking comments unless force=True.
    """
    if plan.format is PlanFormat.FLAT:
        msg = "Plan is already flat"
        raise ValueError(msg)

    if not force:
        has_tracking = any(p.tracking_url for p in plan.phases)
        if has_tracking:
            msg = (
                "Cannot convert to flat: plan has tracking comments linking to "
                "GitHub Issues. Use force=True to convert anyway (this will orphan "
                "the issue links)."
            )
            raise ValueError(msg)

    tasks: list[Task] = []
    num = 1
    for phase in plan.phases:
        for task in phase.tasks:
            tasks.append(
                Task(
                    number=num,
                    title=task.title,
                    tag=task.tag or phase.tag,
                    steps=task.steps,
                    files_mentioned=task.files_mentioned,
                    file_mention_verbs=task.file_mention_verbs,
                )
            )
            num += 1

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.FLAT,
        phases=(),
        tasks=tuple(tasks),
        preamble=plan.preamble,
    )


def to_phased_single(plan: Plan) -> Plan:
    """Convert a flat plan to a single phase.

    The phase gets the dominant tag (most common among tasks).
    On a tie, prefers 'agentic'.
    """
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    tag = _dominant_tag(plan.tasks)
    renumbered = _renumber_tasks(plan.tasks)
    phase = Phase(
        number=1,
        title=plan.title,
        tag=tag,
        depends_on=(),
        tasks=renumbered,
        tracking_url=None,
    )

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=(phase,),
        tasks=(),
        preamble=plan.preamble,
    )


def to_phased_one_per_task(plan: Plan) -> Plan:
    """Convert a flat plan to phased with one phase per task."""
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    phases: list[Phase] = []
    for i, task in enumerate(plan.tasks):
        renumbered_task = Task(
            number=1,
            title=task.title,
            tag=None,
            steps=task.steps,
            files_mentioned=task.files_mentioned,
            file_mention_verbs=task.file_mention_verbs,
        )
        phases.append(
            Phase(
                number=i + 1,
                title=task.title,
                tag=task.tag or "agentic",
                depends_on=(),
                tasks=(renumbered_task,),
                tracking_url=None,
            )
        )

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=tuple(phases),
        tasks=(),
        preamble=plan.preamble,
    )


def to_phased_group_by_tag(plan: Plan) -> Plan:
    """Convert a flat plan to phased, grouping consecutive same-tag tasks."""
    if plan.format is PlanFormat.PHASED:
        msg = "Plan is already phased"
        raise ValueError(msg)

    phases: list[Phase] = []
    phase_num = 1

    for tag, group in groupby(plan.tasks, key=lambda t: t.tag or "agentic"):
        group_tasks = list(group)
        renumbered = _renumber_tasks(tuple(group_tasks))
        if len(group_tasks) == 1:
            title = group_tasks[0].title
        else:
            title = f"Phase {phase_num}"

        phases.append(
            Phase(
                number=phase_num,
                title=title,
                tag=cast(_TagType, tag),
                depends_on=(),
                tasks=renumbered,
                tracking_url=None,
            )
        )
        phase_num += 1

    return Plan(
        title=plan.title,
        spec=plan.spec,
        status=plan.status,
        goal=plan.goal,
        format=PlanFormat.PHASED,
        phases=tuple(phases),
        tasks=(),
        preamble=plan.preamble,
    )


def _dominant_tag(tasks: tuple[Task, ...]) -> _TagType:
    """Return the most common tag among tasks.  Tie-breaks to 'agentic'."""
    counts: Counter[str] = Counter()
    for t in tasks:
        counts[t.tag or "agentic"] += 1
    if not counts:
        return "agentic"
    max_count = max(counts.values())
    if counts.get("agentic", 0) == max_count:
        return "agentic"
    return cast(_TagType, counts.most_common(1)[0][0])


def _renumber_tasks(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Renumber tasks starting from 1."""
    return tuple(
        Task(
            number=i + 1,
            title=t.title,
            tag=t.tag,
            steps=t.steps,
            files_mentioned=t.files_mentioned,
            file_mention_verbs=t.file_mention_verbs,
        )
        for i, t in enumerate(tasks)
    )
