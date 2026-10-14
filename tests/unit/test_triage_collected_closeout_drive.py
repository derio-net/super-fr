"""The driver's collected close-out (spec 2026-10-14-exit-gates R15, R27, §D).

`drive_pass` step 2 plans at most ONE `closeout` per repo, covering every landed batch
that is not gated and not closed out, and none while a previous collected close-out is
under way. `attributed` names the shared head for every member, a batch with no run
included. A batch whose archive would hold is a need, never a member. The pass is pure:
these tests hand-build the `Snapshot`.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.batch_drive import (
    attributed,
    closeout_event,
    collected_item_id,
    drive_pass,
)
from fr.triage.model import load_judgements

from tests.unit.test_triage_batch_closeout_cmd import _landed as _world_landed
from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive import NOW, REPO, _dispatched, _kinds, _live, _snap
from tests.unit.test_triage_batch_drive_cmd import (
    DriveCheckout,
    World,
    _drive,
    _lines,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    runner_fixture,  # noqa: F401 - registered as `runner`
    world_fixture,  # noqa: F401 - registered as `world`
)

DAY = NOW.date().isoformat()
FIRST = f"chore/closeout-{DAY}-1"


def _landed(*bids: str, **kw: Any) -> Any:
    batches = [_dispatched(b, i, events=kw.pop(f"{b}_events", [])) for i, b in enumerate(bids, 1)]
    merged_at = {b: NOW - timedelta(hours=1) for b in bids}
    return _snap(batches, dict.fromkeys(bids, "merged"), merged_at=merged_at, **kw)


def _recorded(archive: str = FIRST, run: str | None = "r", **kw: Any) -> list[dict[str, Any]]:
    return [{"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake",
             "handle": f"{REPO}/run/{archive.removeprefix('chore/')}", "run": run,
             "archive": archive, **kw}]  # fmt: skip


# ------------------------------------------------------------- step 2 (R15)


def test_three_landed_batches_in_one_repo_get_one_collected_closeout() -> None:
    plan = drive_pass(_landed("a", "b", "c"))

    closeouts = [a for a in plan.actions if a.kind == "closeout"]
    assert len(closeouts) == 1
    (action,) = closeouts
    assert action.items == ("a", "b", "c")
    assert action.key == f"closeout-{DAY}-1"
    assert collected_item_id(REPO, action.key) in action.detail
    assert plan.summary.closing == 3


def test_two_repos_get_one_collected_closeout_each() -> None:
    other = "derio-net/other"
    snap = _landed("a", "b", repos={"a": REPO, "b": other})
    plan = drive_pass(snap)
    assert sorted(a.items for a in plan.actions if a.kind == "closeout") == [("a",), ("b",)]


def test_none_starts_while_a_previous_collected_closeout_is_under_way() -> None:
    snap = _landed("a", "b", a_events=_recorded())
    plan = drive_pass(snap)
    assert [a for a in plan.actions if a.kind == "closeout"] == []
    assert plan.summary.closing == 2  # b waits; a's close-out is still closing


def test_the_next_collected_closeout_takes_the_next_number_once_the_last_merged() -> None:
    snap = _landed("a", "b", a_events=_recorded(archived=900))
    (action,) = [a for a in drive_pass(snap).actions if a.kind == "closeout"]
    assert action.items == ("b",) and action.key == f"closeout-{DAY}-2"


def test_a_batch_whose_archive_would_hold_is_a_need_never_a_member() -> None:
    snap = _landed("a", "b", closeout_holds={"b": "Test Plan step 2 has no outcome"})
    plan = drive_pass(snap)

    assert [a.items for a in plan.actions if a.kind == "closeout"] == [("a",)]
    assert ("closeout-held", "b") in _kinds(plan.actions)
    assert plan.summary.blocked == 1


def test_a_gated_batch_never_joins_a_collected_closeout() -> None:
    from fr.triage.batch_drive import GateLedger

    snap = _landed("a", "b", ledgers={"b": GateLedger(pr=7, labels=frozenset({"gate:tester"}))})
    assert [a.items for a in drive_pass(snap).actions if a.kind == "closeout"] == [("a",)]


# -------------------------------------------------------- attributed (§D)


def test_attributed_accepts_the_shared_head_for_a_trusted_author_even_with_no_run() -> None:
    batch = _dispatched("d", 1, skill="debug", events=_recorded(run=None))
    event = closeout_event(batch)
    assert event is not None
    shared = _live(900, "h900", head_ref=FIRST, trusted=True)
    assert attributed(shared, batch, event)
    assert not attributed(_live(901, "h", head_ref=FIRST, trusted=False), batch, event)
    other = _live(902, "h", head_ref=f"chore/closeout-{DAY}-2", trusted=True)
    assert not attributed(other, batch, event)


# ------------------------------------------------------ the executor (§E)

CMD_DAY = "2026-10-02"  # the drive tests' NOW


def test_the_driver_starts_one_session_for_three_batches_and_records_each_first(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _world_landed(world, tmp_path, "b1", "b2", "b3")
    checkout.released = True

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    (item,) = runner.dispatched
    assert item.id == f"{REPO}/run/closeout-{CMD_DAY}-1"
    assert "fr triage batch closeout b1 b2 b3 --yes" in item.payload["brief"]
    archives = {
        b.id: [e.archive for e in b.events if e.kind == "closeout"]  # type: ignore[union-attr]
        for b in load_judgements(tmp_path / "judgements.yaml").batches
    }
    assert archives == dict.fromkeys(("b1", "b2", "b3"), [f"chore/closeout-{CMD_DAY}-1"])
    # the next pass starts nothing: the collected close-out is under way
    code, out = _drive(tmp_path, "--once", "--yes")
    assert len(runner.dispatched) == 1 and _lines(out, "closeout") == []


def test_a_batch_whose_archive_would_hold_is_named_and_not_started(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.commands import triage_batch_cmd
    from fr.triage.ledger import CloseoutRead

    reads = {"feat/batch-b2": CloseoutRead("r2", (2,))}
    monkeypatch.setattr(
        triage_batch_cmd, "closeout_read",
        lambda c, ref, branch, repo: reads.get(branch, CloseoutRead(None)),
    )  # fmt: skip
    _world_landed(world, tmp_path, "b1", "b2")
    checkout.released = True

    code, out = _drive(tmp_path, "--once", "--yes")

    (held,) = _lines(out, "closeout-held")
    assert "b2" in held and "Test Plan step(s) 2 of run r2" in held
    (item,) = runner.dispatched
    assert "closeout b1 --yes" in item.payload["brief"]
