"""`fr triage batch drive --supervise` and the supervised driver (spec
2026-11-19-batch-train-truth R11, R12)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage.driver_record import load_record
from typer.testing import CliRunner

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
SCOPE = ["--repo", "example-org/widgets"]


def _run(tmp_path: Path, *args: str) -> Any:
    return CliRunner().invoke(
        app, ["triage", "batch", "drive", *SCOPE, "--dir", str(tmp_path), *args]
    )


def test_supervise_is_refused_with_once(tmp_path: Path) -> None:
    result = _run(tmp_path, "--supervise", "--once", "--yes")
    assert result.exit_code == 2
    assert "--once" in result.output


def test_supervise_is_refused_without_yes(tmp_path: Path) -> None:
    result = _run(tmp_path, "--supervise")
    assert result.exit_code == 2
    assert "--yes" in result.output


def test_supervise_runs_the_same_arguments_less_supervise_and_takes_no_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def supervise(args: list[str], target: Path, *rest: object) -> NoReturn:
        seen.update(args=args, target=target)
        raise SystemExit(0)

    def no_lock(*_: object) -> NoReturn:
        raise AssertionError("the supervisor takes neither drive.lock nor the lease")

    monkeypatch.setattr(triage_batch_cmd, "_supervise", supervise)
    monkeypatch.setattr(triage_batch_cmd, "drive_lock", no_lock)
    monkeypatch.setattr(triage_batch_cmd, "_host_lease", no_lock)
    result = _run(tmp_path, "--supervise", "--yes", "--interval", "30", "--max-inflight", "2")
    assert result.exit_code == 0
    args = seen["args"]
    assert args[:3] == ["triage", "batch", "drive"]
    assert "--supervise" not in args and "--yes" in args and "--once" not in args
    assert args[args.index("--interval") + 1] == "30"
    assert args[args.index("--max-inflight") + 1] == "2"
    assert seen["target"] == tmp_path


def test_supervise_builds_the_childs_argv_through_the_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.triage.supervise as supervise_mod

    built: dict[str, Any] = {}

    class Fake:
        def __init__(self, make_argv: Any, state_dir: Path, **_: object) -> None:
            built["argv"] = make_argv(4242)
            built["dir"] = state_dir

        def run(self) -> int:
            return 3

    monkeypatch.setattr(supervise_mod, "Supervisor", Fake)
    with pytest.raises(Exception) as info:  # typer.Exit
        triage_batch_cmd._supervise(["triage", "batch", "drive", "--yes"], tmp_path)
    assert getattr(info.value, "exit_code", None) == 3
    argv = built["argv"]
    assert argv[1:5] == ["-P", "-m", "fr", "triage"] and argv[-2:] == ["--supervised-by", "4242"]


# --------------------------------------------------- a supervised driver stops with its parent


class StubDriver:
    yes = True
    restart_to: str | None = None
    failed_write = False

    def __init__(self, target: Path) -> None:
        self.target = target
        self.read_failures: set[str] = set()
        self.leased = False

    def observation_owed(self) -> bool:
        return False

    def warn_single_pass(self) -> None:
        pass

    def take_lease(self) -> None:
        pass

    def _write_board(self) -> None:
        pass


@pytest.fixture
def supervised(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(triage_batch_cmd, "_SUPERVISOR", 777)
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    parent = {"pid": 777}
    monkeypatch.setattr(triage_batch_cmd.os, "getppid", lambda: parent["pid"])
    return parent


def _passes(monkeypatch: pytest.MonkeyPatch, on_pass: Any) -> list[int]:
    calls: list[int] = []

    def one_pass(driver: Any) -> Any:
        calls.append(1)
        on_pass(len(calls))
        return False, SimpleNamespace(done=False, stalled=False), []

    monkeypatch.setattr(triage_batch_cmd, "one_pass", one_pass)
    return calls


def test_a_changed_parent_stops_the_driver_between_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, supervised: dict[str, int]
) -> None:
    def on_pass(n: int) -> None:
        if n == 2:
            supervised["pid"] = 1  # the supervisor is gone: the driver was re-parented

    calls = _passes(monkeypatch, on_pass)
    monkeypatch.setattr(triage_batch_cmd, "_sleep", lambda s: None)
    end = triage_batch_cmd._host_loop(StubDriver(tmp_path), once=False, interval=60)
    assert end == triage_batch_cmd.LoopEnd(0)
    assert len(calls) == 2


def test_a_changed_parent_stops_the_driver_inside_a_wait_within_a_second(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, supervised: dict[str, int]
) -> None:
    naps: list[float] = []

    def nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 3:
            supervised["pid"] = 1

    _passes(monkeypatch, lambda n: None)
    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    end = triage_batch_cmd._host_loop(StubDriver(tmp_path), once=False, interval=600)
    assert end == triage_batch_cmd.LoopEnd(0)
    assert naps == [1.0, 1.0, 1.0]  # a 600 s wait is cut into one-second looks at the parent


def test_an_unsupervised_wait_is_one_sleep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(triage_batch_cmd, "_SUPERVISOR", None)
    naps: list[float] = []
    monkeypatch.setattr(triage_batch_cmd, "_sleep", naps.append)
    triage_batch_cmd._wait(600)
    assert naps == [600]


def test_driver_started_records_the_supervisor_on_driver_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    triage_batch_cmd._driver_started(StubDriver(tmp_path), 777)  # type: ignore[arg-type]
    record = load_record(tmp_path)
    assert record is not None and record.supervised == 777 and record.started == NOW
    triage_batch_cmd._driver_started(StubDriver(tmp_path), None)  # type: ignore[arg-type]
    record = load_record(tmp_path)
    assert record is not None and record.supervised is None and record.restarts == 0


# --------------------------------------- the real drive command's interrupt, and its lease


def _drive_with_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiser: Any, *args: str
) -> tuple[Any, StubDriver]:
    driver = StubDriver(tmp_path)
    driver.released = 0  # type: ignore[attr-defined]
    driver.release_lease = lambda: setattr(driver, "released", driver.released + 1)  # type: ignore[attr-defined,method-assign]
    monkeypatch.setattr(triage_batch_cmd, "build_driver", lambda *a, **k: driver)
    monkeypatch.setattr(triage_batch_cmd, "_host_lease", lambda *a, **k: None)
    monkeypatch.setattr(triage_batch_cmd, "_host_loop", raiser)
    monkeypatch.setattr(triage_batch_cmd, "_driver_started", lambda *a, **k: None)
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    return _run(tmp_path, "--yes", *args), driver


def test_an_interrupted_supervised_drive_exits_130_and_releases_its_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.supervise import Stop, restart_decision

    def interrupted(*a: Any, **k: Any) -> NoReturn:
        raise KeyboardInterrupt

    result, driver = _drive_with_loop(tmp_path, monkeypatch, interrupted, "--supervised-by", "777")
    assert result.exit_code == 130, result.output
    assert driver.released == 1  # type: ignore[attr-defined]
    # and the supervisor reads that exit as a deliberate end, never a crash
    assert restart_decision([], NOW, result.exit_code) == Stop(130)


def test_an_interrupted_unsupervised_drive_releases_its_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*a: Any, **k: Any) -> NoReturn:
        raise KeyboardInterrupt

    result, driver = _drive_with_loop(tmp_path, monkeypatch, interrupted)
    assert driver.released == 1  # type: ignore[attr-defined]


def test_a_vanished_supervisor_ends_the_loop_cleanly_and_the_lease_is_released(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _passes(monkeypatch, lambda n: None)
    monkeypatch.setattr(triage_batch_cmd, "_sleep", lambda s: None)
    driver = StubDriver(tmp_path)
    driver.released = 0  # type: ignore[attr-defined]
    driver.release_lease = lambda: setattr(driver, "released", driver.released + 1)  # type: ignore[attr-defined,method-assign]
    monkeypatch.setattr(triage_batch_cmd, "build_driver", lambda *a, **k: driver)
    monkeypatch.setattr(triage_batch_cmd, "_host_lease", lambda *a, **k: None)
    monkeypatch.setattr(triage_batch_cmd, "_driver_started", lambda *a, **k: None)
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    # --supervised-by names a pid that is not this process's parent: the supervisor is gone
    result = _run(tmp_path, "--yes", "--supervised-by", str(os.getppid() + 100000))
    assert result.exit_code == 0, result.output
    assert calls == []  # it stopped before any pass
    assert driver.released == 1  # type: ignore[attr-defined]
