"""`fr triage state export|import` (spec 2026-10-05-triage-pages-goal, R12, §H).

The same scope options as every `fr triage` verb. `<dir>/<scope>/` is the repo-side
root: `export --to <dir>` writes it, `import --from <dir>` reads it. Both print every
file they copied and every file they skipped. Neither reads or writes a registered
artifact, so `triage` stays in `READ_ONLY_COMMANDS`. Exit codes: 0 success; 2 usage, or a
repo-side root that is a symlink or leaves the given directory (nothing is read or written).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.markup import escape

import fr.commands.triage_cmd as triage_cmd
from fr.commands.triage_cmd import DirOpt, OrgOpt, RepoOpt, console, err_console, triage_app
from fr.triage.errors import TriageError
from fr.triage.model import state_dir
from fr.triage.state_sync import SyncReport, check_scope_name, export_state, import_state

state_app = typer.Typer(
    name="state",
    help="Copy a scope's durable state (judgements, origins, manifests, fragments, "
    "snapshots) to a repo directory and back.",
    no_args_is_help=True,
)
triage_app.add_typer(state_app)


def _refuse(exc: TriageError) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
    raise typer.Exit(code=2) from exc


def _print(report: SyncReport) -> None:
    for rel in report.copied:
        console.print(f"copied {rel}", markup=False, soft_wrap=True)
    for skip in report.skipped:
        console.print(f"skipped {skip.path} ({skip.reason})", markup=False, soft_wrap=True)
    console.print(
        f"{len(report.copied)} copied, {len(report.skipped)} skipped",
        markup=False,
        soft_wrap=True,
    )


@state_app.command("export")
def export_command(
    to: Annotated[
        Path, typer.Option("--to", help="Repo directory; the state lands in <dir>/<scope>/.")
    ],
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Copy the scope's durable state to <dir>/<scope>/. Facts and pages never travel."""
    scope = triage_cmd._scope(repo, org)
    try:
        report = export_state(state_dir(scope, dir_override), to, check_scope_name(scope.name))
    except TriageError as exc:
        _refuse(exc)
    _print(report)


@state_app.command("import")
def import_command(
    from_: Annotated[Path, typer.Option("--from", help="Repo directory holding <dir>/<scope>/.")],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite state files newer than the repo copy.")
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Copy <dir>/<scope>/ back into the state directory; a state file newer than its
    repo copy is skipped unless --force."""
    scope = triage_cmd._scope(repo, org)
    try:
        report = import_state(
            from_, check_scope_name(scope.name), state_dir(scope, dir_override), force=force
        )
    except TriageError as exc:
        _refuse(exc)
    _print(report)
