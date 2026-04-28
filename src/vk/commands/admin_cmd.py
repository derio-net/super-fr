"""vk admin — operator-driven cross-repo administration."""

from __future__ import annotations

import typer
from rich.console import Console

from vk import gh

console = Console()
err_console = Console(stderr=True)

admin_app = typer.Typer(help="Operator-driven cross-repo administration.")


def _resolve_target_repos(*, owner: str, repo: str | None) -> list[str]:
    """Resolve target repos as `owner/name` slugs.

    With explicit `repo`, returns the single slug. Without, enumerates
    non-archived repos under `owner` via gh.list_repos.
    """
    if repo:
        return [f"{owner}/{repo}"]
    return [f"{owner}/{r['name']}" for r in gh.list_repos(owner=owner)]


@admin_app.command(name="labels-sync")
def labels_sync(
    owner: str = typer.Option(..., "--owner", help="GitHub owner / org."),
    repo: str | None = typer.Option(
        None, "--repo", help="Single repo (without owner). Default: all repos under owner."
    ),
    remove_defaults: bool = typer.Option(
        False,
        "--remove-defaults",
        help="Also remove GitHub default labels with zero attached Issues.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Print planned changes without mutating (default). Use --apply or --yes.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Apply changes without confirmation."),
) -> None:
    """Sync repo labels to the canonical registry across one or many repos."""
    if yes:
        dry_run = False  # noqa: F841 — used in Phase 2
    # Body is wired in Phase 2 of this plan; apply mode in Phase 3.
    raise NotImplementedError("labels-sync body lands in Phase 2 of this plan.")
