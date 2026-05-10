"""vk skills — condensed overview of the vk-* skills and their CLI subcommands."""

from __future__ import annotations

import typer

from vk.commands.migrate_cmd import migrate_app
from vk.commands.plan_cmd import plan_app
from vk.commands.spec_cmd import spec_app

SKILLS: list[tuple[str, str, typer.Typer, str]] = [
    (
        "vk-plan",
        "plan",
        plan_app,
        "Author / edit plans (create, tick, complete, rework, self-review).",
    ),
    (
        "vk-dispatch",
        "spec",
        spec_app,
        "Spec-level rollups (status across plans).",
    ),
    (
        "vk-execute",
        "migrate",
        migrate_app,
        "v1-to-v2 plan-folder migration.",
    ),
]

# Singleton commands (not Typer sub-apps) shown after the grouped skills.
SINGLETONS: list[tuple[str, str]] = [
    ("vk apply <plan>", "Render → observe → diff → mutate. --yes to write."),
    ("vk pickup <plan> --phase N", "Markdown phase scope for an agent."),
]


def _subcommands(app: typer.Typer) -> list[tuple[str, str]]:
    """Return (name, first-line-help) for each subcommand of a Typer app."""
    import click

    click_group = typer.main.get_command(app)
    assert isinstance(click_group, click.Group), "Typer app must compile to a Group"
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
    typer.echo("Singleton commands:")
    for cmd, help_text in SINGLETONS:
        typer.echo(f"  {cmd}  —  {help_text}")
    typer.echo()
    typer.echo("Full skill docs: ~/.claude/plugins/cache/derio-net/superpowers-for-vk/")
