"""`fr triage batch drive` reports idle sessions (driver-sessions §D, R7).

The world, clone and runner are `test_triage_batch_drive_cmd`'s; the inspecting runner is a
`FakeRunner` that also answers `session_statuses`. Nothing here touches a real herdr pane.
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
    _lines,
    _state,
    checkout_fixture,
    git_checkout_fixture,
    runner_fixture,
    sleeps_fixture,
    world_fixture,
)

BATCH_ITEM = f"{REPO}/run/batch-b1"
CLOSEOUT_ITEM = f"{REPO}/run/closeout-b1"


class InspectingRunner(FakeRunner):
    """A runner that reports session state (`SessionInspector`)."""

    def __init__(self) -> None:
        super().__init__()
        self.status: dict[str, str] = {}
        self.asked: list[list[str]] = []

    def session_statuses(self, items: Any) -> dict[str, str]:
        self.calls.append("session_statuses")
        self.asked.append([i.id for i in items])
        return {i.id: self.status.get(i.id, "absent") for i in items}


@pytest.fixture(name="inspector")
def inspector_fixture(monkeypatch: pytest.MonkeyPatch) -> InspectingRunner:
    fake = InspectingRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


def _dispatched(world: World, tmp_path: Path, *, pr: bool = False) -> None:
    world.issues[1] = "open"
    if pr:
        world.pr(101, "feat/batch-b1", [1])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))


def _driver(tmp_path: Path) -> Any:
    return triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={},
        max_inflight=4, yes=True, scope_args=["--repo", REPO, "--dir", str(tmp_path)],
    )  # fmt: skip


def test_an_idle_batch_session_with_no_pr_is_reported_with_its_focus_command(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    (warn,) = [ln for ln in _lines(out, "warn") if "idle for" in ln]
    assert f"{BATCH_ITEM} has sat idle for" in warn and "min with no PR" in warn
    assert "fr triage batch focus b1" in warn


def test_it_is_reported_once_across_passes_and_never_ends_the_drive(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = "idle"
    driver = _driver(tmp_path)
    driver.run_pass()
    driver.run_pass()
    seen = capsys.readouterr()
    assert (seen.out + seen.err).count("has sat idle for") == 1


@pytest.mark.parametrize("status", ["working", "blocked", "absent", "done-not"])
def test_a_session_that_is_not_idle_is_not_reported(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner,
    status: str,
) -> None:  # fmt: skip
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = status
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "has sat" not in out


def test_only_candidates_are_probed(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    # a PR exists: the session is not a candidate, so the runner is never asked
    _dispatched(world, tmp_path, pr=True)
    inspector.status[BATCH_ITEM] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "has sat" not in out and inspector.asked == []


def test_a_young_dispatch_is_not_a_candidate(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = "idle"
    world.config = {"idle_session_minutes": 60 * 24 * 365}
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "has sat" not in out and inspector.asked == []


def test_without_yes_no_runner_is_read(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = "idle"
    code, out = _drive(tmp_path, "--once")
    assert code in (0, 3), out
    assert inspector.asked == []


def test_a_runner_that_cannot_inspect_is_skipped(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _dispatched(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "has sat" not in out


def test_a_refusing_or_raising_runner_is_soft(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    _dispatched(world, tmp_path)
    inspector.status[BATCH_ITEM] = "idle"
    inspector.preflight = lambda items: "no herdr"  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "has sat" not in out and inspector.asked == []

    inspector.preflight = lambda items: None  # type: ignore[method-assign]

    def boom(items: Any) -> Any:
        raise RuntimeError("tab list failed")

    inspector.session_statuses = boom  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out


def test_an_idle_closeout_with_no_archive_pr_is_reported(
    tmp_path: Path, world: World, checkout: DriveCheckout, inspector: InspectingRunner
) -> None:
    world.issues[1] = "closed"
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(hours=3)).isoformat())  # fmt: skip
    closeout = (
        f"      - {{kind: closeout, at: {(NOW - timedelta(hours=2)).isoformat()}, "
        "runner: fake, handle: h}\n"
    )
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    inspector.status[CLOSEOUT_ITEM] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    (warn,) = [ln for ln in _lines(out, "warn") if "idle for" in ln]
    assert f"{CLOSEOUT_ITEM} has sat idle for " in warn and "min with no archive PR" in warn
    assert "fr triage batch focus b1 --closeout" in warn
