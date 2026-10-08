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
but wait, or a wake within half an interval of the last pass, which only renews the
lease; 2 a refusal (a lease held by another driver, a push conflict, a cloud runner that
cannot be loaded or keeps no mailbox); 1 a forge write failed.
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


def latest_fr_release() -> str | None:
    """The latest fr release's tag, through the forge client's releases route (R17, R18);
    None, with a warning, when it cannot be read: drift is then not checked this pass."""
    from fr.commands import triage_batch_cmd as batch
    from fr.triage.drift import FR_RELEASE_REPO

    try:
        client = batch.make_client(f"https://github.com/{FR_RELEASE_REPO}")
        return client.latest_release(FR_RELEASE_REPO)
    except Exception as exc:  # noqa: BLE001 - drift is upkeep; the pass goes on without it
        err_console.print(
            f"[yellow]warning:[/yellow] the latest fr release could not be read "
            f"({escape(str(exc) or type(exc).__name__)}); version drift is not checked "
            "this pass",
            soft_wrap=True,
        )
        return None


def _installed_version() -> str:
    """The fr running this pass; tests replace it."""
    from fr import __version__

    return __version__


def _install_release(release: str, *, remote: str | None = None) -> None:
    """Install fr *release* the way the cloud setup does (spec §H): a super-fr source
    clone on a clean `main` at origin/main, which must contain the release's tag, then
    its `scripts/install.sh` with its normal preflight. The clone lives under
    `~/.cache/fr/src/super-fr`, never in the marketplace directory, which install.sh
    replaces (dropping its `.git`), so a second reinstall finds the clone it left (p6-r1).
    *remote* defaults to the release repo. Raises `RuntimeError` naming the failed step
    and its stderr; tests replace it."""
    import subprocess
    from pathlib import Path as _Path

    from fr.triage.drift import FR_RELEASE_REPO

    url = remote or f"https://github.com/{FR_RELEASE_REPO}.git"
    clone = _Path.home() / ".cache" / "fr" / "src" / "super-fr"

    def run(*argv: str) -> None:
        try:
            subprocess.run(argv, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            said = " ".join((exc.stderr or exc.stdout or "").split())
            raise RuntimeError(
                f"`{' '.join(argv[:3])}` exited {exc.returncode}: {said or 'no output'}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"`{argv[0]}` could not run: {exc}") from exc

    if not (clone / ".git").is_dir():
        if clone.exists():
            import shutil

            shutil.rmtree(clone)  # a half-made clone from an interrupted install
        clone.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--quiet", url, str(clone))
    git = ("git", "-C", str(clone))
    run(*git, "remote", "set-url", "origin", url)
    run(*git, "fetch", "--quiet", "--force", "--tags", "origin", "main")
    # install.sh's preflight installs only a clean `main` in sync with origin/main
    # (p7-r1), so the release is installed from there, never from a detached tag:
    # refuse a tag main does not contain rather than install something else.
    try:
        on_main = subprocess.run(
            [*git, "merge-base", "--is-ancestor", f"refs/tags/{release}", "origin/main"],
            capture_output=True, text=True,
        )  # fmt: skip
    except OSError as exc:
        raise RuntimeError(f"`git` could not run: {exc}") from exc
    if on_main.returncode != 0:
        said = " ".join((on_main.stderr or "").split())
        raise RuntimeError(
            f"release tag {release} is not on origin/main of {url}; refusing to install "
            f"it (install.sh installs only main){': ' + said if said else ''}"
        )
    run(*git, "checkout", "--quiet", "--force", "-B", "main", "origin/main")
    run(*git, "clean", "-fdxq")
    run("bash", str(clone / "scripts" / "install.sh"))


def _reexec(release: str) -> None:
    """Run this same pass again on the fr just installed (first `fr` on PATH), marked so
    it never reinstalls the same release twice. Never returns; tests replace it."""
    import os
    import sys

    from fr.triage.drift import REEXEC_ENV

    os.environ[REEXEC_ENV] = release
    sys.stdout.flush()
    os.execvp("fr", ["fr", *sys.argv[1:]])


def _self_update(
    scope: Any,
    target: Path,
    release: str | None,
    *,
    scope_args: list[str],
    state_repo: str | None,
    generation: int,
) -> tuple[dict[str, Any] | None, bool]:
    """§E step 2 (R18): `(the self-re-home request, None to go on; re-execute?)`. The
    driver session's start version is recorded on its first pass that knows the release.
    A re-home moves the lease to the next generation and records the request in the
    ledger, both pushed in one compare-and-swap before the request is emitted (p6-r4); a
    pending request is re-emitted as it is, never made twice, and a session of its
    generation or later takes it as done (its record was lost, but it exists)."""
    import os

    from fr.triage import drift
    from fr.triage.lease import LEASE_FILE, bump_generation
    from fr.triage.scope_config import load_durable

    if release is None:
        return None, False
    installed = _installed_version()
    try:
        ledger = drift.load_ledger(target)
    except TriageError as exc:
        _fail(str(exc))
    adopted = drift.adopt_pending(ledger, generation)
    if adopted is not None:
        drift.save_ledger(target, adopted)
        console.print(
            f"this driver session (generation {generation}) is the re-home onto fr "
            f"{ledger.driver['pending'].get('release')}: recorded as done",
            markup=False,
            soft_wrap=True,
        )
        ledger = adopted
    plan = drift.plan_self_update(installed, release, ledger)
    if plan.action == "rehome":
        pending = ledger.driver.get("pending")
        if isinstance(pending, dict):  # re-emitted as it is: one session per re-home
            return {"request_tag": pending.get("id"), **pending}, False
        saved = {
            name: (target / name).read_bytes() if (target / name).exists() else None
            for name in (LEASE_FILE, drift.REHOMES_FILE)
        }
        try:
            new_generation = bump_generation(target).generation
            repo_of_state = state_repo or load_durable(target).state_repo
            brief = drift.driver_brief(
                scope_args=scope_args, state_repo=repo_of_state, host_id=host_id(),
                release=release, generation=new_generation,
            )  # fmt: skip
            pending = drift.driver_request(release, brief, generation=new_generation)
            drift.save_ledger(target, ledger.with_driver(start=plan.start, pending=pending))
            triage_cmd.push_now(scope, target)
        except TriageError as exc:  # nothing emitted: put the lease and ledger back
            for name, body in saved.items():
                if body is None:
                    (target / name).unlink(missing_ok=True)
                else:
                    (target / name).write_bytes(body)
            _fail(str(exc))
        return pending, False
    if "start" not in ledger.driver:
        drift.save_ledger(target, ledger.with_driver(start=plan.start))
    if plan.action != "reinstall":
        return None, False
    if os.environ.get(drift.REEXEC_ENV) == release:
        err_console.print(
            f"[yellow]warning:[/yellow] reinstalled fr {escape(release)}, but this pass still "
            f"runs on {escape(installed)}; running it on {escape(installed)}",
            soft_wrap=True,
        )
        return None, False
    try:
        _install_release(release)
    except Exception as exc:  # noqa: BLE001 - the pass still runs, on the installed fr
        err_console.print(
            f"[yellow]warning:[/yellow] installing fr {escape(release)} failed "
            f"({escape(str(exc) or type(exc).__name__)}); this pass runs on {escape(installed)}",
            soft_wrap=True,
        )
        return None, False
    console.print(f"installed fr {release}; running the pass on it", markup=False)
    return None, True


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
GenerationOpt = Annotated[
    int,
    typer.Option(
        "--generation",
        min=0,
        help="This driver session's lease generation, from its brief (a self-re-homed "
        "session's; 0 otherwise). A session older than the lease's stops (§D).",
    ),
]


def _superseded_by(target: Path, holder: str, generation: int) -> int | None:
    """The lease's generation when this driver session (*holder*, *generation*) is
    superseded by a newer one (p6-r4), else None."""
    from fr.triage import drift

    try:
        current = load_lease(target)
        if current is None or current.holder != holder:
            return None
        ledger = drift.load_ledger(target)
    except TriageError as exc:
        _fail(str(exc))
    return current.generation if drift.superseded(current.generation, generation, ledger) else None


def _stop_superseded(outbox: Path | None, newer: int, generation: int, what: str) -> NoReturn:
    """A superseded session stops: exit 0, nothing driven or recorded, no further wake."""
    if outbox is not None:
        _write_outbox(outbox, [])
    console.print(
        f"superseded by generation {newer}: this driver session (generation {generation}) "
        f"stops; {what}. Schedule no further wake.",
        markup=False,
        soft_wrap=True,
    )
    raise typer.Exit(code=0)


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
    generation: GenerationOpt = 0,
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
    requests to --outbox for the agent to execute. A wake within half of --interval of the
    last pass only renews the lease (p4-r2: `send_later` truncates to the minute).

    A session whose --generation is older than the lease's (another session replaced it
    by a self-re-home) drives nothing and exits 0 (p6-r4).

    Exit codes: 0 acted, everything is done, or superseded; 3 nothing to do but wait, or a
    wake that only renewed the lease; 2 a refusal (another driver's lease included); 1 a
    forge write failed."""
    from fr.commands import triage_batch_cmd as batch
    from fr.commands.triage_kanban_cmd import scope_args, try_load
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
    newer = _superseded_by(target, holder_of(sid, identity), generation)
    if newer is not None:
        _stop_superseded(outbox, newer, generation, "it drove nothing")
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    recent = (
        current is not None
        and current.holder == holder_of(sid, identity)
        and current.last_pass is not None
        and now - current.last_pass < timedelta(minutes=interval) / 2
    )
    if recent:  # a wake within half an interval of the last pass: renew, nothing else (p4-r2)
        assert current is not None and current.last_pass is not None
        try:
            acquire(target, identity, now, scope_id=sid, duration=duration,
                    generation=generation,
                    push=lambda: triage_cmd.push_now(scope, target))  # fmt: skip
        except TriageError as exc:
            _fail(str(exc))
        _write_outbox(outbox, [])
        console.print(
            f"renewed the drive lease; the last pass ran at {current.last_pass.isoformat()}, "
            f"within half the {interval:g}-minute interval",
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
        scope_args=scope_args(repo, org, dir_override, workspace),  # p4-r9
        adapter=CLOUD,
        statuses=_read_json(statuses, "statuses"),
        lease=batch.LeaseTerms(identity, duration, generation),
    )
    # The cloud runner is opened before the pass, so a request still pending from an
    # earlier pass is re-emitted even when this pass asks nothing new of it (§F).
    # A pass that could write no session request refuses before it acts (p4-r6).
    runner, reason = try_load(CLOUD_RUNNER, driver.runner)
    if runner is None:
        _fail(f"runner `{CLOUD_RUNNER}` could not be loaded ({reason}); nothing done")
    if not isinstance(runner, Mailbox):
        _fail(f"runner `{CLOUD_RUNNER}` keeps no mailbox, so no session request could be "
              "written; nothing done")  # fmt: skip
    driver.fr_release = latest_fr_release()  # R17: what each run's major is held to
    stop: dict[str, Any] | None = None  # the self-re-home request that ends this pass
    reexec = False
    newer = None
    try:  # drive.lock: the fast same-host check, before the lease (§D)
        with batch.drive_lock(triage_cmd.drive_lock_dir(scope, dir_override)):
            driver.take_lease()  # §E step 1, before the self-update (step 2)
            # the lease just fetched may name a session that replaced this one meanwhile
            newer = _superseded_by(target, holder_of(sid, identity), generation)
            if newer is None:
                stop, reexec = _self_update(
                    scope, target, driver.fr_release,
                    scope_args=scope_args(repo, org, dir_override, workspace),
                    state_repo=state_repo, generation=generation,
                )  # fmt: skip
            if newer is None and stop is None and not reexec:
                acted, summary, _ = batch.one_pass(driver, lease_taken=True)
    except batch.ForgeReadError as exc:
        _fail(str(exc), code=exc.code)
    if newer is not None:
        _stop_superseded(outbox, newer, generation, "it drove nothing")
    if reexec:  # outside drive.lock: the new process takes it again under this pid
        assert driver.fr_release is not None
        _reexec(driver.fr_release)
    if stop is not None:  # the pending worker requests too, as every pass (p6-r5); stop last
        _write_outbox(outbox, [*driver.outbox(), stop])
        console.print(
            f"re-homing this driver onto fr {stop['release']}: its session started on another "
            "major; execute the outbox (the re-home last), record it, and stop this session",
            markup=False,
            soft_wrap=True,
        )
        return
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
    generation: GenerationOpt = 0,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Apply every result the agent recorded for the outbox's requests to the scope's
    state (through the cloud runner's mailbox), empty the outbox, and push the state ref.
    Only the current, unexpired holder of the scope's lease records, under the same-host
    `drive.lock` (p4-r5). A session whose --generation is older than the lease's records
    nothing and exits 0 (p6-r4), except the one whose own self-re-home moved it, which
    records that pass's results. Exit 2 on a refusal: no live lease of this driver's, a
    driver holding the lock, a result no pending request names, or a runner that keeps no
    mailbox."""
    from fr.commands import triage_batch_cmd as batch

    scope = triage_cmd._scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    holder = holder_of(scope_id(scope), identity_for("cloud"))
    try:
        current = load_lease(target)
    except TriageError as exc:
        _fail(str(exc))
    if current is None:
        _fail(f"no drive lease is held for this scope, so this driver ({holder}) does not "
              "hold it: nothing recorded; run `fr triage drive pass` first")  # fmt: skip
    if current.holder != holder:
        _fail(
            f"the drive lease is held by {current.holder} (expires "
            f"{current.expires.isoformat()}), not this driver ({holder}): nothing recorded"
        )
    if current.expired(_now()):
        _fail(f"this driver's drive lease expired at {current.expires.isoformat()}: nothing "
              "recorded; run `fr triage drive pass` to renew it first")  # fmt: skip
    with batch.drive_lock(triage_cmd.drive_lock_dir(scope, dir_override)):  # §D, p4-r5
        newer = _superseded_by(target, holder, generation)
        if newer is not None:
            _stop_superseded(None, newer, generation, "nothing recorded")
        _record(target, outbox, result)


def _record(target: Path, outbox: Path, result: Path) -> None:
    from fr.commands import triage_batch_cmd as batch
    from fr.triage.driver import CLOUD_RUNNER, Mailbox

    results = _read_json(result, "results")
    if isinstance(results, dict):
        results = results.get("results")
    if not isinstance(results, list) or not all(isinstance(r, dict) for r in results):
        _fail(f"{result}: a list of results, one object per request")
    from fr.triage import drift

    mine = [r for r in results if str(r.get("id", "")).startswith(drift.DRIVER_REQUEST_PREFIX)]
    if mine:  # the driver's own re-home (R18): the ledger's, not the runner's mailbox
        try:
            ledger = drift.load_ledger(target)
            for r in mine:
                ledger = drift.record_driver_result(ledger, r)
        except TriageError as exc:
            _fail(str(exc))
        drift.save_ledger(target, ledger)
        results = [r for r in results if r not in mine]
    if results:
        runner = batch.load_runner(CLOUD_RUNNER)
        if not isinstance(runner, Mailbox):
            _fail(f"runner `{CLOUD_RUNNER}` keeps no mailbox: nothing to record into")
        runner.open_mailbox(target, None)
        try:
            applied = set(runner.record_results(results))
        except (TriageError, ValueError) as exc:  # the runner's own refusal of a result
            _fail(str(exc))
        unknown = [str(r.get("id")) for r in results if r.get("id") not in applied]
        if unknown:
            _fail(f"no pending request is named {', '.join(unknown)}; the rest were recorded")
    _write_outbox(outbox, [])
    console.print(f"recorded {len(results) + len(mine)} result(s)", markup=False)
