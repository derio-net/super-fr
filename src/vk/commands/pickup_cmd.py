"""`vk pickup` CLI — output phase scope for an agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from vk import parse
from vk.commands.common import require_migrated_layout
from vk.parser import PlanSchemaError

console = Console()
err_console = Console(stderr=True)


def pickup_command(
    plan_dir: Path = typer.Argument(..., help="Path to plan folder."),
    phase: int = typer.Option(..., "--phase", help="Phase number to pick up."),
) -> None:
    """Output a phase's scope (markdown) for an agent. No state mutation.

    Returns: phase title, all step text (full multi-line), PR title template,
    dependency reminder, pointer to _prose.md for plan-level context.
    """
    require_migrated_layout()
    try:
        plan = parse(plan_dir)
    except PlanSchemaError as e:
        err_console.print(f"[red]parse error:[/red] {e}")
        raise typer.Exit(2) from e

    matched = next((p for p in plan.phases if p.phase.number == phase), None)
    if matched is None:
        err_console.print(f"phase {phase} not found in plan")
        raise typer.Exit(2)

    total = len(plan.phases)
    lines: list[str] = []
    lines.append(
        f"# Phase {matched.phase.number}/{total}: {matched.phase.title} [{matched.phase.tag}]"
    )
    lines.append("")
    if matched.phase.depends_on:
        lines.append(
            f"**Depends on:** Phase(s) {', '.join(str(n) for n in matched.phase.depends_on)}"
        )
    else:
        lines.append("**Depends on:** —")
    lines.append("")
    lines.append("## PR title template (when you open the PR)")
    lines.append("")
    lines.append(
        f"`[{plan.meta.target_repo}] {plan.meta.plan} · "
        f"Phase {matched.phase.number}/{total} · {matched.phase.title}`"
    )
    lines.append("")
    lines.append("## Tasks and steps")
    lines.append("")
    for task in matched.tasks:
        lines.append(f"### Task {task.number}: {task.title}")
        lines.append("")
        for step in task.steps:
            state = matched.state.steps[step.id].state
            mark = "x" if state == "x" else ("-" if state == "-" else " ")
            # Multi-line step text rendered as nested content under the
            # list item. 4-space indent is the markdown convention for
            # "continuation paragraph under a list item" — preserves
            # code-fence semantics for previewers and `gh issue view`.
            lines.append(f"- [{mark}] **{step.id}**")
            for sub in step.text.splitlines() or [""]:
                lines.append(f"    {sub}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"For plan-level context, read `{plan.repo_relative_dir}/_prose.md`.")
    # Disable Rich markup parsing — the PR title contains literal "[repo]"
    # which Rich would otherwise interpret as a tag and strip.
    typer.echo("\n".join(lines))
