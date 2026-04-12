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
    """Write the plan header block."""
    lines.append(f"# {plan.title}")
    lines.append("")
    if plan.spec:
        lines.append(f"**Spec:** `{plan.spec}`")
    lines.append(f"**Status:** {plan.status}")
    lines.append("")
    lines.append(f"**Goal:** {plan.goal}")


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
        _write_tasks(lines, phase.tasks)


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
            for f in task.files_mentioned:
                lines.append(f"- Create: `{f}`")
            lines.append("")
        _write_steps(lines, task.steps)


def _write_steps(lines: list[str], steps: tuple[Step, ...]) -> None:
    """Write all steps within a task."""
    for step in steps:
        lines.append(f"- [{step.state}] **Step {step.number}: {step.title}**")
        if step.body:
            lines.append("")
            lines.append(step.body)
        lines.append("")
