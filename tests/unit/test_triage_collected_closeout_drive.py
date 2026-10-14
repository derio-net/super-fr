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


# ------------------------------------------------ step 3: ready, merge, hand back


ITEM = f"{REPO}/run/closeout-{DAY}-1"


def _under_way(pr: Any, *bids: str, handbacks: list[dict[str, Any]] | None = None) -> Any:
    kw: dict[str, Any] = {f"{b}_events": [*_recorded(), *(handbacks or [])] for b in bids}
    return _landed(*bids, archives={REPO: (pr,)}, **kw)


def _shared(**kw: Any) -> Any:
    kw.setdefault("mergeable", "MERGEABLE")
    return _live(900, kw.pop("head", "h900"), head_ref=FIRST, trusted=True, base="main", **kw)


def test_a_green_mergeable_collected_pr_is_readied_and_merged_once_for_every_member() -> None:
    plan = drive_pass(_under_way(_shared(draft=True), "a", "b", "c"))

    (merge,) = [a for a in plan.actions if a.kind == "archive"]
    assert (merge.pr, merge.head, merge.items, merge.draft) == (900, "h900", ("a", "b", "c"), True)


def test_a_collected_pr_not_yet_known_mergeable_waits() -> None:
    plan = drive_pass(_under_way(_shared(mergeable="UNKNOWN"), "a"))
    assert [a for a in plan.actions if a.kind in ("archive", "closeout-handback")] == []


def test_a_conflicting_collected_pr_is_handed_back_once_to_its_session() -> None:
    plan = drive_pass(_under_way(_shared(mergeable="CONFLICTING"), "a", "b"))

    (back,) = [a for a in plan.actions if a.kind == "closeout-handback"]
    assert (back.key, back.head, back.items, back.checks) == (ITEM, "h900", ("a", "b"),
                                                              ("merge conflict",))  # fmt: skip
    assert "archive" not in [k for k, _ in _kinds(plan.actions)]


def test_a_red_collected_pr_is_handed_back_naming_its_failing_checks() -> None:
    pr = _shared(checks="failing", failing=("lint", "test"))
    (back,) = [a for a in drive_pass(_under_way(pr, "a")).actions if a.kind == "closeout-handback"]
    assert back.checks == ("lint", "test")


def _handback(head: str, delivered: str = "session") -> dict[str, Any]:
    return {"kind": "closeout_handback", "at": "2026-10-02T11:30:00Z", "item": ITEM, "pr": 900,
            "head": head, "reason": "merge conflict", "delivered": delivered}  # fmt: skip


def test_a_hand_back_at_this_head_is_never_repeated() -> None:
    snap = _under_way(_shared(mergeable="CONFLICTING"), "a", "b", handbacks=[_handback("h900")])
    kinds = [k for k, _ in _kinds(drive_pass(snap).actions)]
    assert "closeout-handback" not in kinds and "closeout-stuck" not in kinds


def test_a_second_failure_at_a_later_head_is_a_stuck_need() -> None:
    """R27: the budget is ONE per close-out item, counted across its members: a hand-back
    recorded on a only still spends b's."""
    snap = _landed("a", "b", archives={REPO: (_shared(mergeable="CONFLICTING", head="h901"),)},
                   a_events=[*_recorded(), _handback("h900")], b_events=_recorded())  # fmt: skip
    plan = drive_pass(snap)

    (stuck,) = [a for a in plan.actions if a.kind == "closeout-stuck"]
    assert stuck.key == ITEM and stuck.items == ("a", "b")
    assert plan.summary.blocked == 1


def test_a_hand_back_no_session_took_is_a_stuck_need_at_once() -> None:
    snap = _under_way(_shared(mergeable="CONFLICTING"), "a", handbacks=[_handback("h900", "none")])
    assert "closeout-stuck" in [k for k, _ in _kinds(drive_pass(snap).actions)]


def test_the_closeout_hand_back_budget_is_its_own_and_conflict_decisions_is_unchanged() -> None:
    from fr.triage.batch_drive import HANDBACKS_PER_DISPATCH, conflict_decision

    assert HANDBACKS_PER_DISPATCH == 2
    assert conflict_decision([], "h", ["p"], []).kind == "handback"


# ------------------------------------------------------- the event (schema 10)


