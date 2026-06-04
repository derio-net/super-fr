"""vk init — repo initialization commands (devcontainer profile scaffolding)."""

from __future__ import annotations

from pathlib import Path

import typer

from vk.isolation.scaffold import scaffold_profile
from vk.isolation.types import IsolationError

init_app = typer.Typer(
    name="init",
    help="Repo initialization: devcontainer profile scaffolding (driven by vk-init).",
    no_args_is_help=True,
)


@init_app.command()
def scaffold(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    profile: str = typer.Option(..., help="Profile name (e.g. dev, readonly, admin)."),
    purpose: str = typer.Option(..., help="One-line purpose, recorded in vk-profiles.yaml."),
    tool: list[str] = typer.Option([], help="Tool to include (repeatable; known tools map to features)."),
    secret: list[str] = typer.Option([], help="Secret KEY the profile expects (repeatable; placeholder scaffolded)."),
    default: bool = typer.Option(False, "--default", help="Make this the repo's default profile."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing profile config."),
) -> None:
    """Write .devcontainer/<profile>/, vk-profiles.yaml entry, and host secrets placeholders."""
    try:
        path = scaffold_profile(
            repo.resolve(), profile, purpose, tools=list(tool), secrets=list(secret),
            default=default, force=force,
        )
    except IsolationError as err:
        typer.echo(f"error: {err}")
        raise typer.Exit(2) from err
    typer.echo(f"scaffolded: {path}")
