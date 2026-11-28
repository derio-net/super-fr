"""`fr run dod <run-id> [--json]` (spec 2026-11-27-ops-gate-truth R18).

Defined here, never in `commands/run_cmd.py` (its line budget): importing this module
registers the command on `run_app`, and `fr.cli` imports it after `run_app`.
"""

from __future__ import annotations

import json

import typer
from rich.markup import escape

from fr.commands.common import resolve_repo_root
from fr.commands.run_cmd import _load_or_exit, err_console, run_app


@run_app.command("dod")
def dod_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    as_json: bool = typer.Option(False, "--json", help="Emit the groups as JSON."),
) -> None:
    """Print a run's Definition of Done, derived from its gates, plan and journals.

    Read-only. Exit 0 when every item is discharged, 1 when one is owed, 2 when the run
    or its inputs cannot be read.
    """
    from fr.run.dod import DodError, definition_of_done, dod_lines

    repo_root = resolve_repo_root()
    state = _load_or_exit(repo_root, run_id)
    try:
        dod = definition_of_done(repo_root, state)
    except DodError as exc:
        err_console.print(
            f"[red]run {escape(run_id)}: the Definition of Done cannot be read: "
            f"{escape(str(exc))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from exc
    if as_json:
        typer.echo(json.dumps({"run": state.run, **dod.as_json()}, indent=2))
    else:
        typer.echo(f"run {state.run}")
        typer.echo("\n".join(dod_lines(dod)))
    raise typer.Exit(0 if dod.discharged else 1)
