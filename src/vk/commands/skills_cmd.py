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
        "vk status  →  vk apply [--yes] [--force]  ·  vk undispatch / vk archive to invert/finish",
    ),
    (
        "vk-execute",
        "Implement a phase end-to-end (skill).",
        "vk pickup --phase N  →  vk plan edit --tick / --complete-phase  →  vk apply --yes",
    ),
    (
        "vk-progress",
        "Plan / spec progress reporting (skill).",
        "vk status <plan-dir>  +  vk spec status [--all]  +  vk plan edit  +  vk archive [--all]"
        "  ·  vk repair [--yes] to normalize stale refs",
    ),
    (
        "vk-goal",
        "Autonomous goal-to-PR pipeline (skill).",
        "vk plan {create,self-review,edit}  →  vk spec status",
    ),
    (
        "vk-isolation",
        "Isolated workspace: worktree + devcontainer, exec-bridge (skill).",
        "vk isolation {up,exec,status,down}",
    ),
    (
        "vk-init",
        "Scaffold devcontainer profiles via interview (skill).",
        "vk init scaffold --profile NAME --purpose TEXT [--tool ...] [--secret ...]",
    ),
    (
        "vk-brainstorming",
        "Brainstorm inside vk-isolation; hard stop without a profile (skill).",
        "vk isolation up  →  superpowers:brainstorming  →  vk-plan handoff",
    ),
]


def _commands(app: typer.Typer) -> list[tuple[str, str]]:
    """Introspect a typer app: return (name, first-line-help) for every command/sub-app.

    Duck-typed on purpose: typer ≥0.26 vendors click (`typer._click`), so the
    compiled group is NOT an instance of the externally-installed click's
    Group — isinstance checks (and bare `import click`) break across typer
    versions. `.commands` exists on both lineages.
    """
    click_group = typer.main.get_command(app)
    commands = getattr(click_group, "commands", {})
    rows: list[tuple[str, str]] = []
    for name, cmd in commands.items():
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
