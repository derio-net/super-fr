"""The bounded settle poll (spec 2026-11-23-pr-readiness-wait R3)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.ghclient import UnsupportedForgeOperation
from fr.settle.model import Modes
from fr.settle.target import HeadTime
from fr.run.ci_evidence import NO_CI_WAIT_SECONDS
from fr.settle.poll import DEFAULT_WAIT, WAIT_CEILING, SettleRefused, check_wait, settle

HEAD = "b" * 40
READS = frozenset({"pr_view", "pr_checks"})


class ReadOnlyForge:
    """Serves a script of (view, checks) reads; any other attribute is a write and fails."""

    def __init__(self, script: list[tuple[dict[str, Any], list[dict[str, Any]]]]) -> None:
        self.script = script
        self.views = 0
        self.checks = 0
        self.calls: list[str] = []

    def _at(self, n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self.script[min(n, len(self.script) - 1)]

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.calls.append("pr_view")
        view = self._at(self.views)[0]
        self.views += 1
        return view

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        self.calls.append("pr_checks")
        checks = self._at(self.checks)[1]
        self.checks += 1
        return checks

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"settle called {name}: it may only read")


def _view(mergeable: str = "MERGEABLE", state: str = "CLEAN") -> dict[str, Any]:
    return {"head_oid": HEAD, "base_ref": "main", "mergeable": mergeable, "merge_state": state}


PENDING = [{"name": "ci-ok", "bucket": "pending"}]
GREEN = [{"name": "ci-ok", "bucket": "pass"}]


class Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def _modes(conflicts: str = "fix", ci: str = "fix") -> Modes:
    return Modes.from_setting(conflicts=conflicts, ci=ci)


def _settle(
    forge: ReadOnlyForge,
    clock: Clock,
    modes: Modes,
    wait: float = 300,
    committed: float | None = None,
) -> Any:
    return settle(
        forge,
        "o/r",
        7,
        gate_names=None,
        modes=modes,
        ci_none=False,
        wait=wait,
        clock=clock.now,
        sleep=clock.sleep,
        committed_at=lambda _sha: HeadTime(clock.t - 10 if committed is None else committed),
    )


def test_the_poll_stops_as_soon_as_every_concern_settles() -> None:
    forge = ReadOnlyForge([(_view("UNKNOWN", "UNKNOWN"), PENDING), (_view(), GREEN)])
    clock = Clock()
    v = _settle(forge, clock, _modes())
    assert (v.conflict_state, v.ci_state, v.exit_code) == ("clean", "green", 0)
    assert forge.views == 2 and len(clock.slept) == 1


def test_the_poll_stops_at_the_end_of_the_wait() -> None:
    forge = ReadOnlyForge([(_view(), PENDING)])
    clock = Clock()
    v = _settle(forge, clock, _modes(), wait=60)
    assert v.ci_state == "pending" and v.exit_code == 75
    assert sum(clock.slept) == pytest.approx(60)


def test_a_settled_read_does_not_sleep() -> None:
    forge = ReadOnlyForge([(_view(), GREEN)])
    clock = Clock()
    _settle(forge, clock, _modes())
    assert clock.slept == []


def test_an_off_concern_is_never_read() -> None:
    forge = ReadOnlyForge([(_view(), PENDING)])
    clock = Clock()
    v = _settle(forge, clock, _modes(ci="off"))
    assert "pr_checks" not in forge.calls
    assert v.ci_state == "off" and v.exit_code == 0 and clock.slept == []


def test_both_off_reads_nothing() -> None:
    forge = ReadOnlyForge([(_view(), PENDING)])
    v = _settle(forge, Clock(), _modes(conflicts="off", ci="off"))
    assert forge.calls == [] and v.exit_code == 0


def test_only_report_and_fix_concerns_are_polled() -> None:
    # conflicts off: an unknown mergeability never keeps the poll going.
    forge = ReadOnlyForge([(_view("UNKNOWN", "UNKNOWN"), GREEN)])
    clock = Clock()
    v = _settle(forge, clock, _modes(conflicts="off", ci="report"))
    assert v.settled and clock.slept == []
    # a report concern still waits.
    forge = ReadOnlyForge([(_view(), PENDING), (_view(), GREEN)])
    clock = Clock()
    v = _settle(forge, clock, _modes(conflicts="off", ci="report"))
    assert v.ci_state == "green" and len(clock.slept) == 1


def test_the_poll_makes_only_reads() -> None:
    forge = ReadOnlyForge([(_view("UNKNOWN", "UNKNOWN"), PENDING)] * 3 + [(_view(), GREEN)])
    _settle(forge, Clock(), _modes())
    assert set(forge.calls) <= READS


def test_an_unsupported_read_is_unsupported_and_exits_0() -> None:
    class Glab(ReadOnlyForge):
        def pr_view(self, repo: str, number: int) -> dict[str, Any]:
            raise UnsupportedForgeOperation("pr_view", "glab")

    v = _settle(Glab([]), Clock(), _modes())
    assert (v.conflict_state, v.ci_state, v.exit_code) == ("unsupported", "unsupported", 0)
    assert "glab" in v.lines[0]


def test_the_wait_has_a_default_and_a_ceiling_below_600() -> None:
    assert DEFAULT_WAIT == 300
    assert WAIT_CEILING == 540
    check_wait(0)
    check_wait(540)
    with pytest.raises(SettleRefused, match="540"):
        check_wait(541)
    with pytest.raises(SettleRefused):
        check_wait(-1)
    with pytest.raises(SettleRefused, match="540"):
        _settle(ReadOnlyForge([(_view(), GREEN)]), Clock(), _modes(), wait=541)


def test_an_unsupported_checks_read_keeps_the_views_head() -> None:
    class NoChecks(ReadOnlyForge):
        def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            raise UnsupportedForgeOperation("pr_checks", "gitea")

    v = _settle(NoChecks([(_view(), GREEN)]), Clock(), _modes())
    assert v.ci_state == "unsupported"
    assert v.witness.endswith(f"@{HEAD}")


def test_a_first_view_is_not_read_again() -> None:
    forge = ReadOnlyForge([(_view(), GREEN)])
    clock = Clock()
    settle(
        forge, "o/r", 7, gate_names=None, modes=_modes(), ci_none=False, wait=0,
        clock=clock.now, sleep=clock.sleep, committed_at=lambda _s: HeadTime(clock.t),
        first_view=_view(),
    )  # fmt: skip
    assert forge.views == 0


@pytest.mark.parametrize("wait", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_a_wait_that_is_not_a_finite_bounded_number_is_refused(wait: float) -> None:
    """Review l-errors-r1: `nan` compares false against both bounds."""
    with pytest.raises(SettleRefused):
        check_wait(wait)


def test_a_head_that_crosses_the_no_ci_wait_during_the_poll_ends_missing() -> None:
    """l-tests-r1: no check yet, the head 30 s short of the no-CI wait, a 60 s poll."""
    forge = ReadOnlyForge([(_view(), [])])
    clock = Clock()
    start = clock.t

    v = _settle(forge, clock, _modes(), wait=60, committed=start - (NO_CI_WAIT_SECONDS - 30))

    assert forge.views >= 2
    assert (v.ci_state, v.exit_code) == ("missing", 4)
