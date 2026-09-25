"""`fr pickup` CLI — output phase scope for an agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from fr import parse
from fr.commands.common import require_migrated_layout, resolve_repo_root
from fr.parser import PlanSchemaError
from fr.run.closeout import CloseoutNotReadyError, closeout_brief
from fr.run.model import RunStateError, load_run_state

if TYPE_CHECKING:
    from fr.record.template import RecordBrief

console = Console()
err_console = Console(stderr=True)


def pickup_command(
    plan_dir: Path | None = typer.Argument(None, help="Path to plan folder."),
    phase: int | None = typer.Option(None, "--phase", help="Phase number to pick up."),
    run: str | None = typer.Option(
        None,
        "--run",
        help="Run id — print the closeout brief for a finished run's `fr pickup --run` "
        "handoff instead of a phase's scope. Mutually exclusive with a plan dir/--phase.",
    ),
) -> None:
    """Output a phase's scope (markdown) for an agent, or a run's closeout
    brief. No state mutation either way.

    Phase mode returns: phase title, all step text (full multi-line), PR
    title template, dependency reminder, pointer to `_prose.md` for
    plan-level context.

    `--run` mode (spec 2026-09-25-fr-goal-closeout-defects §3.D.1) returns a
    self-contained closeout brief for a run whose `deliver` step is done —
    read by a brand-new session that inherits none of the delivering
    session's context.
    """
    require_migrated_layout()

    if run is not None:
        if plan_dir is not None or phase is not None:
            err_console.print(
                "[red]--run cannot be combined with a plan dir or --phase — pick one mode[/red]"
            )
            raise typer.Exit(2)
        repo_root = resolve_repo_root()
        try:
            run_state = load_run_state(repo_root, run)
        except RunStateError as e:
            err_console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from e
        try:
            brief = closeout_brief(repo_root, run_state)
        except CloseoutNotReadyError as e:
            err_console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from e
        typer.echo(brief)
        return

    if plan_dir is None or phase is None:
        err_console.print("[red]pass a plan dir with --phase, or --run <run-id>[/red]")
        raise typer.Exit(2)

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
    lines.extend(_record_section(plan, phase))
    lines.append("---")
    lines.append("")
    lines.append(f"For plan-level context, read `{plan.repo_relative_dir}/_prose.md`.")
    # Disable Rich markup parsing — the PR title contains literal "[repo]"
    # which Rich would otherwise interpret as a tag and strip.
    typer.echo("\n".join(lines))


def _record_section(plan: object, phase: int) -> list[str]:
    """The phase's step record (spec 2026-09-25 §5.C.3), when a run on disk
    executes this plan: the in-progress record if one exists (a resumed
    session continues it), else the pre-filled template. Nothing when no run
    names the plan — the runner path has no cursor and uses the verbs."""
    try:
        found = _run_unit_record(plan, phase)
    except Exception:  # noqa: BLE001 — pickup never fails over its optional section
        return []
    if found is None:
        return []
    lines = ["## Step record", ""]
    if found.in_progress:
        lines += [found.in_progress, "", "Continue it; do not start a new one.", ""]
        return lines
    lines += [
        f"Fill `{found.path}` as you work:",
        "",
        "```yaml",
        found.template.rstrip(),
        "```",
        "",
    ]
    return lines


def _run_unit_record(plan: object, phase: int) -> RecordBrief | None:
    from fr.commands.run_cmd import _resolve_manifest_for_state
    from fr.record.template import record_brief
    from fr.run.model import RUNS_REL, parse_run_state

    repo_root = getattr(plan, "repo_root", None)
    rel = getattr(plan, "repo_relative_dir", None)
    if repo_root is None or rel is None:
        return None
    for path in sorted((repo_root / RUNS_REL).glob("*.yaml")):
        try:
            state = parse_run_state(path.read_text())
        except Exception:  # noqa: BLE001, S112 — an unreadable cursor is not this plan's
            continue
        if not any(r.emitted and r.emitted.get("plan") == str(rel) for r in state.steps.values()):
            continue
        manifest = _resolve_manifest_for_state(repo_root, state)
        for group in manifest.steps:
            for member in group.steps:
                if "plan:ticks" in (member.emits or group.emits):
                    return record_brief(repo_root, state, member, group, f"phase/{phase}")
    return None
