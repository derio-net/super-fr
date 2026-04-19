"""vk skills — condensed overview of the vk-* skills and their CLI subcommands."""

from __future__ import annotations

import typer

from vk.commands.dispatch_cmd import dispatch_app
from vk.commands.execute_cmd import execute_app
from vk.commands.plan_cmd import plan_app
from vk.commands.progress_cmd import progress_app

SKILLS: list[tuple[str, str, typer.Typer, str]] = [
    (
        "vk-plan",
        "plan",
        plan_app,
        "Write phase-structured plans with operator collaboration.",
    ),
    (
        "vk-dispatch",
        "dispatch",
        dispatch_app,
        "Dispatch plan phases to GitHub Issues (one Issue per phase).",
    ),
    (
        "vk-execute",
        "execute",
        execute_app,
        "Execute a single agentic phase (agent-facing; one phase = one PR).",
    ),
    (
        "vk-progress",
        "progress",
        progress_app,
        "Work lifecycle — sync, board, create, transition, audit.",
    ),
]


def _subcommands(app: typer.Typer) -> list[tuple[str, str]]:
    """Return (name, first-line-help) for each subcommand of a Typer app."""
    click_group = typer.main.get_command(app)
    rows: list[tuple[str, str]] = []
    for name, cmd in click_group.commands.items():
        help_text = (cmd.help or "").strip().splitlines()[0] if cmd.help else ""
        rows.append((name, help_text))
    return rows


def skills() -> None:
    """Show an overview of the vk-* skills and their CLI subcommands."""
    for skill_name, cli_name, app, purpose in SKILLS:
        typer.echo(f"{skill_name} — {purpose}")
        rows = _subcommands(app)
        width = max((len(n) for n, _ in rows), default=0)
        for sub_name, sub_help in rows:
            typer.echo(f"  vk {cli_name} {sub_name:<{width}}  {sub_help}")
        typer.echo()
    typer.echo("Full skill docs: ~/.claude/plugins/cache/derio-net/superpowers-for-vk/")
