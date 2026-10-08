"""`fr triage lease show|take` and `fr triage drive pass|record` (spec
2026-10-07-cloud-triage R9, R12, R13, §D, §E).

The lease (`fr.triage.lease`) is the cross-host check that one driver runs per scope;
`lease take --yes` is the operator's explicit take-over of a lease another driver left.

`drive pass` is the `claude-cloud` driver's one pass per wake: restore the state from the
ref, renew the lease (a push, so the privacy guard runs), and run the SAME pass the host
loop runs (`triage_batch_cmd.one_pass`, policy single-sourced, R13), then write the
session requests the runner left to the outbox for the agent to execute. `drive record`
hands the agent's results back to the runner and pushes the ref. `fr triage batch drive`
stays the host adapter's entry.

Exit codes: 0 success (`pass`: acted, or everything is done); 3 (`pass`) nothing to do
but wait, or a wake within the interval of the last pass, which only renews the lease;
2 a refusal (a lease held by another driver, a push conflict, a runner that keeps no
mailbox); 1 a forge write failed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, NoReturn

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
from fr.triage.lease import (
    DEFAULT_INTERVAL_MIN,
    DEFAULT_ROUTINE_MIN,
    DriverKind,
    acquire,
    driver_identity,
    holder_of,
    lease_duration,
    load_lease,
)
from fr.triage.scope_config import host_id, scope_id

lease_app = typer.Typer(
    name="lease",
    help="The drive lease: which driver runs this scope (one per scope).",
    no_args_is_help=True,
)
triage_app.add_typer(lease_app)

drive_app = typer.Typer(
    name="drive",
    help="The cloud driver's one pass per wake, and the record of its session results.",
    no_args_is_help=True,
)
triage_app.add_typer(drive_app)


def _now() -> datetime:
    """The clock; tests replace it."""
    return datetime.now(UTC)


def _fail(message: str, code: int = 2) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(code=code)


IntervalOpt = Annotated[
    float,
    typer.Option("--interval", min=0, help="Minutes between the driver's wakes (lease sizing)."),
]
RoutineOpt = Annotated[
    float,
    typer.Option("--routine", min=0, help="Minutes between the safety-net Routine's wakes."),
]
AsOpt = Annotated[
    str,
    typer.Option("--as", help="The driver this lease is taken for: host or cloud."),
]


def identity_for(kind: str) -> str:
    """This machine's driver identity of *kind* (`host:<host id>`, `cloud:<host id>`)."""
    if kind not in ("host", "cloud"):
        _fail(f"--as must be host or cloud, got {kind!r}")
    kind_: DriverKind = "host" if kind == "host" else "cloud"
    try:
        return driver_identity(kind_, host_id())
    except TriageError as exc:
        _fail(str(exc))


@lease_app.command("show")
def lease_show_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Who holds the scope's drive lease, since when and until when; or `free`."""
    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    if current is None:
        console.print("lease: free", markup=False)
        return
    state = "expired" if current.expired(_now()) else "live"
    console.print(f"lease: {current.holder} ({state})", markup=False, soft_wrap=True)
    console.print(f"  started {current.started.isoformat()}", markup=False)
    console.print(f"  expires {current.expires.isoformat()}", markup=False)
    if current.last_pass is not None:
        console.print(f"  last pass {current.last_pass.isoformat()}", markup=False)


@lease_app.command("take")
def lease_take_command(
    as_: AsOpt = "host",
    interval: IntervalOpt = DEFAULT_INTERVAL_MIN,
    routine: RoutineOpt = DEFAULT_ROUTINE_MIN,
    yes: Annotated[bool, typer.Option("--yes", help="Take it; without it, nothing changes.")] = (
        False
    ),
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Take the scope's drive lease for this machine's driver, from whoever holds it (R9):
    the operator's take-over of a lease another driver left. Refuses without --yes."""
    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    identity = identity_for(as_)
    sid = scope_id(scope)
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    held = f"held by {current.holder}, expires {current.expires.isoformat()}" if current else "free"
    if not yes:
        _fail(
            f"the drive lease is {held}; `fr triage lease take --yes` takes it for "
            f"{holder_of(sid, identity)} (a driver still running under the old holder is "
            "then refused at its next pass)"
        )
    try:
        got = acquire(
            target,
            identity,
            _now(),
            scope_id=sid,
            duration=lease_duration(interval, routine),
            force=True,
            push=lambda: triage_cmd.push_now(scope, target),
        )
    except TriageError as exc:
        _fail(str(exc))
    console.print(
        f"took the drive lease for {got.holder} until {got.expires.isoformat()} (was {held})",
        markup=False,
        soft_wrap=True,
    )


def _read_json(path: Path | None, what: str) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{path}: not a {what} JSON file ({exc})")
