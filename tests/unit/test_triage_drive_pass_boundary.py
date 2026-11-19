# ruff: noqa: F811 - pytest fixtures imported from the sibling test modules
"""The looping driver's pass boundary (spec 2026-11-19-batch-train-truth R1-R7).

`fr.triage.drive_errors.classify` sorts every failure into a driver refusal (only the
operator can fix it: the loop stops, exit 2) or a transient failure (the pass ends, the
next one starts after a backoff). The loop cases drive `_host_loop` with a stub driver and a
fake `_sleep`, so a wait is a number in a list, never wall clock.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import triage_batch_cmd
from fr.forgeapi import ForgeApiError
from fr.ghclient import UnsupportedForgeOperation
from fr.triage.drive_errors import DriverRefusal, TransientPassFailure, classify
from fr.triage.driver_record import load_ledger, load_record
from fr.triage.errors import ConfigError, TriageError
from fr.triage.gitseam import GitError
from fr.triage.lease import Lease, LeaseExpired, LeaseHeld
from fr.triage.privacy import PrivacyError
from fr.triage.state_ref import StateRefConflict, StateRefPushRefused

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    _sandbox,
    checkout_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import clock, remote, runners, visibility  # noqa: F401

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
_LEASE = Lease(holder="x:host:1", started=NOW, expires=NOW)


# ------------------------------------------------------------- the classifier (R2-R4)


@pytest.mark.parametrize(
    ("exc", "cause"),
    [
        (StateRefConflict("moved at /tmp/a"), "state-ref-conflict"),
        (LeaseHeld("held by y until z", _LEASE), "lease-held"),
        (LeaseExpired("expired at z", _LEASE), "lease-expired"),
        (UnsupportedForgeOperation("pr_ready", "gitlab"), "unsupported-forge-operation"),
        (PrivacyError("private issue in public state repo"), "privacy"),
        (ConfigError("merge_method: rebase in .fr/triage.yaml"), "config:ConfigError"),
        (ForgeApiError("forge.api: soap"), "config:ForgeApiError"),
    ],
)
def test_classify_the_operators_failures_are_refusals(exc: Exception, cause: str) -> None:
    out = classify(exc)
    assert isinstance(out, DriverRefusal)
    assert out.cause == cause
    assert out.code == 2
    assert out.resume
    assert out.message == str(exc)


def test_classify_an_expired_lease_resumes_with_lease_take() -> None:
    out = classify(LeaseExpired("expired", _LEASE))
    assert isinstance(out, DriverRefusal)
    assert out.resume == "fr triage lease take --yes"


@pytest.mark.parametrize(
    ("exc", "cause"),
    [
        (StateRefPushRefused("the remote refused the push"), "push-refused"),
        (GitError("`git fetch origin` failed in /x: Could not resolve host"), "git:fetch"),
        (GitError("`git -C /x -c a=b push origin HEAD` failed in /x: no"), "git:push"),
        (GitError("cannot run git: no such file"), "git:run"),
        (TriageError("bad state file /tmp/x"), "triage:TriageError"),
        (ValueError("bad"), "unexpected:ValueError"),
    ],
)
def test_classify_every_other_failure_is_transient(exc: Exception, cause: str) -> None:
    out = classify(exc)
    assert isinstance(out, TransientPassFailure)
    assert out.cause == cause
    assert out.code == 2
    assert out.original is exc


def test_classify_causes_never_carry_the_message_text() -> None:
    for exc in (
        StateRefConflict("secret-head-abc123"),
        TriageError("secret-head-abc123"),
        GitError("`git fetch` failed: secret-head-abc123"),
        ValueError("secret-head-abc123"),
    ):
        assert "secret" not in classify(exc).cause


def _raise_in(function: str, body: str) -> BaseException:
    """An exception raised inside a function *function* of an `fr.` module."""
    scope: dict[str, Any] = {"__name__": "fr.commands.fake", "typer": typer}
    exec(f"def {function}():\n    {body}\n", scope)  # noqa: S102 - a module stand-in
    from fr.commands.triage_kanban_cmd import _fail

    scope["_fail"] = _fail
    try:
        scope[function]()
    except BaseException as exc:  # noqa: BLE001 - the point
        return exc
    raise AssertionError("did not raise")


def test_classify_an_exit_2_from_a_helper_is_a_refusal_named_by_its_function() -> None:
    out = classify(_raise_in("dispatch_batch", "raise typer.Exit(code=2)"))
    assert isinstance(out, DriverRefusal)
    assert out.cause == "exit:dispatch_batch"
    assert out.code == 2


def test_classify_an_exit_through_fail_names_the_caller_not_fail() -> None:
    out = classify(_raise_in("dispatch_batch", "_fail('nope')"))
    assert isinstance(out, DriverRefusal)
    assert out.cause == "exit:dispatch_batch"


def test_classify_an_exit_1_from_a_helper_is_transient_with_its_code() -> None:
    out = classify(_raise_in("dispatch_batch", "_fail('nope', code=1)"))
    assert isinstance(out, TransientPassFailure)
    assert out.cause == "exit:dispatch_batch"
    assert out.code == 1


def test_classify_returns_an_already_classified_failure_unchanged() -> None:
    refusal = DriverRefusal("runner-refused:fake", "no", "fix it")
    transient = TransientPassFailure("dispatch-failed:fake", "no", code=1)
    assert classify(refusal) is refusal
    assert classify(transient) is transient


# --------------------------------------------------------- the loop's boundary (R1-R7)


class StubDriver:
    yes = True
    restart_to: str | None = None
    failed_write = False

    def __init__(self, target: Path) -> None:
        self.target = target
        self.read_failures: set[str] = set()
        self.leased = False
        self.renewed = 0
        self.boards = 0

    def observation_owed(self) -> bool:
        return False

    def warn_single_pass(self) -> None:
        pass

    def take_lease(self) -> None:
        self.renewed += 1

    def _write_board(self) -> None:
        self.boards += 1


class _StopError(Exception):
    """Ends a loop from its sleep hook; never a pass failure."""


def _script(monkeypatch: pytest.MonkeyPatch, *outcomes: BaseException | bool) -> list[int]:
    """one_pass: each call takes the next outcome: an exception is raised, True ends the
    drive, False is a clean pass with work left."""
    calls: list[int] = []
    queue = list(outcomes)

    def one_pass(driver: Any) -> Any:
        calls.append(1)
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return False, SimpleNamespace(done=outcome, stalled=False), []

    monkeypatch.setattr(triage_batch_cmd, "one_pass", one_pass)
    return calls


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    out: list[float] = []

    def nap(seconds: float) -> None:
        out.append(seconds)
        if len(out) > 30:
            raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    return out


def _loop(driver: Any, *, once: bool = False, interval: int = 60) -> Any:
    return triage_batch_cmd._host_loop(driver, once=once, interval=interval)


def test_a_push_refusal_ends_the_pass_not_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    calls = _script(monkeypatch, StateRefPushRefused("refused by a hook"), False, True)
    end = _loop(StubDriver(tmp_path))
    assert end == triage_batch_cmd.LoopEnd(0)
    assert len(calls) == 3
    assert sleeps == [60, 60]
    assert capsys.readouterr().err.count("refused by a hook") == 1


def test_a_persistent_failure_is_reported_once_and_backs_off_to_its_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    failures = [StateRefPushRefused("the remote said no") for _ in range(8)]
    _script(monkeypatch, *failures, True)
    assert _loop(StubDriver(tmp_path), interval=60) == triage_batch_cmd.LoopEnd(0)
    assert sleeps == [60, 120, 240, 480, 900, 900, 900, 900]
    assert capsys.readouterr().err.count("the remote said no") == 1
    entry = load_ledger(tmp_path).causes["push-refused"]
    assert (entry.kind, entry.count, entry.exception) == ("transient", 8, "StateRefPushRefused")


def test_the_backoff_cap_is_the_interval_when_that_is_longer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    _script(monkeypatch, TriageError("x"), TriageError("x"), True)
    _loop(StubDriver(tmp_path), interval=1200)
    assert sleeps == [1200, 1200]


def test_a_clean_pass_resets_the_backoff_and_the_report_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _script(monkeypatch, TriageError("boom"), TriageError("boom"), False, TriageError("boom"), True)
    _loop(StubDriver(tmp_path), interval=10)
    assert sleeps == [10, 20, 10, 10]
    assert capsys.readouterr().err.count("boom") == 2


def test_ten_failed_passes_in_a_row_stop_as_a_refusal_with_the_last_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _script(monkeypatch, *[TriageError("x") for _ in range(9)], GitError("`git fetch` failed"))
    driver = StubDriver(tmp_path)
    end = _loop(driver)
    assert end == triage_batch_cmd.LoopEnd(2)
    assert len(sleeps) == 9
    err = capsys.readouterr().err
    assert "git:fetch" in err
    assert "fr triage drive failures --file --yes" in err
    assert driver.boards == 1
    ledger = load_ledger(tmp_path).causes
    assert ledger["triage:TriageError"].count == 9
    assert ledger["git:fetch"].kind == "refusal"
    record = load_record(tmp_path)
    assert record is not None and record.last_refusal is not None
    assert record.last_refusal.cause == "git:fetch"


@pytest.mark.parametrize(
    "exc",
    [StateRefConflict("someone else wrote it"), LeaseHeld("held by y", _LEASE)],
)
def test_a_refusal_stops_the_loop_on_the_first_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float], exc: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _script(monkeypatch, exc)
    driver = StubDriver(tmp_path)
    assert _loop(driver) == triage_batch_cmd.LoopEnd(2)
    assert sleeps == []
    err = capsys.readouterr().err
    assert str(exc) in " ".join(err.split())
    assert "fr triage drive failures --file --yes" in err
    assert driver.boards == 1
    cause = classify(exc).cause
    assert load_ledger(tmp_path).causes[cause].kind == "refusal"
    record = load_record(tmp_path)
    assert record is not None and record.last_refusal is not None
    assert (record.last_refusal.cause, record.last_refusal.message) == (cause, str(exc))


def test_a_renewal_that_fails_inside_wait_out_is_classified_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    from datetime import timedelta

    from fr.triage.quota import Pace

    class Leased(StubDriver):
        def __init__(self, target: Path) -> None:
            super().__init__(target)
            self.leased = True

        def take_lease(self) -> None:
            raise LeaseHeld("held by another driver", _LEASE)

    lease = Lease(holder="me", started=NOW, expires=NOW + timedelta(minutes=1))
    monkeypatch.setattr(triage_batch_cmd, "load_lease", lambda target: lease)

    class Pacer:
        def before_pass(self) -> Pace:
            return Pace("wait", NOW + timedelta(hours=1), "exhausted")

        def line(self, pace: Pace) -> str:
            return "waiting"

    driver = Leased(tmp_path)
    end = triage_batch_cmd._host_loop(driver, once=False, interval=60, pacer=Pacer())  # type: ignore[arg-type]
    assert end == triage_batch_cmd.LoopEnd(2)


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (StateRefConflict("moved"), 2),
        (StateRefPushRefused("refused"), 2),
        (TransientPassFailure("dispatch-failed:fake", "failed to dispatch", code=1), 1),
        (ValueError("bad"), 2),
    ],
)
def test_once_exits_with_the_failures_carried_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float], exc: Exception,
    code: int, capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _script(monkeypatch, exc)
    assert _loop(StubDriver(tmp_path), once=True) == triage_batch_cmd.LoopEnd(code)
    assert sleeps == []
    assert str(exc) in capsys.readouterr().err


def test_a_pass_whose_helper_fails_with_exit_2_stops_as_that_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _script(monkeypatch, _raise_in("dispatch_batch", "_fail('the batch is gone')"))
    assert _loop(StubDriver(tmp_path)) == triage_batch_cmd.LoopEnd(2)
    assert "exit:dispatch_batch" in capsys.readouterr().err


def test_a_pass_whose_helper_fails_with_exit_1_is_transient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    _script(monkeypatch, _raise_in("dispatch_batch", "_fail('the runner', code=1)"), True)
    assert _loop(StubDriver(tmp_path)) == triage_batch_cmd.LoopEnd(0)
    assert sleeps == [60]


def test_an_exception_out_of_a_wait_is_never_a_pass_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def nap(seconds: float) -> None:
        raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    _script(monkeypatch, False)
    with pytest.raises(_StopError):
        _loop(StubDriver(tmp_path))


def test_keyboard_interrupt_passes_through_the_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    _script(monkeypatch, KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        _loop(StubDriver(tmp_path))


# ------------------------------------------- a refused push, with the real driver (R3)


def test_a_refused_push_mid_loop_is_pushed_by_the_next_pass_with_no_event_twice(
    tmp_path: Path,
    world: Any,
    checkout: Any,
    runners: Any,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    import yaml
    from fr.cli import app
    from fr.triage.scope_config import scope_id
    from fr.triage.state_ref import ref_name
    from typer.testing import CliRunner

    from tests.unit.test_triage_batch_drive_cmd import REPO, _naps_until
    from tests.unit.test_triage_batch_drive_cmd import _StopError as StopLoop
    from tests.unit.test_triage_driver_pass import SCOPE, _workspace, _world

    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    pushes: list[int] = []
    real = triage_batch_cmd.push_now

    def push(scope: Any, target: Path) -> Any:
        pushes.append(1)
        if len(pushes) == 2:  # the first pass's save: nothing on the remote moved
            raise StateRefPushRefused("the proxy answered HTTP 403")
        return real(scope, target)

    monkeypatch.setattr(triage_batch_cmd, "push_now", push)
    naps = _naps_until(monkeypatch, 2)
    result = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--yes", "--interval", "30", "--repo", REPO,
              "--dir", str(state)],
    )  # fmt: skip

    assert isinstance(result.exception, StopLoop), result.output
    assert " ".join(result.output.split()).count("the proxy answered HTTP 403") == 1
    assert naps == [30, 30]
    assert len(pushes) >= 4  # the second pass renewed and saved, both pushed
    head = subprocess.run(
        ["git", "rev-parse", ref_name(scope_id(SCOPE))], cwd=remote, check=True,
        capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    pushed = yaml.safe_load(
        subprocess.run(["git", "show", f"{head}:judgements.yaml"], cwd=remote, check=True,
                       capture_output=True, text=True).stdout
    )  # fmt: skip
    for batch in pushed["batches"]:
        kinds = [e["kind"] for e in batch.get("events") or []]
        assert kinds.count("dispatch") <= 1, (batch["id"], kinds)
    assert any(
        "dispatch" in [e["kind"] for e in b.get("events") or []]
        for b in pushed["batches"] if b["id"] == "b1"
    ), "the first pass's dispatch reached the remote with the second pass's push"  # fmt: skip
