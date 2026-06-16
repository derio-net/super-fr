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
    secret_provider: str = typer.Option(
        "env-file", "--secret-provider", help="Secret backend: env-file (default) | infisical."
    ),
    infisical_project: str | None = typer.Option(
        None,
        "--infisical-project",
        help="Infisical project_id (required for --secret-provider infisical).",
    ),
    infisical_env: str | None = typer.Option(
        None, "--infisical-env", help="Infisical environment slug (e.g. prod)."
    ),
    infisical_path: str | None = typer.Option(
        None,
        "--infisical-path",
        help="Infisical secret path — the isolation boundary; scope narrowly.",
    ),
) -> None:
    """Write + commit .devcontainer/<profile>/ and the fr-profiles.yaml entry, plus
    host secrets placeholders. The commit is what lets `fr isolation up` see the
    profile; pass --no-commit to write only."""
    try:
        infisical = None
        if secret_provider == "infisical":
            if not (infisical_project and infisical_env and infisical_path):
                missing = [
                    flag
                    for flag, val in (
                        ("--infisical-project", infisical_project),
                        ("--infisical-env", infisical_env),
                        ("--infisical-path", infisical_path),
                    )
                    if not val
                ]
                raise IsolationError(f"--secret-provider infisical requires {', '.join(missing)}.")
            infisical = {
                "project_id": infisical_project,
                "env": infisical_env,
                "path": infisical_path,
            }
        path = scaffold_profile(
            repo.resolve(),
            profile,
            purpose,
            tools=list(tool),
            secrets=list(secret),
            default=default,
            force=force,
            commit=not no_commit,
            secret_provider=secret_provider,
            infisical=infisical,
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
