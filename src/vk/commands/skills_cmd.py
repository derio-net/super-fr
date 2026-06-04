"""vk skills — overview of the v2 CLI surface and the skill files that document it.

Two sections:
  - **Commands** — every top-level command and sub-app, introspected from the
    typer app at runtime (so it stays in sync with the actual surface).
  - **Skills** — the four `vk-*` SKILL.md files. v2 skills are not 1:1 with
    sub-apps (e.g. `vk-execute` orchestrates `vk pickup` + `vk plan edit` +
    `vk apply`), so the skill section is free-form prose pointing at the
    relevant commands rather than a single-app mapping.
"""

from __future__ import annotations

import typer

# Free-form skill summaries — what each `vk-*` skill is for and which CLI
# verbs it orchestrates. Update alongside the SKILL.md files.
SKILLS: list[tuple[str, str, str]] = [
    (
        "vk-plan",
        "Author / edit plans (skill).",
        "vk plan {create,edit,rework,rework-add,rework-list,self-review}",
    ),
    (
        "vk-dispatch",
        "Reconcile a plan's GitHub Issues (skill).",
        "vk apply [--yes] [--format text|json]",
    ),
    (
        "vk-execute",
        "Implement a phase end-to-end (skill).",
        "vk pickup --phase N  →  vk plan edit --tick / --complete-phase  →  vk apply --yes",
    ),
    (
        "vk-progress",
        "Plan / spec progress reporting (skill).",
        "vk apply  +  vk spec status [--all]  +  vk plan edit",
    ),
    (
        "vk-goal",
        "Autonomous goal-to-PR pipeline (skill).",
        "vk plan {create,self-review,edit}  →  vk spec status",
    ),
]


def _commands(app: typer.Typer) -> list[tuple[str, str]]:
    """Introspect a typer app: return (name, first-line-help) for every command/sub-app."""
    import click

    click_group = typer.main.get_command(app)
    assert isinstance(click_group, click.Group), "Typer app must compile to a Group"
    rows: list[tuple[str, str]] = []
    for name, cmd in click_group.commands.items():
        help_text = (cmd.help or "").strip().splitlines()[0] if cmd.help else ""
        rows.append((name, help_text))
    return rows


def skills() -> None:
    """Show the v2 CLI surface + skill summaries."""
    # Late import — avoids cycle: cli.py imports skills_cmd, and we need cli.app here.
    from vk.cli import app

    typer.echo("Commands:")
    rows = _commands(app)
    width = max((len(n) for n, _ in rows), default=0)
    for name, help_text in rows:
        typer.echo(f"  vk {name:<{width}}  {help_text}")
    typer.echo()
    typer.echo("Skills (full docs in skills/<name>/SKILL.md):")
    skill_width = max((len(n) for n, _, _ in SKILLS), default=0)
    for name, summary, verbs in SKILLS:
        typer.echo(f"  {name:<{skill_width}}  {summary}")
        typer.echo(f"  {' ' * skill_width}    →  {verbs}")
    typer.echo()
