"""The driver keeps every page current (spec 2026-11-18-triage-pages-ux R6, R7, §C).

The world, clone and runner are `test_triage_batch_drive_cmd`'s; the clock is a fake that
moves one hour per read, so every snapshot the drive stores has its own file name.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.commands import triage_architecture_cmd, triage_batch_cmd, triage_cmd
from fr.triage.architecture import Measured
from fr.triage.origins import OriginsFacts, write_facts

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 — fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _drive,
    _proposed,
    _sandbox,
    _state,
    checkout_fixture,
    runner_fixture,
    world_fixture,
)

PAGES = ("backlog", "issues", "history")
SUBSYSTEMS = {"subsystems": [{"name": "src", "path": ["src/**"], "then_ref": "HEAD", "themes": []}]}
CANCEL = "      - {kind: cancel, at: 2026-10-01T12:00:00Z}\n"


def _written(state: Path) -> set[str]:
    return {p.stem for p in state.glob("*.html")}


def _snapshots(state: Path) -> int:
    return len(list((state / "snapshots").glob("*.json")))


def _origins(state: Path) -> None:
    write_facts(
        state / "origins-facts.json",
        OriginsFacts(scope=REPO, since="2026-09-01", collected_at=NOW.isoformat(), issues=[]),
    )


def _subsystems(state: Path) -> None:
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")


class Loop:
    """A drive that runs `passes` passes; `between[i]` runs after pass i+1."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, state: Path, passes: int) -> None:
        self.state, self.passes, self.sleeps = state, passes, 0
        self.between: dict[int, Any] = {}
        self.clock = [NOW]
        monkeypatch.setattr(triage_batch_cmd, "_now", lambda: self._tick())
        monkeypatch.setattr(triage_batch_cmd, "_sleep", self._nap)

    def _tick(self) -> Any:
        self.clock[0] += timedelta(hours=1)
        return self.clock[0]

    def _nap(self, seconds: float) -> None:
        self.sleeps += 1
        if (hook := self.between.get(self.sleeps)) is not None:
            hook()
        if self.sleeps >= self.passes:
            raise RuntimeError("end of the test loop")

    def run(self) -> tuple[int, str]:
        return _drive(self.state, "--yes", "--interval", "5")


