"""`vk v2 migrate v1-to-v2` CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from vk.v2.migrate import MigrationError, migrate_repo

console = Console()
err_console = Console(stderr=True)

migrate_app = typer.Typer(help="v2 migration tools.", no_args_is_help=True)


@migrate_app.command("v1-to-v2")
def v1_to_v2_cmd(
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply the migration. Without this flag, runs as a preview (dry-run is the default).",
    ),
    include_in_progress: bool = typer.Option(
        False,
        "--include-in-progress",
        help="Migrate plans even if Status != Complete.",
    ),
) -> None:
    """Convert every v1 .md plan in this repo to a v2 folder + rewrite spec tables.

    Defaults to a preview. Pass --yes to actually write changes.
    """
    repo_root = Path.cwd()
    try:
        outcomes = migrate_repo(
            repo_root,
            dry_run=not yes,
            include_in_progress=include_in_progress,
        )
    except MigrationError as e:
        err_console.print(f"[red]migration error:[/red] {e}")
        raise typer.Exit(2) from e

    for o in outcomes:
        console.print(f"  {o.plan_path.name}: {o.reason}")
    n_migrated = sum(1 for o in outcomes if o.reason.startswith("migrated"))
    n_skipped = sum(1 for o in outcomes if o.reason.startswith("skipped"))
    suffix = "" if yes else " (dry-run; pass --yes to apply)"
    console.print(f"\n{n_migrated} migrated, {n_skipped} skipped.{suffix}")
