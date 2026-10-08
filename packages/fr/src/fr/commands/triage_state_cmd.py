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
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    WorkspaceOpt,
    console,
    err_console,
    resolve_state_dir,
    triage_app,
)
from fr.triage.errors import TriageError
from fr.triage.model import Scope
from fr.triage.privacy import guard_state
from fr.triage.scope_config import load_durable, scope_id
from fr.triage.state_ref import fetch_state, push_state, read_base, ref_name
from fr.triage.state_sync import SyncReport, check_scope_name, export_state, import_state

state_app = typer.Typer(
    name="state",
    help="Copy a scope's durable state (judgements, origins, manifests, fragments, "
    "snapshots) to a repo directory and back, or push and fetch its state ref.",
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Copy the scope's durable state to <dir>/<scope>/. Facts and pages never travel.
    With a state repo, the privacy guard runs first (cloud-triage R8)."""
    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    try:
        state_repo = load_durable(target).state_repo
        if state_repo is not None:
            client = triage_cmd.make_visibility_client()
            guard_state(target, scope=scope, state_repo=state_repo, client_for=lambda _r: client)
        report = export_state(target, to, check_scope_name(scope.name))
    except TriageError as exc:
        _refuse(exc)
    _print(report)


RemoteOpt = Annotated[
    str | None,
    typer.Option(
        "--remote",
        help="Where the state ref is pushed and fetched: a git URL or path (default: the "
        "state repo on GitHub).",
    ),
]


def _ref_target(scope: Scope, target: Path, remote: str | None) -> tuple[str, str, str]:
    """(state repo, remote, scope id) for a push or fetch; exit 2 without a state repo."""
    state_repo = load_durable(target).state_repo
    if state_repo is None:
        raise TriageError(
            "this scope has no state repo (scope-durable.yaml): run `fr triage collect` at a "
            "terminal to choose one (cloud-triage R7)"
        )
    return state_repo, remote or triage_cmd.state_remote(state_repo), scope_id(scope)


@state_app.command("push")
def push_command(
    remote: RemoteOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Push the scope's state to its ref, the branch refs/heads/fr-triage/<scope-id>, as a
    compare-and-swap on the ref this state was last fetched from or pushed to (R5); the
    privacy guard runs first (R8). Exit 2 on a refusal (the privacy guard's, or the remote
    refusing the push: pushing is this verb's whole job) or a ref someone else moved."""
    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace, sync=False)
    try:
        state_repo, url, sid = _ref_target(scope, target, remote)
        sha = push_state(
            target,
            url,
            sid,
            expected_old=read_base(target, remote=url, ref=ref_name(sid)),
            scope=scope,
            state_repo=state_repo,
            client=triage_cmd.make_visibility_client(),
        )
    except TriageError as exc:
        _refuse(exc)
    console.print(f"pushed {ref_name(sid)} {sha}", markup=False, soft_wrap=True)


@state_app.command("fetch")
def fetch_command(
    remote: RemoteOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
    state_repo_opt: Annotated[
        str | None,
        typer.Option(
            "--state-repo",
            help="OWNER/REPO holding the ref, for a fresh workspace with no state yet.",
        ),
    ] = None,
    discard_local: Annotated[
        bool,
        typer.Option(
            "--discard-local",
            help="Overwrite state changes that were never pushed (they are lost).",
        ),
    ] = False,
) -> None:
    """Restore the scope's state from its ref, refs/heads/fr-triage/<scope-id> (R5; the
    legacy refs/fr/triage/<scope-id> when that branch does not exist yet): the state
    directory's ref files become exactly the ref's, and a file the ref no longer carries is
    removed. Changes not yet pushed are never overwritten unless --discard-local. Exit 2 on
    a refusal."""
    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace, sync=False)
    try:
        if state_repo_opt is not None and load_durable(target).state_repo is None:
            url, sid = remote or triage_cmd.state_remote(state_repo_opt), scope_id(scope)
        else:
            _, url, sid = _ref_target(scope, target, remote)
        sha = fetch_state(target, url, sid, discard_local=discard_local)
    except TriageError as exc:
        _refuse(exc)
    if sha is None:
        console.print(f"no {ref_name(sid)} on {url}; nothing restored", markup=False)
        return
    console.print(f"restored {ref_name(sid)} {sha}", markup=False, soft_wrap=True)


@state_app.command("import")
def import_command(
    from_: Annotated[Path, typer.Option("--from", help="Repo directory holding <dir>/<scope>/.")],
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite state files whose mtime is newer than the repo copy's."
        ),
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Copy <dir>/<scope>/ back into the state directory. An identical file is skipped;
    a state file whose mtime is newer than its repo copy's is skipped unless --force.
    Git keeps no mtime: after a fresh checkout or pull the repo copy looks newer, so a
    state file edited before it is overwritten. Export first if you edited one."""
    scope = triage_cmd._scope(repo, org)
    try:
        report = import_state(
            from_,
            check_scope_name(scope.name),
            resolve_state_dir(scope, dir_override, workspace),
            force=force,
        )
    except TriageError as exc:
        _refuse(exc)
    _print(report)
