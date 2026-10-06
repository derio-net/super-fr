"""`fr triage batch drive` restarts idle sessions once per pass (driver-sessions §B, R6).

The world, clone and runner are `test_triage_batch_drive_cmd`'s; the restarting runner is a
`FakeRunner` that is also a `SessionRestarter`.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.commands import triage_batch_cmd

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 — fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _drive,
    _drive_named,
    _state,
    _StopError,
    checkout_fixture,
    git_checkout_fixture,
    runner_fixture,
    sleeps_fixture,
    world_fixture,
)


@pytest.fixture
def execs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    out: list[list[str]] = []

    def _exec(argv: list[str]) -> None:
        out.append(argv)
        raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_exec", _exec)
    return out


POST_MERGE = ["./scripts/install.sh"]


class RestartingRunner(FakeRunner):
    """A FakeRunner that can also restart idle sessions; records every call in `calls`."""

    def __init__(self) -> None:
        super().__init__()
        self.restarts: list[tuple[str, ...]] = []
        self.summary: Any = None
        self.raises: Exception | None = None

    def restart_idle(self, *, exclude: Any = ()) -> Any:
        from fr_dispatch.protocols import RestartSummary

        self.calls.append("restart_idle")
        self.restarts.append(tuple(exclude))
        if self.raises is not None:
            raise self.raises
        return self.summary or RestartSummary(ok=2, skipped=1, failed=())


@pytest.fixture(name="rrunner")
def rrunner_fixture(monkeypatch: pytest.MonkeyPatch) -> RestartingRunner:
    fake = RestartingRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


def _two_merged(world: World, tmp_path: Path) -> None:
    for n in (1, 2):
        world.issues[n] = "closed"
        world.pr(100 + n, f"feat/batch-b{n}", [n], state="MERGED",
                 merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    _state(
        tmp_path, world,
        _batch("b1", 1, events=_dispatch_event("b1")),
        _batch("b2", 2, events=_dispatch_event("b2")),
    )  # fmt: skip


def _opted_in(world: World) -> None:
    world.config = {"post_merge": POST_MERGE, "post_merge_restart": "idle"}


def test_two_closeouts_in_one_pass_restart_once_after_both_started(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(rrunner.dispatched) == 2
    assert rrunner.restarts == [()]
    last_dispatch = max(i for i, c in enumerate(rrunner.calls) if c == "dispatch")
    assert rrunner.calls.index("restart_idle") > last_dispatch
    assert "restart: 2 ok, 1 skipped, 0 failed" in out


def test_a_failed_pane_is_named(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    from fr_dispatch.protocols import RestartSummary

    rrunner.summary = RestartSummary(ok=1, skipped=0, failed=(("w1:p2", "did not exit"),))
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "restart: 1 ok, 0 skipped, 1 failed" in out
    assert "restart failed w1:p2: did not exit" in out


def test_the_default_config_never_restarts(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    world.config = {"post_merge": POST_MERGE}
    _two_merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert rrunner.restarts == [] and "restart:" not in out


def test_a_failed_post_merge_never_restarts(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    from fr.triage.errors import TriageError

    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True

    def _boom(command: list[str]) -> None:
        raise TriageError("install failed")

    checkout.run_command = _boom  # type: ignore[method-assign]
    _drive(tmp_path, "--once", "--yes")
    assert rrunner.restarts == []


def test_a_runner_that_cannot_restart_is_reported_once_and_closeouts_still_start(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    sleeps: list[float], monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(runner.dispatched) == 2
    assert out.count("cannot restart sessions") == 1


def test_a_runner_that_refuses_preflight_is_reported_and_not_restarted(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    real = rrunner.preflight
    state = {"calls": 0}

    def _preflight(items: Any) -> str | None:
        state["calls"] += 1
        # the close-out dispatches pass; the restart's probe is refused
        return (
            "no herdr"
            if any(i.id.endswith("closeout-b1") and state["calls"] > 2 for i in items)
            else real(items)
        )

    rrunner.preflight = _preflight  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert rrunner.restarts == []


def test_a_restart_that_raises_is_reported_and_the_exit_code_is_unaffected(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner
) -> None:
    rrunner.raises = RuntimeError("herdr gone")
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "herdr gone" in out
    assert len(rrunner.dispatched) == 2


def test_the_restart_happens_before_the_exec_restart(
    tmp_path: Path, world: World, checkout: DriveCheckout, rrunner: RestartingRunner,
    monkeypatch: pytest.MonkeyPatch, execs: list[list[str]], sleeps: list[float],
) -> None:  # fmt: skip
    _opted_in(world)
    _two_merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(triage_batch_cmd, "_installed_version", lambda: "99.0.0")
    seen: list[int] = []
    real_exec = triage_batch_cmd._exec

    def _exec(argv: list[str]) -> None:
        seen.append(len(rrunner.restarts))
        real_exec(argv)

    monkeypatch.setattr(triage_batch_cmd, "_exec", _exec)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert seen == [1]
