"""fr init — repo initialization commands (devcontainer profile scaffolding)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from fr.isolation.migrate import SECRETS_BLOCK, migrate_repo
from fr.isolation.scaffold import KNOWN_TOOLS, scaffold_profile
from fr.isolation.types import IsolationError
from fr.plan_validator_wrapper import (
    ValidatorWrapperError,
    ensure_validator_wrapper,
    validator_wrapper_path,
)

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
        [],
        help="Tool to include (repeatable; <tool>[@<version>]; known tools: "
        f"{', '.join(sorted(KNOWN_TOOLS))}; unknown tools are refused — see --feature).",
    ),
    feature: list[str] = typer.Option(
        [],
        "--feature",
        help="Raw devcontainer feature ref to include with no options (repeatable) — "
        "the escape hatch for a tool --tool does not know.",
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
        typer.echo(
            f"error: --backend must be one of github, gitlab, gitea; got {backend!r}", err=True
        )
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
            features=list(feature),
        )
    except IsolationError as err:
        typer.echo(f"error: {err}", err=True)
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


@init_app.command("validator-wrapper")
def validator_wrapper_cmd(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
) -> None:
    """Write scripts/validate-plans.sh (0755) and stage it — the harness-neutral
    remedy every isolation guard names when a plan repo is missing the wrapper.
    Idempotent; refuses (exit 2) rather than overwrite a foreign file there."""
    repo_root = repo.resolve()
    target = validator_wrapper_path(repo_root)
    try:
        changed = ensure_validator_wrapper(repo_root)
    except ValidatorWrapperError as err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(2) from err
    if (repo_root / ".git").exists():
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", str(target.relative_to(repo_root))],
            check=False,
        )
    if changed:
        typer.echo(f"wrote {target} — commit it to make it visible to isolation guards.")
    else:
        typer.echo(f"{target} already up to date.")
