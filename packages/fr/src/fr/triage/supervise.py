"""The session-bound supervisor of the looping driver (spec 2026-11-19-batch-train-truth
R11-R13): the restart policy (pure) and the process that applies it.

`fr triage batch drive --supervise --yes` starts the driver as its child, restarts it when it
ends other than deliberately, and never detaches: it stays in its caller's session and process
group, so it ends with its caller. A deliberate end is exit 0, 2 or 3, or the child's own clean
stop on SIGINT, SIGTERM or SIGHUP; anything else (another exit code, death by another signal,
such as SIGKILL) is a crash.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType

from fr.safe_spawn import Child
from fr.triage.drive_log import DriveLog
from fr.triage.driver_record import FAILURES_COMMAND, FailureKind
from fr.triage.errors import TriageError

DELIBERATE_CODES = frozenset({0, 2, 3})
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
BASE_DELAY_S = 5.0
MAX_DELAY_S = 300.0
LOOP_WINDOW = timedelta(minutes=30)
LOOP_RESTARTS = 5  # the sixth restart within the window is a crash loop
GRACE_S = 10.0  # SIGTERM to SIGKILL
POLL_S = 1.0


@dataclass(frozen=True)
class Stop:
    """The end was deliberate: the supervisor exits with *code*."""

    code: int


@dataclass(frozen=True)
class Restart:
    """A crash: start the driver again after *delay* seconds."""

    delay: float


@dataclass(frozen=True)
class CrashLoop:
    """Too many crashes too fast: the supervisor stops as a refusal (*code*)."""

    code: int = 2


Decision = Stop | Restart | CrashLoop


def describe(end: int) -> str:
    """The crash's name for the ledger: `SIGKILL` for a death by signal, else the code."""
    if end < 0:
        try:
            return signal.Signals(-end).name
        except ValueError:
            return f"signal {-end}"
    return str(end)


def restart_decision(
    history: Sequence[datetime],
    now: datetime,
    end: int,
    *,
    base: float = BASE_DELAY_S,
) -> Decision:
    """What the supervisor does about a child that ended with *end* (a `Popen` return code:
    negative for a signal). *history* holds the times of its earlier restarts; those more than
    30 minutes old fall out. Delays are *base*, doubling, capped at five minutes."""
    if end in DELIBERATE_CODES:
        return Stop(end)
    for sig in STOP_SIGNALS:
        if end in (128 + sig, -sig):  # the driver's own clean stop on that signal
            return Stop(128 + int(sig))
    recent = [t for t in history if now - t <= LOOP_WINDOW]
    if len(recent) >= LOOP_RESTARTS:
        return CrashLoop()
    return Restart(min(base * 2 ** len(recent), MAX_DELAY_S))


