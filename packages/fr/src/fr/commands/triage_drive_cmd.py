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
from datetime import UTC, datetime, timedelta
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


def _write_outbox(path: Path, requests: list[dict[str, Any]]) -> None:
    """`{"requests": [...]}`: the session requests the agent executes (§E step 6, §F)."""
    from fr.artifacts.atomic import write_text_atomic

    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps({"requests": requests}, indent=2, sort_keys=True) + "\n")


OutboxOpt = Annotated[
    Path, typer.Option("--outbox", help="Where the session requests are written (JSON).")
]
StateRepoOpt = Annotated[
    str | None,
    typer.Option(
        "--state-repo",
        help="OWNER/REPO holding the state ref, for a fresh workspace with no state yet "
        "(the driver's brief carries it).",
    ),
]


@drive_app.command("pass")
def drive_pass_command(
    outbox: OutboxOpt,
    statuses: Annotated[
        Path | None,
        typer.Option("--statuses", help="The session statuses the agent read (JSON)."),
    ] = None,
    state_repo: StateRepoOpt = None,
    interval: IntervalOpt = DEFAULT_INTERVAL_MIN,
    routine: RoutineOpt = DEFAULT_ROUTINE_MIN,
    max_inflight: Annotated[
        int,
        typer.Option("--max-inflight", min=1, help="Batches dispatched and unmerged at once."),
    ] = 3,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """One pass of the cloud driver (R12): restore the state from its ref when it is
    missing or older, renew the drive lease (pushed), collect, plan and act with the host
    driver's own policy (R13), run every forge action itself, and write the session
    requests to --outbox for the agent to execute. A wake within --interval of the last
    pass only renews the lease.

    Exit codes: 0 acted or everything is done; 3 nothing to do but wait, or a wake that
    only renewed the lease; 2 a refusal (another driver's lease included); 1 a forge
    write failed."""
    from fr.commands import triage_batch_cmd as batch
    from fr.commands.triage_kanban_cmd import try_load
    from fr.triage.driver import CLOUD, CLOUD_RUNNER, Mailbox

    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace, sync=False)
    try:  # 1. restore: the brief's state repo finds the ref before any local state exists
        triage_cmd.fetch_now(scope, target, state_repo=state_repo)
    except TriageError as exc:
        _fail(str(exc))
    target = resolve_state_dir(scope, dir_override, workspace)  # and push when it ends
    identity = identity_for("cloud")
    duration = lease_duration(interval, routine)
    now, sid = _now(), scope_id(scope)
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    recent = (
        current is not None
        and current.holder == holder_of(sid, identity)
        and current.last_pass is not None
        and now - current.last_pass < timedelta(minutes=interval)
    )
    if recent:  # a wake within the interval of the last pass: renew, nothing else
        assert current is not None and current.last_pass is not None
        try:
            acquire(target, identity, now, scope_id=sid, duration=duration,
                    push=lambda: triage_cmd.push_now(scope, target))  # fmt: skip
        except TriageError as exc:
            _fail(str(exc))
        _write_outbox(outbox, [])
        console.print(
            f"renewed the drive lease; the last pass ran at {current.last_pass.isoformat()}, "
            f"within the {interval:g}-minute interval",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(code=3)
    driver = batch.build_driver(
        scope,
        target,
        batch_ids=None,
        checkout=None,
        max_inflight=max_inflight,
        yes=True,
        scope_args=["--repo", repo] if repo else ["--org", org] if org else [],
        adapter=CLOUD,
        statuses=_read_json(statuses, "statuses"),
        lease=batch.LeaseTerms(identity, duration),
    )
    # The cloud runner is opened before the pass, so a request still pending from an
    # earlier pass is re-emitted even when this pass asks nothing new of it (§F).
    runner, reason = try_load(CLOUD_RUNNER, driver.runner)
    if runner is None or not isinstance(runner, Mailbox):
        err_console.print(
            f"[yellow]warning:[/yellow] runner `{CLOUD_RUNNER}` "
            + (
                f"could not be loaded ({escape(reason or 'no reason given')})"
                if runner is None
                else "keeps no mailbox"
            )  # fmt: skip
            + "; no session requests can be written",
            soft_wrap=True,
        )
    try:  # drive.lock: the fast same-host check, before the lease (§D)
        with batch.drive_lock(triage_cmd.drive_lock_dir(scope, dir_override)):
            acted, summary, _ = batch.one_pass(driver)
    except batch.ForgeReadError as exc:
        _fail(str(exc), code=exc.code)
    _write_outbox(outbox, driver.outbox())
    code = batch.pass_exit(driver, acted, summary)
    if code:
        raise typer.Exit(code=code)


@drive_app.command("record")
def drive_record_command(
    outbox: OutboxOpt,
    result: Annotated[
        Path, typer.Option("--result", help="The agent's results, one per request (JSON).")
    ],
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Apply every result the agent recorded for the outbox's requests to the scope's
    state (through the cloud runner's mailbox), empty the outbox, and push the state ref.
    Only the lease's holder records. Exit 2 on a refusal: a lease another driver holds, a
    result no pending request names, or a runner that keeps no mailbox."""
    from fr.commands import triage_batch_cmd as batch
    from fr.triage.driver import CLOUD_RUNNER, Mailbox

    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    holder = holder_of(scope_id(scope), identity_for("cloud"))
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    if current is not None and current.holder != holder:
        _fail(
            f"the drive lease is held by {current.holder} (expires "
            f"{current.expires.isoformat()}), not this driver ({holder}): nothing recorded"
        )
    results = _read_json(result, "results")
    if isinstance(results, dict):
        results = results.get("results")
    if not isinstance(results, list) or not all(isinstance(r, dict) for r in results):
        _fail(f"{result}: a list of results, one object per request")
    if results:
        runner = batch.load_runner(CLOUD_RUNNER)
        if not isinstance(runner, Mailbox):
            _fail(f"runner `{CLOUD_RUNNER}` keeps no mailbox: nothing to record into")
        runner.open_mailbox(target, None)
        try:
            applied = set(runner.record_results(results))
        except TriageError as exc:
            _fail(str(exc))
        unknown = [str(r.get("id")) for r in results if r.get("id") not in applied]
        if unknown:
            _fail(f"no pending request is named {', '.join(unknown)}; the rest were recorded")
    _write_outbox(outbox, [])
    console.print(f"recorded {len(results)} result(s)", markup=False)
