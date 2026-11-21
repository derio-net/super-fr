"""Phase 5's review findings (spec 2026-11-19-wave-merge-queue): approved drafts are
readied (p5-r1), an unconfigured repo is visible (p5-r2), an ejected close-out or archive
entry goes back to its session (p5-r3), no entry lands off the default branch (p5-r4, r8)
and `order` only breaks ties (p5-r6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.triage.model import Batch, load_judgements
from fr.triage.views import NEED_LABELS, needs_you
from fr.triage.wave_queue import (
    QueueConfig,
    QueueSnapshot,
    _by_readiness,
    _Cand,
    plan_queue,
)

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive import REPO as DRIVE_REPO
from tests.unit.test_triage_batch_drive_cmd import (
    CLOSEOUT_B1,
    DriveCheckout,
    MessengerRunner,
    RecordingQueue,
    World,
    _batch,
    _closing,
    _conflict_error,
    _dispatch_event,
    _drive,
    _lines,
    _pr_open,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    _state,
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    runner_fixture,  # noqa: F401 - registered as `runner`
    triage_batch_cmd,
    world_fixture,  # noqa: F401 - registered as `world`
)
from tests.unit.test_triage_collected_closeout_drive import (
    CMD_ITEM,
    _started,
)
from tests.unit.test_wave_queue_planner import _batch as _pbatch
from tests.unit.test_wave_queue_planner import _live, _qs

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------ p5-r1


@pytest.mark.parametrize("land", ["push", "merge"])
def test_p5_r1_an_approved_green_draft_batch_pr_is_readied_when_the_queue_builds_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, land: str
) -> None:
    """merge-train-safety R1: a labelled green draft is readied and merged, whichever way
    the queue lands it."""
    world.config = {"queue": {"ci": "push", "land": land}}
    _pr_open(world, tmp_path, draft=True)  # approved-fr by default

    code, out = _drive(tmp_path, "--once", "--yes")
    assert code in (0, 3), out
    assert "pr_ready 101" not in world.calls  # admitting readies nothing: building does
    entry = RecordingQueue.ports.entry_of("b1")  # the executor's build of the entry

    assert entry is not None and entry.pr == 101
    assert world.calls.count("pr_ready 101") == 1, out


def test_p5_r1_a_draft_that_is_not_approved_is_never_readied(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path, draft=True, labels=[])
    _drive(tmp_path, "--once", "--yes")
    assert world.queue_plans == [] or not any(a.kind == "queue-open" for a in world.queue_plans)
    assert "pr_ready 101" not in world.calls


# ------------------------------------------------------------------ p5-r2


def _unconfigured(world: World, tmp_path: Path) -> Any:
    _pr_open(world, tmp_path)
    return load_judgements(tmp_path / "judgements.yaml")


def test_p5_r2_a_repo_with_no_queue_block_is_a_need_naming_what_to_add(
    tmp_path: Path, world: World
) -> None:
    judgements = _unconfigured(world, tmp_path)
    needs = [n for n in needs_you(world.facts(), judgements) if n.kind == "queue-unconfigured"]
    (need,) = needs
    assert need.ref == DRIVE_REPO and DRIVE_REPO in need.text
    assert "queue: {ci: push}" in need.text and "fr-queue/**" in need.text
    assert "queue-unconfigured" in NEED_LABELS


def test_p5_r2_a_configured_repo_has_no_such_need(tmp_path: Path, world: World) -> None:
    world.config = {"queue": {"ci": "push"}}
    judgements = _unconfigured(world, tmp_path)
    assert not [n for n in needs_you(world.facts(), judgements) if n.kind == "queue-unconfigured"]


def test_p5_r2_the_facts_only_board_says_the_queue_holds_it_not_merge_ready(
    tmp_path: Path, world: World
) -> None:
    from fr.triage.kanban import HINT_MERGE_READY, HINT_QUEUE_UNCONFIGURED, build_board

    judgements = _unconfigured(world, tmp_path)
    card = build_board(world.facts(), judgements, {}).card("b1")
    assert card.hint == HINT_QUEUE_UNCONFIGURED != HINT_MERGE_READY
    world.config = {"queue": {"ci": "push"}}
    assert build_board(world.facts(), judgements, {}).card("b1").hint == HINT_MERGE_READY


# ------------------------------------------------------------------ p5-r3


def test_p5_r3_an_ejected_closeout_entry_goes_back_to_the_closeout_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    messenger = MessengerRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: messenger)
    _started(world, tmp_path, "b1", "b2", checkout=checkout)
    RecordingQueue.script[900] = _conflict_error(
        head="sha-900", bid="closeout#900", number=900)  # fmt: skip

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code in (0, 3), out
    ((item, text),) = messenger.messages
    assert item == CMD_ITEM and "PR #900" in text
    backs = {
        b.id: [(e.item, e.head, e.delivered) for e in b.events if e.kind == "closeout_handback"]
        for b in load_judgements(tmp_path / "judgements.yaml").batches
    }
    assert backs == dict.fromkeys(("b1", "b2"), [(CMD_ITEM, "sha-900", "session")])
    _drive(tmp_path, "--once", "--yes")  # R27's one hand-back: not again at this head
    assert len(messenger.messages) == 1


def test_p5_r3_an_ejected_archive_entry_goes_back_to_its_batchs_closeout_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    messenger = MessengerRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: messenger)
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    world.checks[201] = [{"name": "test", "bucket": "pass"}]
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _closeout_r1()))
    messenger.status[CLOSEOUT_B1] = "idle"
    RecordingQueue.script[201] = _conflict_error(
        head="sha-201", bid="archive#201", number=201)  # fmt: skip

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code in (0, 3), out
    ((target, text),) = messenger.messages
    assert target == CLOSEOUT_B1 and "PR #201" in text
    assert _lines(out, "queue-eject"), out


def _closeout_r1() -> str:
    from tests.unit.test_triage_batch_drive_cmd import _CLOSEOUT_R1

    return _CLOSEOUT_R1


# ------------------------------------------------------------------ p5-r4, p5-r8


def test_p5_r4_a_housekeeping_pr_based_on_another_branch_is_never_an_entry(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = {"queue": {"ci": "push"}}
    _pr_open(world, tmp_path)
    world.prs[101]["labels"] = []
    world.pr(300, "chore/ops-x", [], base="release", labels=["approved-fr"])
    world.checks[300] = [{"name": "test", "bucket": "pass"}]

    code, out = _drive(tmp_path, "--once", "--yes")

    assert not [k for a in world.queue_plans for k in a.entries if k == "housekeeping#300"]
    assert "housekeeping#300) is based on release, not main" in out


def _planner(base: str) -> QueueSnapshot:
    batch = _pbatch("b1", 1)
    return _qs([batch], {"b1": "pr-open"}, live={"b1": _live(101, "head-b1", base=base)},
               default="main")  # fmt: skip


def test_p5_r8_a_batch_pr_based_on_another_branch_is_no_entry_and_is_a_need() -> None:
    plan = plan_queue(_planner("release"))
    assert plan.entries == () and not [a for a in plan.actions if a.kind == "queue-open"]
    (need,) = [a for a in plan.actions if a.kind == "queue-need"]
    assert "based on release, not main" in need.detail and "#101" in need.detail


def test_p5_r8_a_batch_pr_based_on_the_default_branch_opens_the_queue() -> None:
    plan = plan_queue(_planner("main"))
    assert [a.kind for a in plan.actions] == ["queue-open"]


def test_p5_r8_an_unread_default_branch_checks_nothing() -> None:
    qs = _planner("release")
    plan = plan_queue(QueueSnapshot(**{**qs.__dict__, "default": ""}))
    assert [a.kind for a in plan.actions] == ["queue-open"]


# ------------------------------------------------------------------ p5-r6


def test_p5_r6_order_only_breaks_ties_among_entries_ready_together() -> None:
    early = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
    late = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    cands = [
        _Cand("a", 1, late, order=1),  # lowest order, ready last
        _Cand("b", 1, early, order=9),  # highest order, ready first
        _Cand("c", 1, early, order=2),  # ready with b: order decides
    ]
    assert [c.key for c in _by_readiness(cands)] == ["c", "b", "a"]


_ = (Batch, QueueConfig)
