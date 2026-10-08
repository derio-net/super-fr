"""The driver adapter chooses the runner and owns `post_merge` (spec 2026-10-07-cloud-triage
R10, R20, §E, Test Plan 9).

One `.fr/triage.yaml` names `launch.runner: herdr` and a `post_merge`: the host driver
dispatches through herdr and runs `post_merge` (as today); the cloud driver dispatches
every batch through `claude-cloud` and runs neither `post_merge` nor
`post_merge_restart`. A batch whose explicit `launch.runner` is not the driver's is
reported (`warn`) and not dispatched. The world, clone and runner fakes are
`test_triage_batch_drive_cmd`'s.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
from fr.commands import triage_batch_cmd
from fr.triage.driver import CLOUD, CLOUD_RUNNER, HOST, CloudDriver, Driver, HostDriver
from fr.triage.errors import TriageError
from fr.triage.model import Scope, load_judgements

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    _cursor,
    _drive,
    _events,
    _lines,
    _state,
    checkout_fixture,
    world_fixture,
)

CONFIG = {
    "defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "claude-opus-5-5"}},
    "post_merge": ["./scripts/install.sh"],
    "post_merge_restart": "idle",
}


class Runners:
    """`load_runner` by name: one FakeRunner per runner name, every name asked recorded."""

    def __init__(self) -> None:
        self.by_name: dict[str, FakeRunner] = {}
        self.asked: list[str] = []

    def __call__(self, name: str) -> FakeRunner:
        self.asked.append(name)
        return self.by_name.setdefault(name, FakeRunner())

    def dispatched(self) -> dict[str, list[str]]:
        return {n: [i.id for i in r.dispatched] for n, r in self.by_name.items() if r.dispatched}


@pytest.fixture
def runners(monkeypatch: pytest.MonkeyPatch) -> Runners:
    found = Runners()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", found)
    return found


def _batch(bid: str, n: int, *, launch: str = "{}", events: str = "") -> str:
    ev = f"    events:\n{events}" if events else ""
    return (
        f'  - id: {bid}\n    title: {bid}\n    ids: ["super-fr#{n}"]\n    wave: 1\n'
        f"    launch: {launch}\n{ev}"
    )


def _proposed(world: World, tmp_path: Path, *, launch: str = "{}") -> None:
    world.config = CONFIG
    world.issues[1] = "open"
    _state(tmp_path, world, _batch("b1", 1, launch=launch))


def _merged(
    world: World, tmp_path: Path, checkout: DriveCheckout, runner: str, launch: str = "{}"
) -> None:
    world.config = CONFIG
    world.issues[1] = "closed"
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    event = (f"      - {{kind: dispatch, at: 2026-10-01T10:00:00Z, runner: {runner}, "
             "handle: h, branch: feat/batch-b1}\n")  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, launch=launch, events=event))
    _cursor(checkout, "2026-10-01-b1", "feat/batch-b1")
    checkout.released = True


def _cloud_pass(tmp_path: Path, max_inflight: int = 3) -> tuple[bool, Any, list[str]]:
    driver = triage_batch_cmd._Driver(
        Scope(kind="repo", target=REPO),
        tmp_path,
        named=None,
        checkouts={},
        max_inflight=max_inflight,
        yes=True,
        driver=CLOUD,
    )
    return driver.run_pass()


# ----------------------------------------------------------------- the adapters


def test_the_two_adapters_are_drivers() -> None:
    assert isinstance(HOST, HostDriver) and isinstance(CLOUD, CloudDriver)
    assert isinstance(HOST, Driver) and isinstance(CLOUD, Driver)
    assert (HOST.kind, CLOUD.kind) == ("host", "cloud")
    assert CLOUD_RUNNER == "claude-cloud"


def test_the_host_adapter_keeps_the_batchs_runner_and_the_cloud_one_names_its_own() -> None:
    from fr.triage.model import Batch

    plain = Batch.model_validate({"id": "b1", "title": "t", "ids": ["r#1"]})
    herdr = Batch.model_validate(
        {"id": "b2", "title": "t", "ids": ["r#2"], "launch": {"runner": "herdr"}}
    )
    assert HOST.runner_for(plain) is None  # the batch's, else the repo's default
    assert HOST.runner_for(herdr, "vk") == "vk"  # `--to` wins, as today
    assert HOST.refusal(herdr) is None
    assert CLOUD.runner_for(plain) == "claude-cloud"
    assert CLOUD.refusal(plain) is None
    assert "herdr" in (CLOUD.refusal(herdr) or "")
    with pytest.raises(TriageError):
        CLOUD.runner_for(herdr)
    with pytest.raises(TriageError):
        CLOUD.runner_for(plain, "herdr")


# --------------------------------------------------------- dispatch, per driver


def test_a_host_scope_dispatches_through_the_repos_runner(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners
) -> None:
    _proposed(world, tmp_path)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert runners.dispatched() == {"herdr": [f"{REPO}/run/batch-b1"]}
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    assert batch.events[-1].runner == "herdr"  # type: ignore[union-attr]


def test_a_cloud_scope_dispatches_through_claude_cloud_whatever_the_repo_names(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners
) -> None:
    _proposed(world, tmp_path)

    acted, _, _ = _cloud_pass(tmp_path)

    assert acted
    assert runners.dispatched() == {"claude-cloud": [f"{REPO}/run/batch-b1"]}
    assert "herdr" not in runners.asked
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    assert batch.events[-1].runner == "claude-cloud"  # type: ignore[union-attr]


def test_a_batch_naming_another_runner_is_reported_and_not_dispatched(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _proposed(world, tmp_path, launch="{runner: herdr}")

    acted, summary, _ = _cloud_pass(tmp_path)

    assert not acted and runners.dispatched() == {}
    out = capsys.readouterr().out
    (line,) = _lines(out, "held")  # a hold the planner sees (p4-r1)
    assert line.startswith("held b1:") and "herdr" in line and "claude-cloud" in line
    assert _lines(out, "dispatch") == []
    assert summary.pending == 1 and summary.in_flight == 0
    assert _events(tmp_path, "b1") == []


def test_a_refused_batch_takes_no_in_flight_slot_from_the_next(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners
) -> None:
    """p4-r1: with --max-inflight 1, a refused batch first in order is a hold, not an
    occupant, so the next batch is dispatched in the same pass."""
    world.config = CONFIG
    world.issues[1] = world.issues[2] = "open"
    _state(tmp_path, world, _batch("a1", 1, launch="{runner: herdr}") + _batch("b2", 2))

    acted, summary, _ = _cloud_pass(tmp_path, max_inflight=1)

    assert acted
    assert runners.dispatched() == {"claude-cloud": [f"{REPO}/run/batch-b2"]}
    assert summary.in_flight == 1 and summary.pending == 1


# ------------------------------------------------------------ post_merge (R20)


def test_the_host_runs_post_merge_and_restarts_after_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners
) -> None:
    _merged(world, tmp_path, checkout, "herdr")

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert checkout.commands == [["./scripts/install.sh"]]
    assert _events(tmp_path, "b1") == ["dispatch", "post_merge", "closeout"]
    assert runners.dispatched() == {"herdr": [f"{REPO}/run/closeout-b1"]}


def test_the_cloud_runs_neither_post_merge_nor_its_restart(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _merged(world, tmp_path, checkout, "claude-cloud")

    acted, _, _ = _cloud_pass(tmp_path)

    assert acted
    assert checkout.commands == []
    assert _events(tmp_path, "b1") == ["dispatch", "closeout"]
    assert runners.dispatched() == {"claude-cloud": [f"{REPO}/run/closeout-b1"]}
    assert "restart" not in capsys.readouterr().out


def test_a_close_out_another_drivers_runner_owns_is_reported_and_left_to_it(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """p4-r10 (§E): a batch dispatched with an explicit runner this driver lacks is closed
    out by that runner's driver: reported, never dispatched through the foreign runner."""
    _merged(world, tmp_path, checkout, "herdr", launch="{runner: herdr}")

    _cloud_pass(tmp_path)

    assert runners.dispatched() == {}  # herdr may be probed for its session, never used
    assert _events(tmp_path, "b1") == ["dispatch"]
    out = capsys.readouterr().out
    (line,) = _lines(out, "closeout")
    assert "herdr" in line and "left to" in line
