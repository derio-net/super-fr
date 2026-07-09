"""fr init — repo initialization commands (devcontainer profile scaffolding)."""

from __future__ import annotations

from pathlib import Path

import typer

from fr.isolation.migrate import SECRETS_BLOCK, migrate_repo
from fr.isolation.scaffold import scaffold_profile
from fr.isolation.types import IsolationError

init_app = typer.Typer(
    name="init",
    help="Repo initialization: devcontainer profile scaffolding (driven by fr-init).",
    no_args_is_help=True,
)


@init_app.command()
def scaffold(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    profile: str = typer.Option(..., help="Profile name (e.g. dev, readonly, admin)."),
    purpose: str = typer.Option(..., help="One-line purpose, recorded in fr-profiles.yaml."),
    tool: list[str] = typer.Option(
        [], help="Tool to include (repeatable; known tools map to features)."
    ),
    secret: list[str] = typer.Option(
        [], help="Secret KEY the profile expects (repeatable; placeholder scaffolded)."
    ),
    default: bool = typer.Option(False, "--default", help="Make this the repo's default profile."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing profile config."),
    no_commit: bool = typer.Option(
        False, "--no-commit", help="Write the files only; do not commit the profile."
    ),
    backend: str = typer.Option(
        "github",
        "--backend",
        help="Which forge this repo lives on: github (default), gitlab, or gitea. "
        "Picks the devcontainer CLI-install step (github-cli feature vs a "
        "versioned glab/tea binary install) and is recorded in fr-profiles.yaml "
        "for fr._hosts.detect_backend.",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        help="Self-hosted instance hostname (e.g. gitlab.mycorp.com). Omit for "
        "gitlab.com/gitea.com or GitHub.",
    ),
) -> None:
    """Write + commit .devcontainer/<profile>/ and the fr-profiles.yaml entry, plus
    host secrets placeholders. The commit is what lets `fr isolation up` see the
    profile; pass --no-commit to write only."""
    if backend not in ("github", "gitlab", "gitea"):
        typer.echo(f"error: --backend must be one of github, gitlab, gitea; got {backend!r}")
        raise typer.Exit(2)
    try:
        path = scaffold_profile(
            repo.resolve(),
            profile,
            purpose,
            tools=list(tool),
            secrets=list(secret),
            default=default,
            force=force,
            commit=not no_commit,
            backend=backend,  # type: ignore[arg-type]
            host=host,
        )
    except IsolationError as err:
        typer.echo(f"error: {err}")
        raise typer.Exit(2) from err
    typer.echo(f"scaffolded: {path}")


@init_app.command()
def migrate(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    yes: bool = typer.Option(False, "--yes", help="Apply (default is a dry-run preview)."),
) -> None:
    """Rewrite this repo's vk spellings to fr (#272): profiles yaml, devcontainer
    mounts/customizations, isolation state dir. Prints the host secrets-move
    block — never executes it."""
    try:
        actions = migrate_repo(repo.resolve(), yes=yes)
    except IsolationError as err:
        typer.echo(f"error: {err}")
        raise typer.Exit(2) from err
    if not actions:
        typer.echo("nothing to migrate — repo already on fr spellings")
        return
    verb = "applied" if yes else "would apply (re-run with --yes)"
    typer.echo(f"{verb}:")
    for action in actions:
        typer.echo(f"  - {action}")
    typer.echo(SECRETS_BLOCK)