class Supervisor:
    """Runs a driver child and restarts it per `restart_decision`. Never detaches."""

    def __init__(
        self,
        make_argv: Callable[[int], list[str]],
        state_dir: Path,
        *,
        base_delay: float = BASE_DELAY_S,
        grace: float = GRACE_S,
        poll: float = POLL_S,
        now: Callable[[], datetime] | None = None,
        fr_version: str = "",
        resume: str = "fr triage batch drive --supervise --yes",
        on_refusal: Callable[[], None] | None = None,
    ) -> None:
        self.make_argv = make_argv
        self.state_dir = state_dir
        self.base_delay, self.grace, self.poll = base_delay, grace, poll
        self.now = now or (lambda: datetime.now(UTC))
        self.fr_version = fr_version
        self.resume = resume
        self.on_refusal = on_refusal  # renders the board once after a crash loop (R8)
        self.log = DriveLog(state_dir)
        self.history: list[datetime] = []
        self.restarts = 0
        self.last_crash: str | None = None
        self._signal: int | None = None
        self._child: Child | None = None

    # -- the one-line records ------------------------------------------------------------

    def _say(self, kind: str, line: str) -> None:
        """One line to stderr and to `drive.log`: the supervisor appends every line it prints
        (R22)."""
        try:
            print(f"{kind}: {line}", file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass
        try:
            self.log.append(kind, line, self.now())
        except OSError:
            pass  # the log is a view: never a reason to stop supervising

    def _record(self, child_pid: int | None) -> None:
        from fr.triage import driver_record

        try:
            driver_record.record_supervisor(
                self.state_dir,
                supervisor=os.getpid(),
                child=child_pid,
                restarts=self.restarts,
                last_crash=self.last_crash,
            )
        except (OSError, TriageError):
            pass

    def _refuse(self, cause: str, message: str) -> None:
        """The refusal on `driver.yaml` (the board's driver-stopped need reads it), then the
        board rendered once if a renderer was given. Neither can stop the supervisor."""
        from fr.triage import driver_record

        try:
            driver_record.record_refusal(self.state_dir, cause, message, self.resume, self.now(),
                                         self.fr_version, as_supervisor=True)  # fmt: skip
        except (OSError, TriageError):
            pass
        if self.on_refusal is not None:
            try:
                self.on_refusal()
            except Exception:  # noqa: BLE001 - the board is a view
                pass

    def _ledger(self, kind: FailureKind, cause: str, message: str) -> None:
        from fr.triage import driver_record

        try:
            driver_record.record_failure(
                self.state_dir, kind, cause, message, self.now(), self.fr_version
            )
        except (OSError, TriageError):
            pass

    # -- signals -------------------------------------------------------------------------

    def _on_signal(self, signum: int, frame: FrameType | None) -> None:
        self._signal = signum

    def _install(self) -> dict[int, object]:
        if threading.current_thread() is not threading.main_thread():
            return {}
        return {int(s): signal.signal(s, self._on_signal) for s in STOP_SIGNALS}

    @staticmethod
    def _restore(previous: dict[int, object]) -> None:
        for signum, handler in previous.items():
            signal.signal(signum, handler)  # type: ignore[arg-type]

    # -- the child -----------------------------------------------------------------------

    def _terminate(self, child: Child) -> int:
        """SIGTERM *child*, SIGKILL after the grace; its return code."""
        if child.poll() is None:
            child.terminate()
            end = child.wait(self.grace)
            if end is not None:
                return end
            self._say(
                "stop", f"driver pid {child.pid} ignored SIGTERM for {self.grace:g}s: SIGKILL"
            )
            child.kill()
        return child.wait() or 0

    def _watch(self, child: Child, parent: int) -> tuple[int, str | None]:
        """Wait for *child*; `(its code, why we stopped it or None)`. Stops it when this
        process got SIGHUP, SIGINT or SIGTERM, or its own parent changed (R12)."""
        while True:
            if self._signal is not None:
                name = signal.Signals(self._signal).name
                return self._terminate(child), f"{name} received"
            if os.getppid() != parent:
                return self._terminate(child), "the supervisor's parent ended"
            end = child.wait(self.poll)
            if end is not None:
                return end, None

    def _sleep(self, seconds: float, parent: int) -> str | None:
        """Wait *seconds* before a restart, still watching the parent and signals."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._signal is not None:
                return f"{signal.Signals(self._signal).name} received"
            if os.getppid() != parent:
                return "the supervisor's parent ended"
            time.sleep(min(self.poll, max(0.0, deadline - time.monotonic())))
        return None

    def run(self) -> int:
        """Supervise until a deliberate end, a crash loop, a signal or the loss of the
        parent; the exit code."""
        previous = self._install()
        parent = os.getppid()
        try:
            return self._run(parent)
        finally:
            self._restore(previous)

    def _run(self, parent: int) -> int:
        me = os.getpid()
        while True:
            child = Child(self.make_argv(me))
            self._child = child
            self._record(child.pid)
            end, why = self._watch(child, parent)
            if why is not None:
                self._say("stop", f"{why}: the driver (pid {child.pid}) was stopped")
                return 0
            decision = restart_decision(self.history, self.now(), end, base=self.base_delay)
            if isinstance(decision, Stop):
                self._say("stop", f"the driver ended deliberately (exit {decision.code})")
                return decision.code
            crash = describe(end)
            cause = f"crash:{crash}"
            self.last_crash = crash
            if isinstance(decision, CrashLoop):
                minutes = int(LOOP_WINDOW.total_seconds() // 60)
                message = f"{LOOP_RESTARTS + 1} crashes within {minutes} minutes, the last: {crash}"
                self._ledger("crash", cause, f"the driver ended with {crash}")  # p2a-r6
                self._ledger("refusal", "crash-loop", message)
                self._record(None)
                self._refuse("crash-loop", message)
                self._say("refusal", f"driver stopped (crash-loop): {message}; "
                          f"resume: {self.resume}; track it: {FAILURES_COMMAND}")  # fmt: skip
                self._say("stop", f"crash-loop: {message}")
                return decision.code
            self.history.append(self.now())
            self.restarts += 1
            self._ledger("crash", cause, f"the driver ended with {crash}")
            self._record(None)
            self._say("restart", f"the driver (pid {child.pid}) crashed ({crash}); "
                      f"restart {self.restarts} in {decision.delay:g}s")  # fmt: skip
            why = self._sleep(decision.delay, parent)
            if why is not None:
                self._say("stop", f"{why} while waiting to restart the driver")
                return 0
