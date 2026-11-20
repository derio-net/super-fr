"""The supervisor's restart policy (spec 2026-11-19-batch-train-truth R11, R13)."""

from __future__ import annotations

import signal
from datetime import UTC, datetime, timedelta

import pytest
from fr.triage.supervise import CrashLoop, Restart, Stop, restart_decision

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("code", [0, 2, 3])
def test_a_deliberate_exit_code_stops_with_that_code(code: int) -> None:
    assert restart_decision([], NOW, code) == Stop(code)


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_a_clean_stop_after_a_signal_is_deliberate(sig: signal.Signals) -> None:
    # the driver's handler turns SIGINT/SIGTERM into a clean stop (exit 128+n); a child that
    # the signal killed outright (negative returncode) is the same end
    assert restart_decision([], NOW, 128 + sig) == Stop(128 + sig)
    assert restart_decision([], NOW, -sig) == Stop(128 + sig)


@pytest.mark.parametrize("end", [1, 4, 255, -signal.SIGKILL, -signal.SIGSEGV])
def test_another_exit_or_death_is_a_crash_that_restarts(end: int) -> None:
    decision = restart_decision([], NOW, end)
    assert isinstance(decision, Restart)


def test_the_backoff_starts_at_five_seconds_doubles_and_caps_at_five_minutes() -> None:
    delays = []
    history: list[datetime] = []
    for i in range(5):
        decision = restart_decision(history, NOW + timedelta(seconds=i), 1)
        assert isinstance(decision, Restart)
        delays.append(decision.delay)
        history.append(NOW + timedelta(seconds=i))
    assert delays == [5, 10, 20, 40, 80]
    # the cap, with a wide enough window and a short crash-loop limit not reached
    assert restart_decision(history[:2], NOW, 1, base=100.0) == Restart(300.0)


def test_a_sixth_restart_within_thirty_minutes_is_a_crash_loop() -> None:
    history = [NOW - timedelta(minutes=m) for m in (25, 20, 15, 10, 5)]
    assert restart_decision(history, NOW, 1) == CrashLoop(2)
    assert restart_decision(history[1:], NOW, 1) == Restart(80.0)


def test_restarts_older_than_thirty_minutes_fall_out_of_the_window() -> None:
    history = [NOW - timedelta(minutes=m) for m in (95, 90, 80, 60, 31)]
    assert restart_decision(history, NOW, 1) == Restart(5.0)
    history[-1] = NOW - timedelta(minutes=29)
    assert restart_decision(history, NOW, 1) == Restart(10.0)


def test_a_deliberate_end_is_never_a_crash_even_in_a_loop() -> None:
    history = [NOW - timedelta(minutes=m) for m in (4, 3, 2, 1, 0)]
    assert restart_decision(history, NOW, 3) == Stop(3)
