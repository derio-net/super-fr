"""Plan writer — renders a Plan AST back to markdown.

Preserves body content for lossless round-trip:
parse -> write -> parse = identical AST.
"""

from __future__ import annotations

from pathlib import Path

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Step, Task


def write_plan(plan: Plan, path: Path) -> None:
    """Write a Plan AST to a markdown file."""
    lines: list[str] = []
    _write_header(lines, plan)
    lines.append("")
    lines.append("---")
    lines.append("")

    if plan.format is PlanFormat.PHASED:
        _write_phases(lines, plan.phases)
    else:
        _write_tasks(lines, plan.tasks)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_header(lines: list[str], plan: Plan) -> None:
    """Write the plan header block.

    Emits structured fields in canonical order, then any free-form preamble
    (``**Architecture:**``, ``**Tech Stack:**``, blockquotes, …) captured
    by the parser so it survives round-trip.
    """
    lines.append(f"# {plan.title}")
    lines.append("")
    if plan.spec:
        lines.append(f"**Spec:** `{plan.spec}`")
    lines.append(f"**Status:** {plan.status}")
    lines.append("")
    lines.append(f"**Goal:** {plan.goal}")
    if plan.preamble:
        lines.append("")
        lines.append(plan.preamble)


def _write_phases(lines: list[str], phases: tuple[Phase, ...]) -> None:
    """Write all phases in phased format."""
    for i, phase in enumerate(phases):
        if i > 0:
            lines.append("")
        lines.append(f"## Phase {phase.number}: {phase.title} [{phase.tag}]")
        lines.append("")
        if phase.tracking_url:
            lines.append(f"<!-- Tracking: {phase.tracking_url} -->")
            lines.append("")
        lines.append(_format_depends_on(phase))
        if phase.track_label is not None:
            lines.append(f"**Track:** {phase.track_label}")
        lines.append("")
        _write_tasks(lines, phase.tasks)


def _format_depends_on(phase: Phase) -> str:
    """Render the ``**Depends on:**`` line for a phase.

    Roots (no declared deps) render as an em-dash sentinel; phases with
    dependencies render as a comma-separated ``Phase N`` list matching
    what ``_parse_depends_on`` reads back.
    """
    if not phase.depends_on:
        return "**Depends on:** —"
    refs = ", ".join(f"Phase {n}" for n in phase.depends_on)
    return f"**Depends on:** {refs}"


def _write_tasks(lines: list[str], tasks: tuple[Task, ...]) -> None:
    """Write all tasks."""
    for i, task in enumerate(tasks):
        if i > 0:
            lines.append("")
        tag_suffix = f" [{task.tag}]" if task.tag else ""
        lines.append(f"### Task {task.number}: {task.title}{tag_suffix}")
        lines.append("")
        if task.files_mentioned:
            lines.append("**Files:**")
            verbs = task.file_mention_verbs
            for i, f in enumerate(task.files_mentioned):
                verb = verbs[i] if i < len(verbs) else "Create"
                lines.append(f"- {verb}: `{f}`")
            lines.append("")
        _write_steps(lines, task.steps)


def _write_steps(lines: list[str], steps: tuple[Step, ...]) -> None:
    """Write all steps within a task."""
    for step in steps:
        label = step.label if step.label is not None else str(step.number)
        lines.append(f"- [{step.state}] **Step {label}: {step.title}**")
        if step.body:
            lines.append("")
            lines.append(step.body)
        lines.append("")
