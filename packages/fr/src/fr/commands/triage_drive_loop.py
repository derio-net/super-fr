"""The looping `fr triage batch drive`: its pass boundary, its waits and its supervision
(spec 2026-11-19-batch-train-truth).

`_host_loop` runs `one_pass` until the work is done, stalled or refused. Its whole
iteration sits inside ONE boundary (R1): a failure is classified, recorded in the scope's
ledger and on `driver.yaml`, and either ends only the pass, the next one after `backoff`,
or stops the driver (a refusal, or `MAX_FAILED_PASSES` in a row). Its waits keep the lease
alive (`wait_out`, R16) and, under `--supervise`, watch the supervisor (`_wait`, R12).
`_supervise` runs the driver as a child of this process, and `_run_driver` the built
driver under `drive.lock` and its activity log (`_log`, `_emit`, `_say`).

Everything here prints through the command layer's consoles and `_fail`, so it lives
beside `triage_batch_cmd`, which re-exports the names its driver and the tests use. It
never imports that module at load time (it imports this one): each function reads it at
call time, so a test that patches `triage_batch_cmd._now`, `_sleep`, `one_pass`,
`load_lease`, `console`, `_SUPERVISOR`, `drive_lock`, `_host_loop`, `_driver_started` or `_exec`
patches this module's view of it too. Like the driver's pass, nothing here may call
`_fail` or raise `typer.Exit` inside the loop (`tests/unit/test_tripwire_drive_pass_boundary.py`).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from rich.markup import escape

from fr import __version__
from fr.triage.batch_drive import DEFAULT_WORKSPACE_PREFIX
from fr.triage.drive_errors import DriverRefusal, TransientPassFailure, classify, unexpected
from fr.triage.drive_log import TRACEBACK_FILE, DriveLog, append_traceback
from fr.triage.driver_record import (
    FAILURES_COMMAND,
    FailureKind,
    record_failure,
    record_pass,
    record_refusal,
    record_start,
)
from fr.triage.errors import TriageError
from fr.triage.model import Scope
from fr.triage.quota import Pace
from fr.triage.scope_config import load_durable

if TYPE_CHECKING:
    from fr.commands.triage_batch_cmd import LeaseTerms, _Driver
    from fr.triage.pacing import Pacer


_DRIVE_LOG: DriveLog | None = None
"""The activity log a looping driver (loop mode with `--yes`) is attached to, else None:
plan mode and `--once` attach none, so their output is unchanged (batch-train-truth R22)."""


@contextmanager
def drive_log_attached(log: DriveLog | None) -> Iterator[None]:
    """Attach *log* for the block: every `_emit` is then appended to it too."""
    global _DRIVE_LOG
    previous, _DRIVE_LOG = _DRIVE_LOG, log
    try:
        yield
    finally:
        _DRIVE_LOG = previous


def _log(kind: str, line: str) -> None:
    """Append *line* to the attached drive log; the log is a view, so a failed write is
    never a reason to stop the driver."""
    from fr.commands import triage_batch_cmd as batch

    if _DRIVE_LOG is None:
        return
    try:
        _DRIVE_LOG.append(kind, line, batch._now())
    except OSError:
        pass


def _emit(kind: str, line: str) -> None:
    """Print *line* and, while a drive log is attached, append it as a *kind* entry."""
    from fr.commands import triage_batch_cmd as batch

    batch.console.print(line, markup=False, soft_wrap=True, highlight=False)
    _log(kind, line)


def _say(line: str) -> None:
    _emit("action", line)


def _report_read_failure(driver: _Driver, message: str, action: str) -> None:
    """A forge read failure, reported once per cause until a pass reads cleanly (gh#910)."""
    if message not in driver.read_failures:
        driver.read_failures.add(message)
        err_console.print(f"[yellow]warning:[/yellow] {escape(message)}; {action}", soft_wrap=True)
        _log("transient", f"{message}; {action}")


def _stalled_line(blocked: Sequence[str], held_by: Sequence[tuple[str, Sequence[str]]]) -> str:
    """Why an idle loop stops: batches held by another scope wait on that scope (R6) and
    are named apart from those that need the operator (R7)."""
    if not held_by:
        return (
            f"stopped: only blocked batches remain ({', '.join(blocked)}); they need the operator"
        )
    held = ", ".join(f"{b} ({', '.join(who)})" for b, who in held_by)
    parts = [f"held by another scope: {held}"]
    if blocked:
        parts.append(f"need the operator: {', '.join(blocked)}")
    return "stopped: only held or blocked batches remain; " + "; ".join(parts)


SUPERVISED_POLL_S = 1.0  # a supervised driver's waits are cut to this, to look at its parent


class SupervisorGone(BaseException):  # noqa: N818 - carried past the loop's boundary untouched
    """The supervisor is no longer this driver's parent: stop cleanly (R12). Not an
    `Exception`, so no pass boundary mistakes it for a failure."""


def _check_supervisor() -> None:
    from fr.commands import triage_batch_cmd as batch

    if batch._SUPERVISOR is not None and os.getppid() != batch._SUPERVISOR:
        raise SupervisorGone


class _WaitEnded(BaseException):
    """An exception out of a wait (`_sleep`), carried past the loop's boundary untouched:
    a wait is never a pass failure. A real sleep raises nothing but an interrupt; this is
    how a test's sleep hook ends the loop (batch-train-truth R1)."""

    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original


def _wait(seconds: float) -> None:
    """The loop's every wait: `_sleep`, its exceptions carried as `_WaitEnded`."""
    from fr.commands import triage_batch_cmd as batch

    try:
        if batch._SUPERVISOR is None:
            batch._sleep(seconds)
        else:  # a supervised driver wakes every second to see that its supervisor still runs
            left = seconds
            while left > 0:
                _check_supervisor()
                chunk = min(left, SUPERVISED_POLL_S)
                batch._sleep(chunk)
                left -= chunk
            _check_supervisor()
    except Exception as exc:  # noqa: BLE001 - re-raised as itself past the boundary
        raise _WaitEnded(exc) from exc


# A wait that outlives the lease renews it this long before it would lapse (R16).
LEASE_MARGIN = timedelta(minutes=5)
RENEW_RETRY_S = 60


def wait_out(driver: _Driver, pace: Pace) -> None:
    """Sleep until *pace* is over without ever letting the drive's lease lapse (R16): a
    wait that reaches the lease's expiry minus five minutes wakes, renews the lease (the
    state push and its visibility read, the one call a wait makes), and sleeps again."""
    from fr.commands import triage_batch_cmd as batch

    assert pace.until is not None
    left = max(0.0, (pace.until - batch._now()).total_seconds())
    while left > 0:
        held = batch.load_lease(driver.target) if driver.leased else None
        room = (held.expires - LEASE_MARGIN - batch._now()).total_seconds() if held else None
        if room is not None and room <= 0:
            try:
                driver.take_lease()
                continue
            except batch.ForgeReadError as exc:  # unreadable visibility: try again a minute on
                _report_read_failure(driver, str(exc), f"renewal retried every {RENEW_RETRY_S}s")
                room = RENEW_RETRY_S
        chunk = left if room is None else min(left, room)
        _wait(chunk)
        left -= chunk


def _host_lease(scope: Scope, target: Path, interval_s: int) -> LeaseTerms | None:
    """The host driver's lease (R9), when the scope has a state ref to hold it on: a scope
    with no state repo has only this host's `drive.lock`. One with a state repo whose state
    sits in no clone cannot sync the ref, so it refuses (exit 2) naming --workspace rather
    than drive unleased beside a cloud driver (cloud-triage §E, p4-r3)."""
    from fr.commands import triage_batch_cmd as batch
    from fr.commands.triage_cmd import state_clone
    from fr.triage.lease import DEFAULT_ROUTINE_MIN, driver_identity, lease_duration
    from fr.triage.scope_config import host_id

    try:
        state_repo = load_durable(target).state_repo
        if state_repo is None:
            return None
        if state_clone(target) is None:
            _fail(
                f"{target} is in no git clone, so this driver cannot sync the state ref in "
                f"{state_repo} nor hold the scope's drive lease, and will not drive unleased "
                "beside another driver: run from a clone, or pass --workspace <clone>"
            )
        identity = driver_identity("host", host_id())
    except TriageError as exc:
        _fail(str(exc))
    return batch.LeaseTerms(identity, lease_duration(interval_s / 60, DEFAULT_ROUTINE_MIN))


@contextmanager
def _sigterm_interrupts() -> Iterator[None]:
    """SIGTERM raises `KeyboardInterrupt` for the block's duration, so a terminated driver
    stops as a Ctrl-C does and releases its lease (cloud-triage §E, p4-r4); the previous
    handler is restored after. Off the main thread no handler can be installed: a no-op."""
    import signal
    import threading

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@dataclass(frozen=True)
class LoopEnd:
    """How `_host_loop` ended (batch-train-truth R7): the exit code, and the newer fr a
    `post_merge` installed when it stopped to restart on it (gh#998)."""

    code: int = 0
    restart_to: str | None = None


MAX_FAILED_PASSES = 10  # consecutive failed passes before the loop stops as a refusal (R5)
BACKOFF_CAP_S = 900  # the longest backoff, unless --interval is longer (R3)


def backoff(interval: int, failed: int) -> int:
    """The wait after the *failed*-th failed pass in a row: --interval, doubling, capped at
    15 minutes or --interval when that is longer (R3)."""
    return int(min(interval * 2 ** (failed - 1), max(BACKOFF_CAP_S, interval)))


def _host_loop(
    driver: _Driver, *, once: bool, interval: int, pacer: Pacer | None = None
) -> LoopEnd:
    """`fr triage batch drive`'s loop around `one_pass` (the host adapter, R10), ended by a
    returned `LoopEnd`, never an exit (batch-train-truth R7).
    With a *pacer*, a looping drive reads the budget before each pass, waits out an
    exhausted one, and backs off a rate limit instead of retrying it (R2-R4)."""
    try:
        return _loop(driver, once=once, interval=interval, pacer=pacer)
    except _WaitEnded as ended:
        raise ended.original from None
    except SupervisorGone:  # a clean stop: the caller releases the lease (R12)
        _emit("stop", "the supervisor is no longer this driver's parent: stopping")
        return LoopEnd(0)


def _loop(driver: _Driver, *, once: bool, interval: int, pacer: Pacer | None) -> LoopEnd:
    """The loop proper. Its whole iteration (pacing wait, `wait_out`, lease renewal and
    `one_pass`) runs inside ONE boundary (batch-train-truth R1): a failure there is
    classified (`fr.triage.drive_errors.classify`), recorded and reported once per cause,
    and either stops the loop (a refusal, or the tenth failed pass in a row) or ends only
    the pass, the next one starting after `backoff`."""
    from fr.commands import triage_batch_cmd as batch

    paced = pacer if pacer is not None and driver.yes and not once else None
    driver.pacer = paced
    pace: Pace | None = None
    failed = 0  # failed passes in a row (R3, R5)
    while True:
        _check_supervisor()  # between passes (R12)
        try:
            if paced is not None:
                pace = paced.before_pass()
                if pace.kind == "wait":
                    _say(paced.line(pace))
                    wait_out(driver, pace)
                    continue
                driver.pace = pace
                if pace.essential:  # below the floor: the essential-only pass (R7, R13)
                    _say(paced.line(pace))
                    paced.stretch(pace.until)
            try:
                acted, summary, blocked = batch.one_pass(driver)
            except batch.ForgeReadError as exc:
                if paced is not None and paced.limited(str(exc)):  # loop mode, with --yes
                    pace = paced.rate_limited()  # a rate limit keeps its own budget wait (R3)
                    _say(paced.line(pace))
                    if driver.restart_to is not None:
                        return LoopEnd(0, driver.restart_to)
                    wait_out(driver, pace)
                    continue
                # Like a refused merge (rg-4), a degraded forge ends neither the run nor
                # the loop (gh#910): the R3 transient `forge-read`, through the boundary.
                raise TransientPassFailure("forge-read", str(exc), code=exc.code,
                                           original=exc) from exc  # fmt: skip
            failed = 0
            driver.read_failures.clear()
            if driver.yes and not once:
                _driver_pass(driver)
            if paced is not None and driver.failed_write and paced.limited():
                # a failed write with the budget gone is the limit, not a clean pass (p1-r2)
                pace = paced.rate_limited()
                _say(paced.line(pace))
                if driver.restart_to is not None:
                    return LoopEnd(0, driver.restart_to)
                wait_out(driver, pace)
                continue
            if paced is not None:
                paced.clean()
            if not driver.yes:
                return LoopEnd(0)  # the plan of one pass, in loop mode too
            if once:
                driver.warn_single_pass()
                return LoopEnd(batch.pass_exit(driver, acted, summary))
            if summary.done:
                if driver.observation_owed():
                    continue  # the last wave's transition is seen only by one more pass
                return LoopEnd(0)
            if driver.restart_to is not None:
                return LoopEnd(0, driver.restart_to)
            if summary.stalled:
                _emit("stop", _stalled_line(blocked, driver.held_by))
                return LoopEnd(3)
            if pace is not None and pace.essential and pace.until is not None:
                wait_out(driver, Pace("wait", pace.until, "below floor"))  # 4x, lease-safe (R16)
                continue
            _wait(interval)
        except Exception as exc:  # noqa: BLE001 - THE boundary: every failure is classified
            failure = classify(exc)
            if once or not driver.yes:  # R6: today's exit code, from the carried code
                if driver.yes:
                    _ledger_failure(driver, failure)
                if unexpected(failure) is not None:
                    raise  # an fr bug: its traceback and exit 1, as before the boundary
                if failure.message and not failure.said:
                    _error(failure.message)
                return LoopEnd(failure.code)
            failed += 1
            if isinstance(failure, TransientPassFailure) and failed >= MAX_FAILED_PASSES:
                stop = DriverRefusal(
                    failure.cause,
                    f"{MAX_FAILED_PASSES} passes in a row failed, the last with: "
                    f"{failure.message or failure.cause}",
                )
                _stop(driver, stop, ledgered=failure)  # the cause stays transient (p1a-r10)
                return LoopEnd(stop.code)
            if isinstance(failure, DriverRefusal):
                _stop(driver, failure)
                return LoopEnd(failure.code)
            _ledger_failure(driver, failure)
            wait = backoff(interval, failed)
            kept = keep_traceback(driver.target, failure)
            if failure.cause not in driver.read_failures:
                driver.read_failures.add(failure.cause)
                shown = failure.message and not failure.said
                said = f"{escape(failure.message)} " if shown else ""
                where = f"; its traceback: {escape(str(kept))}" if kept is not None else ""
                err_console.print(
                    f"[yellow]warning:[/yellow] {said}({failure.cause}); the pass ended, "
                    f"its state kept; the next pass in {wait}s{where}",
                    soft_wrap=True,
                )
                _log("transient", f"{failure.message} ({failure.cause}); the pass ended, "
                     f"the next pass in {wait}s{where}")  # fmt: skip
            if driver.restart_to is not None:
                return LoopEnd(0, driver.restart_to)
            _wait(wait)


def _error(message: str) -> None:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    _log("refusal", message)


_TRACEBACKS_KEPT: set[tuple[Path, str]] = set()
"""The (state directory, cause) pairs whose traceback this process already kept."""


def keep_traceback(target: Path, failure: DriverRefusal | TransientPassFailure) -> Path | None:
    """An unexpected failure's traceback, appended to `drive-tracebacks.log` in *target* once
    per cause per process (a looping driver, and the cloud pass, have no other trace of an fr
    bug); the file's path, else None. Like the log, it is never a reason to fail."""
    from fr.commands import triage_batch_cmd as batch

    original = unexpected(failure)
    if original is None:
        return None
    path = target / TRACEBACK_FILE
    if (target, failure.cause) not in _TRACEBACKS_KEPT:
        try:
            path = append_traceback(target, failure.cause, original, batch._now())
        except OSError:
            return None
        _TRACEBACKS_KEPT.add((target, failure.cause))
    return path


def _ledger(driver: _Driver, kind: FailureKind, cause: str, message: str, exc: str) -> None:
    """Count one failure in the scope's ledger (R9). The ledger is a record, never a reason
    to fail: a write that fails is one warning."""
    from fr.commands import triage_batch_cmd as batch

    try:
        record_failure(
            driver.target, kind, cause, message, batch._now(), __version__, exception=exc
        )
    except (OSError, TriageError) as err:
        _report_read_failure(driver, f"the driver failure ledger: {err}", "not recorded")


def _ledger_failure(driver: _Driver, failure: DriverRefusal | TransientPassFailure) -> None:
    kind: FailureKind = "refusal" if isinstance(failure, DriverRefusal) else "transient"
    original = failure.original if isinstance(failure, TransientPassFailure) else None
    exc = type(original if original is not None else failure).__name__
    _ledger(driver, kind, failure.cause, failure.message, exc)


def _driver_started(driver: _Driver, supervisor: int | None) -> None:
    """A looping driver's start, on `driver.yaml` (R12, R14)."""
    from fr.commands import triage_batch_cmd as batch

    try:
        record_start(driver.target, batch._now(), supervisor)
    except (OSError, TriageError) as err:
        _report_read_failure(driver, f"the driver record: {err}", "not recorded")


def _supervise(
    args: list[str],
    target: Path,
    scope: Scope | None = None,
    scope_args: Sequence[str] = (),
    workspace_prefix: str = DEFAULT_WORKSPACE_PREFIX,
) -> NoReturn:
    """`drive --supervise --yes` (R11-R13): run the driver as this process's child, with
    *args* (the same arguments less `--supervise`) and `--supervised-by <our pid>`. It takes
    neither `drive.lock` nor the lease: the child does. After a crash loop it renders the
    board once from what is on disk (R8), so the driver-stopped need shows."""
    import shlex

    from fr.safe_spawn import fr_argv
    from fr.triage.supervise import Supervisor

    def render_board() -> None:
        if scope is None:
            return
        # The child that held drive.lock has stopped: the supervisor renders in its place,
        # so it is the dwell ledger's one writer (board-session-state R5).
        out, _ = triage_kanban_cmd.write_board(
            scope, target, scope_args=scope_args, prefix=workspace_prefix, writer=True
        )
        triage_kanban_cmd.publish(scope, target, out, set())

    code = Supervisor(
        lambda pid: fr_argv(*args, "--supervised-by", str(pid)),
        target,
        fr_version=__version__,
        resume="fr " + shlex.join([*args, "--supervise"]),
        on_refusal=render_board,
    ).run()
    raise typer.Exit(code=code)


def _driver_pass(driver: _Driver) -> None:
    """A looping driver's clean pass, on `driver.yaml` (R8, R14)."""
    from fr.commands import triage_batch_cmd as batch

    try:
        record_pass(driver.target, batch._now())
    except (OSError, TriageError) as err:
        _report_read_failure(driver, f"the driver record: {err}", "not recorded")


def _stop(
    driver: _Driver, refusal: DriverRefusal, *, ledgered: TransientPassFailure | None = None
) -> None:
    """A refusal ends the looping driver (R8): recorded on `driver.yaml` and in the ledger,
    the board rendered once to show it, and the stop said with how to resume and file it.
    The tenth transient failure in a row (R5) stops as a refusal, but its cause is counted
    in the ledger as what it was, *ledgered* (p1a-r10)."""
    from fr.commands import triage_batch_cmd as batch

    _ledger_failure(driver, ledgered if ledgered is not None else refusal)
    try:
        record_refusal(driver.target, refusal.cause, refusal.message, refusal.resume, batch._now(),
                       __version__)  # fmt: skip
    except (OSError, TriageError) as err:
        _report_read_failure(driver, f"the driver record: {err}", "not recorded")
    if refusal.message and not refusal.said:
        _error(refusal.message)
    elif refusal.message:  # printed where it was raised, so only the log is owed it
        _log("refusal", refusal.message)
    driver._write_board()
    err_console.print(
        f"[red]driver stopped[/red] ({refusal.cause}); resume: {escape(refusal.resume)}; "
        f"track it: {FAILURES_COMMAND}",
        soft_wrap=True,
    )
    _log("refusal", f"driver stopped ({refusal.cause}); resume: {refusal.resume}; "
         f"track it: {FAILURES_COMMAND}")  # fmt: skip


def _supervise_drive(
    scope: Scope,
    target: Path,
    *,
    repo: str | None,
    org: str | None,
    dir_override: Path | None,
    workspace: Path | None,
    batch_ids: list[str] | None,
    max_inflight: int,
    interval: int,
    workspace_prefix: str,
    keep_sessions: bool,
    checkout: list[str] | None,
    quota_floor: float | None,
) -> NoReturn:
    """`drive --supervise --yes`: `_supervise` the looping command less `--supervise`."""
    from fr.commands import triage_batch_cmd as batch

    batch._supervise(
        batch.loop_command(
            batch_ids=batch_ids,
            scope=scope,
            scope_args=triage_kanban_cmd.scope_args(repo, org, dir_override, workspace),
            max_inflight=max_inflight,
            interval=interval,
            workspace_prefix=workspace_prefix,
            keep_sessions=keep_sessions,
            checkout=checkout,
            toplevel=None,
        )[1:]
        + (["--quota-floor", str(quota_floor)] if quota_floor is not None else []),
        target,
        scope,
        triage_kanban_cmd.scope_args(repo, org, dir_override, workspace),
        workspace_prefix,
    )


def _run_driver(
    driver: _Driver,
    *,
    scope: Scope,
    target: Path,
    dir_override: Path | None,
    once: bool,
    yes: bool,
    interval: int,
    pacer: Pacer | None,
    supervised_by: int | None,
) -> None:
    """Run the built driver under `drive.lock` (and, looping with `--yes`, its activity
    log) until `_host_loop` ends, then exit with its code or restart on a newer fr. The
    names tests patch (`drive_lock`, `_host_loop`, `_driver_started`, `_exec`,
    `_SUPERVISOR`) are read on the command module."""
    from fr.commands import triage_batch_cmd as batch

    end = LoopEnd(0)
    batch._SUPERVISOR = supervised_by
    log = DriveLog(target) if yes and not once else None  # plan mode and --once keep none
    with batch.drive_lock(drive_lock_dir(scope, dir_override)), drive_log_attached(log):
        if log is not None:
            batch._driver_started(driver, supervised_by)
        try:
            with _sigterm_interrupts():
                end = batch._host_loop(driver, once=once, interval=interval, pacer=pacer)
        except KeyboardInterrupt:  # Ctrl-C or SIGTERM: a clean stop too (p4-r4)
            driver.release_lease()
            _log("stop", "interrupted: the driver stopped cleanly")
            if supervised_by is not None:  # its supervisor reads this as deliberate (R11)
                raise typer.Exit(code=130) from None
            raise
        finally:
            batch._SUPERVISOR = None
        if log is not None:
            _log("stop", f"the driver stopped (exit {end.code})")
        if once:
            driver.warn_single_pass()
        if end.code != 2:  # a clean stop; a refusal keeps what it found
            driver.release_lease()
    if end.code:
        raise typer.Exit(code=end.code)
    restart = end.restart_to
    if restart is not None:
        # A `post_merge` installed a newer fr: this process still runs the code it
        # imported, which reads the state and config the new one writes (gh#998,
        # gh#964). It finished its pass; the lock is released, so the new process,
        # with the same pid and arguments, takes it as a fresh driver would.
        _say(f"restart: post_merge installed fr {restart} (this driver runs {__version__}); "
             "restarting on it")  # fmt: skip
        try:
            from fr.safe_spawn import fr_argv

            batch._exec(fr_argv(*sys.argv[1:]))
        except OSError as exc:  # the interpreter moved under a reinstall: say so, not a trace
            _fail(
                f"could not restart on fr {restart} ({exc}); every pass so far is saved, "
                "so start `fr triage batch drive` again with the same arguments",
                code=1,
            )


# The command layer, imported LAST, as `triage_cmd` imports `triage_batch_cmd`: loading
# `triage_cmd` (first, before `triage_kanban_cmd`) loads `triage_batch_cmd`, which imports
# this module's names, so whichever module loads first, every name the other needs exists.
from fr.commands import triage_cmd, triage_kanban_cmd  # noqa: E402, F401
from fr.commands.triage_cmd import drive_lock_dir, err_console  # noqa: E402
from fr.commands.triage_cmd import fail as _fail  # noqa: E402