def test_the_closeout_handback_event_moves_the_judgements_schema() -> None:
    from fr.triage.model import JUDGEMENTS_READS, JUDGEMENTS_SCHEMA, Judgements

    assert JUDGEMENTS_SCHEMA == 10 and JUDGEMENTS_READS[-1] == 10
    batch = {"id": "a", "title": "a", "ids": ["super-fr#1"],
             "events": [*_recorded(), _handback("h900")]}  # fmt: skip
    judged = {"tiers": [{"n": 1, "title": "Now"}], "issues": {"super-fr#1": {"tier": 1}}}
    got = Judgements.model_validate({"schema": 10, **judged, "batches": [batch]})
    assert got.batches[0].events[-1].kind == "closeout_handback"
    with pytest.raises(ValueError, match="schema"):
        Judgements.model_validate({"schema": 9, **judged, "batches": [batch]})
    older = {**batch, "events": _recorded()}
    assert Judgements.model_validate({"schema": 9, **judged, "batches": [older]}).schema_ == 9


# ------------------------------------------------- step 3, executed (§D)

CMD_BRANCH = f"chore/closeout-{CMD_DAY}-1"
CMD_ITEM = f"{REPO}/run/closeout-{CMD_DAY}-1"


def _started(world: World, tmp_path: Path, *bids: str, **pr: Any) -> Path:
    """*bids* landed, their collected close-out recorded and its PR #900 open."""
    from tests.unit.test_triage_batch_drive_cmd import _batch, _dispatch_event, _state

    rec = (f"      - {{kind: closeout, at: '2026-10-02T11:00:00Z', runner: fake, "
           f"handle: {CMD_ITEM}, archive: {CMD_BRANCH}}}\n")  # fmt: skip
    batches = []
    for i, bid in enumerate(bids, 1):
        world.issues[i] = "closed"
        world.pr(100 + i, f"feat/batch-{bid}", [i], state="MERGED",
                 merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
        batches.append(_batch(bid, i, events=_dispatch_event(bid) + rec))
    world.pr(900, CMD_BRANCH, [], **{"mergeable": "MERGEABLE", **pr})
    return _state(tmp_path, world, *batches)


def test_the_driver_readies_and_merges_the_collected_pr_and_records_every_member(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _started(world, tmp_path, "b1", "b2", draft=True)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert world.calls.index("pr_ready 900") < world.calls.index("pr_merge 900")
    assert world.calls.count("pr_merge 900") == 1
    archived = {b.id: closeout_event(b).archived  # type: ignore[union-attr]
                for b in load_judgements(tmp_path / "judgements.yaml").batches}  # fmt: skip
    assert archived == {"b1": 900, "b2": 900}


def test_a_conflicting_collected_pr_is_handed_back_once_and_recorded_on_each_member(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_batch_cmd

    from tests.unit.test_triage_batch_drive_cmd import MessengerRunner

    messenger = MessengerRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: messenger)
    _started(world, tmp_path, "b1", "b2", mergeable="CONFLICTING")

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    ((item, text),) = messenger.messages
    assert item == CMD_ITEM and CMD_BRANCH in text and "PR #900" in text
    backs = {
        b.id: [(e.item, e.head) for e in b.events if e.kind == "closeout_handback"]  # type: ignore[union-attr]
        for b in load_judgements(tmp_path / "judgements.yaml").batches
    }
    assert backs == dict.fromkeys(("b1", "b2"), [(CMD_ITEM, "sha-900")])
    assert "pr_merge 900" not in world.calls
    # a second pass at the same head hands nothing back again
    _drive(tmp_path, "--once", "--yes")
    assert len(messenger.messages) == 1


def test_a_hand_back_no_session_took_is_a_need_on_the_board(tmp_path: Path, world: World) -> None:
    from fr.triage.model import load_judgements as load
    from fr.triage.views import NEED_LABELS, needs_you

    target = _started(world, tmp_path, "b1", "b2", mergeable="CONFLICTING")
    path = target / "judgements.yaml"
    none = (f"      - {{kind: closeout_handback, at: '2026-10-02T11:30:00Z', item: {CMD_ITEM}, "
            "pr: 900, head: sha-900, reason: merge conflict, delivered: none}\n")  # fmt: skip
    text = path.read_text("utf-8").replace("schema: 3\n", "schema: 10\n", 1)
    path.write_text(text.replace(f"archive: {CMD_BRANCH}}}\n", f"archive: {CMD_BRANCH}}}\n"
                                 + none), "utf-8")  # fmt: skip

    needs = [n for n in needs_you(world.facts(), load(path)) if n.kind == "closeout-stuck"]
    assert len(needs) == 1 and "PR #900" in needs[0].text  # one row for both members
    assert "closeout-stuck" in NEED_LABELS and "closeout-held" in NEED_LABELS