def _spy_measure(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    def measure(checkout: Any, subsystems: Any, *, now_ref: str) -> dict[str, Measured]:
        calls.append(1)
        return {"src": Measured(then=None, now=None)}

    monkeypatch.setattr(triage_architecture_cmd, "measure_subsystems", measure)
    return calls


# ------------------------------------------------------------ the pages a pass writes (R6)


def test_a_yes_pass_writes_the_pages_whose_inputs_exist(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert _written(tmp_path) == {"batches", *PAGES}


def test_origins_and_architecture_wait_for_their_inputs(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _spy_measure(monkeypatch)
    _proposed(world, tmp_path, 1)
    _origins(tmp_path)
    _subsystems(tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert _written(tmp_path) == {"batches", *PAGES, "origins", "architecture"}


def test_plan_mode_writes_no_page(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    _drive(tmp_path)
    assert _written(tmp_path) == set()


def test_a_writer_that_raises_warns_once_per_cause_and_the_pass_completes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)

    def boom(*a: Any, **kw: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(triage_cmd, "write_backlog", boom)
    loop = Loop(monkeypatch, tmp_path, 3)
    _, out = loop.run()
    assert out.count("could not write the Backlog page") == 1 and "disk full" in out
    assert loop.sleeps == 3 and world.passes == [1, 1, 1]  # type: ignore[attr-defined]
    assert "history" in _written(tmp_path)  # the other pages were still written
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b1"]


# ------------------------------------------------------ architecture's measurement (R6)


def test_architecture_measures_on_the_first_pass_and_a_wave_finish_only(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    calls = _spy_measure(monkeypatch)
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True, labels=[])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    _subsystems(tmp_path)
    loop = Loop(monkeypatch, tmp_path, 4)

    def cancel() -> None:
        text = (tmp_path / "judgements.yaml").read_text(encoding="utf-8")
        (tmp_path / "judgements.yaml").write_text(
            text.replace("branch: feat/batch-b1}\n", "branch: feat/batch-b1}\n" + CANCEL),
            encoding="utf-8",
        )

    loop.between[2] = cancel  # pass 3 is the one that finds wave 1 finished
    loop.run()
    assert len(calls) == 2  # pass 1 and pass 3; passes 2 and 4 reuse the measurement
    assert "architecture" in _written(tmp_path)


# ------------------------------------------------------------------- the snapshots (R7)


def test_the_first_pass_stores_a_snapshot_and_an_unchanged_later_one_does_not(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)
    Loop(monkeypatch, tmp_path, 3).run()
    assert _snapshots(tmp_path) == 1


def test_a_second_drive_over_an_unchanged_board_stores_none(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True, labels=[])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    Loop(monkeypatch, tmp_path, 1).run()
    assert _snapshots(tmp_path) == 1
    Loop(monkeypatch, tmp_path, 2).run()  # a new drive: its baseline is the stored one
    assert _snapshots(tmp_path) == 1


def test_a_later_pass_stores_one_exactly_when_a_wave_finishes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    world.issues.update({1: "open", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], draft=True, labels=[])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    loop = Loop(monkeypatch, tmp_path, 5)
    seen: list[int] = []

    def changed() -> None:  # the board changes, no wave finishes
        world.issues[2] = "closed"
        seen.append(_snapshots(tmp_path))

    def cancel() -> None:
        seen.append(_snapshots(tmp_path))
        text = (tmp_path / "judgements.yaml").read_text(encoding="utf-8")
        (tmp_path / "judgements.yaml").write_text(
            text.replace("branch: feat/batch-b1}\n", "branch: feat/batch-b1}\n" + CANCEL),
            encoding="utf-8",
        )

    def quiet() -> None:  # pass 2 changed nothing
        seen.append(_snapshots(tmp_path))

    loop.between.update({1: quiet, 2: changed, 3: cancel})
    loop.run()
    # after pass 1: the baseline; pass 2 changed the facts (pass 3 sees it) but finished no
    # wave; pass 4 found wave 1 finished, and with every batch cancelled the drive ends there
    assert seen == [1, 1, 1] and _snapshots(tmp_path) == 2


# ------------------------------------------------------------- the cloud adapter (R6)


def test_the_cloud_adapters_pass_hands_its_loader_and_ci_none_to_the_backlog(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.driver import CLOUD

    seen: list[dict[str, Any]] = []

    def spy(scope: Any, target: Path, **kw: Any) -> Any:
        seen.append(kw)
        return triage_cmd.PageWritten(target / "backlog.html", "")

    monkeypatch.setattr(triage_cmd, "write_backlog", spy)
    _proposed(world, tmp_path, 1)
    driver = triage_batch_cmd._Driver(
        triage_cmd._scope(REPO, None), tmp_path, named=None, checkouts={REPO.lower(): None},
        max_inflight=1, yes=True, driver=CLOUD,
    )  # fmt: skip
    driver._ci = {REPO: True}
    driver._write_pages(False)
    assert seen[0]["loader"] == driver.runner and seen[0]["ci_none"] == frozenset({REPO})
    host = triage_batch_cmd._Driver(
        triage_cmd._scope(REPO, None), tmp_path, named=None, checkouts={REPO.lower(): None},
        max_inflight=1, yes=True,
    )  # fmt: skip
    host._write_pages(False)
    assert seen[1]["loader"] is None


# ----------------------------------------------- p4-r1: a clone that is not there, said once


def _driver(tmp_path: Path, **kw: Any) -> Any:
    return triage_batch_cmd._Driver(
        triage_cmd._scope(REPO, None), tmp_path, named=None, checkouts={REPO.lower(): None},
        max_inflight=1, yes=True, **kw,
    )  # fmt: skip


def test_a_scope_with_no_usable_clone_says_so_once_and_probes_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    probes: list[int] = []

    def refuse(path: Any, owner_repo: str) -> str:
        probes.append(1)
        return "its origin is not the scope's repo"

    monkeypatch.setattr(triage_batch_cmd, "_checkout_refusal", refuse)
    _proposed(world, tmp_path, 1)
    driver = _driver(tmp_path)
    assert driver._scope_clone() is None and driver._scope_clone() is None
    assert len(probes) == 1
    err = capfd.readouterr().err
    assert err.count("renders with no measurement") == 1 and "error:" not in err


# ------------------------------------- p4-r2, p4-r4: the drive's page memory outlives a process


def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [NOW]

    def tick() -> Any:
        now[0] += timedelta(hours=1)
        return now[0]

    monkeypatch.setattr(triage_batch_cmd, "_now", tick)


def _cancel(state: Path, batch: str = "b1") -> None:
    text = (state / "judgements.yaml").read_text(encoding="utf-8")
    needle = f"branch: feat/batch-{batch}}}\n"
    (state / "judgements.yaml").write_text(text.replace(needle, needle + CANCEL), encoding="utf-8")


def _running(world: World, state: Path, *waves: int) -> None:
    batches = []
    for n, wave in enumerate(waves, 1):
        world.issues[n] = "open"
        world.pr(100 + n, f"feat/batch-b{n}", [n], draft=True, labels=[])
        batches.append(_batch(f"b{n}", n, wave=wave, events=_dispatch_event(f"b{n}")))
    _state(state, world, *batches)


def test_a_new_process_sees_a_wave_that_finished_while_no_driver_ran(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    calls = _spy_measure(monkeypatch)
    _clock(monkeypatch)
    _running(world, tmp_path, 1)
    _subsystems(tmp_path)
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 1 and len(calls) == 1
    _drive(tmp_path, "--once", "--yes")  # a new process measures on its first pass (R6)
    assert _snapshots(tmp_path) == 1 and len(calls) == 2
    _cancel(tmp_path)  # a wave finishes (as a pass's own archive leaves it) between drives
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 2 and len(calls) == 3
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 2 and len(calls) == 4


def test_the_memory_file_is_written_beside_the_state_and_carried_by_the_ref(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
) -> None:  # fmt: skip
    from fr.triage.state_ref import REF_FILES

    _running(world, tmp_path, 1)
    _drive(tmp_path, "--once", "--yes")
    memory = json.loads((tmp_path / "drive-pages.json").read_text(encoding="utf-8"))
    assert memory["unfinished"] == ["1"] and memory["owed"] is False
    assert "drive-pages.json" in REF_FILES


def test_a_backlog_write_that_raises_keeps_the_snapshot_owed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _running(world, tmp_path, 1, 2)
    real = triage_cmd.write_backlog
    broken = [False]

    def flaky(*a: Any, **kw: Any) -> Any:
        if broken[0]:
            raise OSError("disk full")
        return real(*a, **kw)

    monkeypatch.setattr(triage_cmd, "write_backlog", flaky)
    loop = Loop(monkeypatch, tmp_path, 4)
    seen: list[int] = []

    def finish_one() -> None:
        _cancel(tmp_path)
        broken[0] = True

    def mend() -> None:
        seen.append(_snapshots(tmp_path))
        broken[0] = False

    loop.between.update({1: finish_one, 2: mend})
    loop.run()
    assert seen == [1] and _snapshots(tmp_path) == 2  # stored by the pass after the failure


def _memory_file(state: Path, **body: Any) -> Path:
    path = state / "drive-pages.json"
    path.write_text(json.dumps({"schema": 1, "unfinished": ["1"], "owed": False, **body}), "utf-8")
    return path


def test_the_memory_round_trips_and_holds_no_measurement(tmp_path: Path) -> None:
    from fr.triage.drive_pages import PAGES_FILE, PagesMemory, load_memory, save_memory

    save_memory(tmp_path, PagesMemory(frozenset({"2", "1"}), True))
    assert load_memory(tmp_path) == PagesMemory(frozenset({"1", "2"}), True)
    assert set(json.loads((tmp_path / PAGES_FILE).read_text("utf-8"))) == {
        "schema", "unfinished", "owed",
    }  # fmt: skip
    (tmp_path / PAGES_FILE).write_text("{not json", encoding="utf-8")
    assert load_memory(tmp_path) is None
    (tmp_path / PAGES_FILE).unlink()
    assert load_memory(tmp_path) is None


@pytest.mark.parametrize(
    "body",
    [
        {"schema": 2},
        {"schema": "1"},
        {"unfinished": "12"},
        {"unfinished": [1, 2]},
        {"unfinished": None},
        {"owed": "yes"},
        {"owed": 1},
        {"surprise": True},
    ],
)
def test_a_memory_of_the_wrong_shape_is_no_memory(tmp_path: Path, body: dict[str, Any]) -> None:
    from fr.triage.drive_pages import load_memory

    _memory_file(tmp_path, **body)
    assert load_memory(tmp_path) is None


def test_an_old_file_that_still_carries_a_measurement_loads_without_it(tmp_path: Path) -> None:
    from fr.triage.drive_pages import PagesMemory, load_memory

    _memory_file(tmp_path, measured={"src": {"then": None, "now": None}})
    assert load_memory(tmp_path) == PagesMemory(frozenset({"1"}), False)


def _real_measure(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    from fr.triage.architecture import Measure

    calls: list[int] = []

    def measure(checkout: Any, subsystems: Any, *, now_ref: str) -> dict[str, Measured]:
        calls.append(1)
        return {"src": Measured(then=Measure("HEAD", "abc1234", 7, 4242), now=None)}

    monkeypatch.setattr(triage_architecture_cmd, "measure_subsystems", measure)
    return calls


def test_a_planted_measurement_in_an_old_memory_never_reaches_the_page(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _running(world, tmp_path, 1)
    _subsystems(tmp_path)
    plant = {
        "then": {"ref": "HEAD", "commit": "PLANTED_C", "files": "PLANTED_F", "lines": "PLANTED_L"}
    }
    _memory_file(tmp_path, measured={"src": {**plant, "now": None}})
    calls = _real_measure(monkeypatch)
    _drive(tmp_path, "--once", "--yes")
    page = (tmp_path / "architecture.html").read_text(encoding="utf-8")
    assert "PLANTED" not in page and "4242" in page
    assert len(calls) == 1  # measured afresh, as a new process's first pass does


def test_the_pages_of_later_passes_render_the_measurement_without_taking_it_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _running(world, tmp_path, 1)
    _subsystems(tmp_path)
    calls = _real_measure(monkeypatch)
    loop = Loop(monkeypatch, tmp_path, 3)
    seen: list[bool] = []
    loop.between.update(
        {n: lambda: seen.append("4242" in (tmp_path / "architecture.html").read_text("utf-8"))
         for n in (1, 2)}
    )  # fmt: skip
    loop.run()
    assert seen == [True, True] and len(calls) == 1


def test_a_scope_with_no_usable_clone_renders_dashes_and_never_measures(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _running(world, tmp_path, 1)
    _subsystems(tmp_path)
    calls = _real_measure(monkeypatch)
    monkeypatch.setattr(triage_batch_cmd, "_checkout_refusal", lambda p, r: "not a clone")
    driver = _driver(tmp_path)
    driver._measured = {"src": Measured(then=None, now=None)}  # a remembered one is never shown
    driver._write_pages(False)
    page = (tmp_path / "architecture.html").read_text(encoding="utf-8")
    assert "4242" not in page and "\u2014" in page and calls == []


def test_a_malformed_memory_means_the_first_pass_decisions_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    calls = _real_measure(monkeypatch)
    _clock(monkeypatch)
    _running(world, tmp_path, 1)
    _subsystems(tmp_path)
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 1 and len(calls) == 1
    (tmp_path / "drive-pages.json").write_text('{"schema": 1, "unfinished": 5}', "utf-8")
    _drive(tmp_path, "--once", "--yes")  # baseline compared: the board is the stored one
    assert _snapshots(tmp_path) == 1 and len(calls) == 2
    (tmp_path / "drive-pages.json").write_text("garbage", "utf-8")
    world.issues[2] = "closed"  # the board differs from the latest snapshot
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 2 and len(calls) == 3


def test_a_second_drive_over_a_changed_board_stores_none_unless_a_wave_finished(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _clock(monkeypatch)
    _running(world, tmp_path, 1)
    world.issues[2] = "open"
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 1
    world.issues[2] = "closed"  # the board changed; the memory file is present
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 1
    _cancel(tmp_path)  # a wave finished
    _drive(tmp_path, "--once", "--yes")
    assert _snapshots(tmp_path) == 2
