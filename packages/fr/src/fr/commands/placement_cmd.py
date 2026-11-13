"""`fr placement` — move a repo's fr artifacts between placements (spec
2026-11-04-repo-feature-settings R27, R28; §3.E).

Not read-only for the artifact-migration gate: both commands write artifacts, so the
gate applies to them (`placement` is not in `READ_ONLY_COMMANDS`). The gate's placement
DRIFT check alone stays out of their way: `migrate-branch` is that check's remedy.
"""

from __future__ import annotations

import typer

from fr.commands.common import resolve_repo_root
from fr.settings import SettingsError

placement_app = typer.Typer(
    help="Move fr's artifacts between placements: move (R27), migrate-branch (R28).",
    no_args_is_help=True,
)


@placement_app.command("move")
def move_cmd(
    to: str = typer.Option(..., "--to", help="The placement to move to: repo, quiet or stealth."),
    tracking: str | None = typer.Option(
        None, "--tracking", help="With --to stealth: the tracking ref, <repo>@<branch>."
    ),
    run: str | None = typer.Option(
        None, "--run", help="Move one stealth run (from its workspace) instead of the repo."
    ),
) -> None:
    """Copy, verify, switch, then remove: every step idempotent and resumable.

    Refused while any workspace has uncommitted work. Out of `repo`, the removal is a
    pushed branch and a printed `fr pr create` command; nothing is pushed to the default
    branch, and git history still holds the files.
    """
    from fr.placement.move import move

    try:
        move(resolve_repo_root(), to, tracking=tracking, run=run, emit=typer.echo)
    except SettingsError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e


@placement_app.command("migrate-branch")
def migrate_branch_cmd() -> None:
    """Move this workspace branch's artifacts to the repo's current placement (R28).

    Run in a valid workspace: one commit on each side, then pushes both where they
    belong. The CLI-entry gate, `fr push`, `deliver` and `fr validate artifacts` refuse a
    mismatched branch, naming this command; none of them migrates. Under stealth it only
    copies the files into the tracking repo: it never commits on, or pushes, the product
    branch, and names the commits to rewrite instead.
    """
    from fr.placement.drift import migrate_branch

    try:
        migrate_branch(resolve_repo_root(), emit=typer.echo)
    except SettingsError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e
