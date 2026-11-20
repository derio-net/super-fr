"""The wave merge queue's pure planner (spec 2026-11-19-wave-merge-queue §A, §B, §C, §M;
R2, R3, R8, R9, R13, R14, R30, R31, R36).

`fr.triage.wave_queue.plan_queue` is a function of a `QueueSnapshot` alone: no git, no
forge, no clock. Every test builds a snapshot by hand and reads the plan it returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.approval import Approved, First, Void
from fr.triage.batch_drive import LivePr
from fr.triage.model import Batch, QueueRecord
from fr.triage.wave_queue import (
    Hold,
    QueueAction,
    QueueConfig,
    QueuePlan,
    QueueSnapshot,
    SlotCheck,
    hold_message,
    parse_hold,
    plan_queue,
    queue_phase,
)

REPO = "derio-net/super-fr"
ME = "s-11111111"
OTHER = "s-22222222"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
AT = "2026-11-20T10:00:00Z"
MAIN = "m0" * 20


def _batch(bid: str, n: int, *, wave: int | None = 1, events: Sequence[dict[str, Any]] = (),
           **kw: Any) -> Batch:  # fmt: skip
    doc: dict[str, Any] = {
        "id": bid, "title": bid, "ids": [f"super-fr#{n}"], "wave": wave,
        "events": [
            {"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake", "handle": "h",
             "branch": f"feat/batch-{bid}"},
            *events,
        ],
        **kw,
    }  # fmt: skip
    return Batch.model_validate(doc)


def _live(n: int, head: str = "", **kw: Any) -> LivePr:
    return LivePr(number=n, state=kw.pop("state", "OPEN"), draft=kw.pop("draft", False),
                  head=head or f"head-{n}", checks=kw.pop("checks", "green"), **kw)  # fmt: skip


def _record(*events: dict[str, Any], wave: int | None = 1, base: str = MAIN,
            scope: str = ME) -> QueueRecord:  # fmt: skip
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": wave, "scope": scope, "base": base, "events": list(events)}
    )


def _open(at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_open", "at": at}


def _built(slot: int, sha: str, bid: str, *, head: str = "", parent: str = MAIN,
           base: str = MAIN, at: str = AT) -> dict[str, Any]:  # fmt: skip
    return {"kind": "queue_built", "at": at, "slot": slot, "sha": sha, "entry": {"batch": bid},
            "head": head or f"head-{bid}", "patch_id": f"pid-{bid}", "base": base,
            "parent": parent}  # fmt: skip


def _land(main: str, *bids: str, at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_land", "at": at, "main": main,
            "entries": [{"batch": b} for b in bids]}  # fmt: skip


def _eject(bid: str, reason: str = "red", at: str = AT, head: str | None = None) -> dict[str, Any]:
    doc = {"kind": "queue_eject", "at": at, "entry": {"batch": bid}, "reason": reason}
    return doc if head is None else {**doc, "head": head}


def _qs(
    batches: Sequence[Batch],
    stages: dict[str, str],
    *,
    live: dict[str, LivePr] | None = None,
    numbers: dict[str, int] | None = None,
    **kw: Any,
) -> QueueSnapshot:
    """A snapshot of REPO: every `pr-open` batch is approved and green unless told."""
    numbers = numbers or {b.id: 100 + i for i, b in enumerate(batches)}
    if live is None:
        live = {
            b.id: _live(numbers[b.id], f"head-{b.id}")
            for b in batches if stages.get(b.id) == "pr-open"
        }  # fmt: skip
    kw.setdefault("approvals", {bid: First(pr.head) for bid, pr in live.items()})
    kw.setdefault("base", MAIN)
    return QueueSnapshot(
        repo=REPO,
        scope=ME,
        config=kw.pop("config", QueueConfig()),
        now=kw.pop("now", NOW),
        batches=tuple(batches),
        stages=stages,  # type: ignore[arg-type]
        live=live,
        **kw,
    )


def _kinds(plan: QueuePlan) -> list[str]:
    return [a.kind for a in plan.actions]


def _one(plan: QueuePlan, kind: str) -> QueueAction:
    (got,) = [a for a in plan.actions if a.kind == kind]
    return got


GREEN, PENDING = SlotCheck("green"), SlotCheck("pending")


def _green(*shas: str) -> dict[str, SlotCheck]:
    return {s: SlotCheck("green") for s in shas}


# ------------------------------------------------ phases and wave choice (R2, R3, R31)


def test_an_idle_repo_opens_the_lowest_unfinished_wave_on_its_first_ready_entry() -> None:
    batches = [
        _batch("w3", 1, wave=3),  # dispatched, no PR yet: not ready, not terminal
        _batch("w3b", 4, wave=3),
        _batch("w4", 2, wave=4),
        _batch("w2", 3, wave=2),  # landed: terminal
    ]
    stages = {"w3": "dispatched", "w3b": "pr-open", "w4": "pr-open", "w2": "merged"}
    plan = plan_queue(_qs(batches, stages))
    assert plan.phase == "idle"
    assert _kinds(plan) == ["queue-open"]
    assert _one(plan, "queue-open").wave == 3 and plan.wave == 3
    assert plan.waiting == ("w4",)


def test_an_idle_repo_opens_nothing_while_no_entry_of_the_lowest_unfinished_wave_is_ready() -> None:
    # p2-queue-opens-on-first-ready: no queue, so no hold blocks a release, while the
    # wave is still being developed; a later wave's ready PR waits all the same (R2).
    batches = [_batch("w3", 1, wave=3), _batch("w4", 2, wave=4), _batch("loose", 3, wave=None)]
    stages = {"w3": "dispatched", "w4": "pr-open", "loose": "pr-open"}
    plan = plan_queue(_qs(batches, stages))
    assert plan.phase == "idle" and plan.actions == () and plan.wave is None
    assert set(plan.waiting) == {"w4", "loose"}


def test_terminal_means_landed_cancelled_abandoned_or_deferred() -> None:
    deferred = [{"kind": "deferred", "at": AT, "wave": 3}]
    batches = [
        _batch("a", 1, wave=3, events=deferred),
        _batch("b", 2, wave=3),
        _batch("c", 3, wave=3),
        _batch("d", 4, wave=3),
        _batch("e", 5, wave=5),
    ]
    stages = {"a": "pr-open", "b": "cancelled", "c": "abandoned", "d": "partial", "e": "pr-open"}
    plan = plan_queue(_qs(batches, stages))
    assert _one(plan, "queue-open").wave == 5


def test_a_requeued_batch_belongs_to_the_wave_it_names() -> None:
    moved = [{"kind": "deferred", "at": AT, "wave": 3},
             {"kind": "requeued", "at": "2026-11-20T10:05:00Z", "wave": 6}]  # fmt: skip
    batches = [_batch("a", 1, wave=3, events=moved), _batch("b", 2, wave=7)]
    plan = plan_queue(_qs(batches, {"a": "pr-open", "b": "pr-open"}))
    assert _one(plan, "queue-open").wave == 6


def test_another_scopes_hold_is_held_naming_it_and_nothing_else() -> None:
    batches = [_batch("a", 1, wave=3)]
    for state in ("open", "drained"):
        hold = Hold(state=state, scope=OTHER, wave=2, parent=MAIN)  # type: ignore[arg-type]
        plan = plan_queue(_qs(batches, {"a": "pr-open"}, hold=hold))
        assert _kinds(plan) == ["queue-held"], state
        held = plan.actions[0]
        assert held.scope == OTHER and OTHER in held.detail and "wave 2" in held.detail


def test_another_scopes_hold_holds_an_open_queue_too() -> None:
    batches = [_batch("a", 1, wave=3)]
    hold = Hold(state="open", scope=OTHER, wave=3, parent=MAIN)
    plan = plan_queue(_qs(batches, {"a": "pr-open"}, records=(_record(_open(), wave=3),),
                          hold=hold))  # fmt: skip
    assert _kinds(plan) == ["queue-held"]


def test_a_drained_hold_opens_nothing_and_a_cleared_or_absent_one_opens() -> None:
    batches = [_batch("a", 1, wave=3)]
    stages = {"a": "pr-open"}
    drained = Hold(state="drained", scope=ME, wave=2, parent=MAIN)
    drain_rec = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN}, wave=2)
    plan = plan_queue(_qs(batches, stages, hold=drained, records=(drain_rec,)))
    assert plan.phase == "releasing" and plan.actions == ()
    plan = plan_queue(_qs(batches, stages, hold=drained))  # no record: still releasing
    assert plan.phase == "releasing" and plan.actions == ()
    for hold in (None, Hold(state="cleared", scope=OTHER, wave=2, parent=MAIN)):
        plan = plan_queue(_qs(batches, stages, hold=hold, records=(drain_rec,)))
        # the cleared hold of a recorded drain is recorded (queue_cleared), then it opens
        assert plan.phase == "idle" and "queue-open" in _kinds(plan), hold


def test_the_phase_reads_records_and_the_hold() -> None:
    hold_open = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    assert queue_phase((), None) == "idle"
    assert queue_phase((_record(_open()),), hold_open) == "open"
    drained = _record(_open(), {"kind": "queue_drain", "at": AT})
    assert queue_phase((drained,), Hold(state="drained", scope=ME, wave=1, parent=MAIN)) == (
        "releasing"
    )
    assert queue_phase((drained,), Hold(state="cleared", scope=ME, wave=1, parent=MAIN)) == "idle"
    assert queue_phase((drained,), None) == "idle"


def test_between_waves_entries_wait_while_a_waved_batch_is_unfinished() -> None:
    batches = [_batch("loose", 1, wave=None), _batch("w2", 2, wave=2)]
    plan = plan_queue(_qs(batches, {"loose": "pr-open", "w2": "dispatched"}))
    assert plan.actions == () and plan.waiting == ("loose",)


def test_between_waves_entries_open_a_one_entry_queue_once_every_wave_is_done() -> None:
    approved = {"kind": "approval", "at": "2026-11-20T10:30:00Z", "pr": 101, "head": "head-new"}
    older = {"kind": "approval", "at": "2026-11-20T10:10:00Z", "pr": 100, "head": "head-old"}
    batches = [
        _batch("new", 1, wave=None, events=[approved]),
        _batch("old", 2, wave=None, events=[older]),
        _batch("w2", 3, wave=2),
    ]
    stages = {"new": "pr-open", "old": "pr-open", "w2": "merged"}
    live = {"new": _live(101, "head-new"), "old": _live(100, "head-old")}
    approvals = {"new": Approved("head-new"), "old": Approved("head-old")}
    plan = plan_queue(_qs(batches, stages, live=live, approvals=approvals))
    opened = _one(plan, "queue-open")
    assert opened.wave is None and opened.entries == ("old",)
    assert plan.waiting == ("new",)


def test_an_idle_repo_with_nothing_unfinished_and_nothing_ready_opens_nothing() -> None:
    batches = [_batch("w2", 1, wave=2), _batch("loose", 2, wave=None)]
    live = {"loose": _live(101, checks="pending")}
    plan = plan_queue(_qs(batches, {"w2": "merged", "loose": "pr-open"}, live=live))
    assert plan.actions == () and plan.phase == "idle"


def test_an_entry_needs_an_open_pr_a_valid_approval_and_green_checks() -> None:
    batches = [_batch(b, i, wave=None) for i, b in enumerate(("red", "void", "closed", "ok"))]
    stages = dict.fromkeys(("red", "void", "closed", "ok"), "pr-open")
    live = {
        "red": _live(1, checks="failing"),
        "void": _live(2),
        "closed": _live(3, state="CLOSED"),
        "ok": _live(4),
    }
    approvals = {"red": First("head-1"), "void": Void("h"), "closed": First("head-3"),
                 "ok": First("head-4")}  # fmt: skip
    plan = plan_queue(_qs(batches, stages, live=live, approvals=approvals))
    assert _one(plan, "queue-open").entries == ("ok",) and plan.waiting == ()


# --------------------------------------------- building, depth and landing (R8, R9)


def _approved(n: int, minute: int) -> dict[str, Any]:
    return {"kind": "approval", "at": f"2026-11-20T09:{minute:02d}:00Z", "pr": n,
            "head": f"head-{n}"}  # fmt: skip


def _abc(*events: dict[str, Any], **kw: Any) -> QueueSnapshot:
    """An open wave-1 queue of a, b, c (approved in that order) at depth 2."""
    batches = [
        _batch("c", 3, events=[_approved(102, 30)]),
        _batch("a", 1, events=[_approved(100, 10)]),
        _batch("b", 2, events=[_approved(101, 20)]),
    ]
    numbers = {"a": 100, "b": 101, "c": 102}
    kw.setdefault("hold", Hold(state="open", scope=ME, wave=1, parent=MAIN))
    stages = kw.pop("stages", dict.fromkeys("abc", "pr-open"))
    return _qs(batches, stages, numbers=numbers, records=(_record(_open(), *events),),
               **kw)  # fmt: skip


def test_an_open_queue_builds_its_first_depth_entries_into_slots_on_the_base() -> None:
    plan = plan_queue(_abc())
    assert plan.phase == "open" and plan.entries == ("a", "b", "c")
    build = _one(plan, "queue-build")
    assert (build.entries, build.slots, build.base, build.fresh_entry) == (
        ("a", "b"), (1, 2), MAIN, "")  # fmt: skip
    assert "queue-land" not in _kinds(plan)


def test_both_slots_green_lands_the_prefix_at_the_second_slots_sha_and_builds_on() -> None:
    plan = plan_queue(_abc(_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"),
                           slots=_green("s1", "s2")))  # fmt: skip
    land = _one(plan, "queue-land")
    assert (land.entries, land.sha) == (("a", "b"), "s2")
    build = _one(plan, "queue-build")
    assert (build.entries, build.slots, build.base) == (("c",), (1,), "s2")
    assert _kinds(plan) == ["queue-land", "queue-build"]
    assert plan.entries == ("c",)


def test_a_green_first_slot_lands_alone_and_the_second_keeps_testing_on_the_landed_main() -> None:
    plan = plan_queue(_abc(_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"),
                           slots={"s1": GREEN, "s2": PENDING}))  # fmt: skip
    land = _one(plan, "queue-land")
    assert (land.entries, land.sha) == (("a",), "s1")
    build = _one(plan, "queue-build")  # c, on main+a+b, into the slot a freed
    assert (build.entries, build.slots, build.base) == (("c",), (1,), "s2")
    assert plan.entries == ("b", "c")


def test_a_pending_first_slot_lands_nothing() -> None:
    plan = plan_queue(_abc(_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"),
                           slots={"s1": PENDING, "s2": GREEN}))  # fmt: skip
    assert plan.actions == ()


def test_after_a_recorded_landing_the_queue_goes_on_from_the_landed_main() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), _land("s1", "a"),
              _built(1, "s3", "c", parent="s2", base="s1"))  # fmt: skip
    live = {"b": _live(101, "head-b"), "c": _live(102, "head-c")}
    plan = plan_queue(_abc(*events, base="s1", live=live, slots=_green("s2", "s3"),
                           stages={"a": "merged", "b": "pr-open", "c": "pr-open"}))  # fmt: skip
    land = _one(plan, "queue-land")
    assert (land.entries, land.sha) == (("b", "c"), "s3")
    assert _kinds(plan) == ["queue-land"]


def test_a_head_that_moved_since_its_build_is_built_again() -> None:
    live = {"a": _live(100, "head-a"), "b": _live(101, "head-b2"), "c": _live(102, "head-c")}
    plan = plan_queue(_abc(_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), live=live,
                           slots=_green("s1", "s2")))  # fmt: skip
    assert _one(plan, "queue-land").entries == ("a",)
    build = _one(plan, "queue-build")
    assert (build.entries, build.base, build.slots) == (("b", "c"), "s1", (1, 2))


def test_a_ci_none_repo_lands_each_built_combination_without_a_wait() -> None:
    plan = plan_queue(_abc(_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"),
                           config=QueueConfig(ci="none")))  # fmt: skip
    assert _one(plan, "queue-land").entries == ("a", "b")


def test_a_later_waves_ready_entry_never_joins_the_open_queue() -> None:
    snap = _abc()
    later = _batch("w2", 9, wave=2, events=[_approved(109, 5)])
    live = {**snap.live, "w2": _live(109)}
    approvals = {**snap.approvals, "w2": First("head-109")}
    stages = {**snap.stages, "w2": "pr-open"}
    from dataclasses import replace

    plan = plan_queue(replace(snap, batches=(*snap.batches, later), live=live,
                              approvals=approvals, stages=stages))  # fmt: skip
    assert plan.entries == ("a", "b", "c") and plan.waiting == ("w2",)


# ---------------------------------------------------- a foreign move of main (R14)


def test_a_foreign_base_move_rebuilds_every_slot_on_the_new_base_and_says_so_once() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"))
    plan = plan_queue(_abc(*events, base="f1", slots=_green("s1", "s2")))
    assert "queue-land" not in _kinds(plan)
    rebuild = _one(plan, "queue-rebuild")
    assert (rebuild.entries, rebuild.slots, rebuild.base) == (("a", "b"), (1, 2), "f1")
    warn = _one(plan, "queue-warn")
    assert "f1" in warn.detail and warn.key
    again = plan_queue(_abc(*events, base="f1", warned=frozenset({warn.key})))
    assert _kinds(again) == ["queue-rebuild"]
    for action in (*plan.actions, *again.actions):
        assert "feat/batch-" not in action.detail  # no action names a PR head ref


def test_a_foreign_move_with_no_entry_left_adopts_the_new_main_and_drains_there() -> None:
    # p2-r2: every batch terminal, nothing queued, main moved under the queue: it drains at
    # the moved main instead of waiting on a rebuild that has nothing to build.
    snap = _abc(_built(1, "s1", "a"), _land("s1", "a"),
                stages={"a": "merged", "b": "cancelled", "c": "abandoned"}, base="f1")  # fmt: skip
    plan = plan_queue(snap)
    assert _kinds(plan) == ["queue-warn", "queue-drain"]
    assert _one(plan, "queue-drain").sha == "f1" and plan.entries == ()


def test_a_foreign_move_with_no_entry_left_still_proposes_the_stalled_batch() -> None:
    batches = [_batch("a", 1), _batch("c", 3, events=_spent(102))]
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    live = {"c": _live(102, checks="failing")}
    plan = plan_queue(_qs(batches, {"a": "merged", "c": "pr-open"}, live=live, hold=hold,
                          records=(_record(_open()),), base="f1"))  # fmt: skip
    assert _kinds(plan) == ["queue-warn", "queue-need"]


def test_once_rebuilt_on_the_new_base_the_queue_lands_again() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"),
              _built(1, "r1", "a", parent="f1", base="f1"),
              _built(2, "r2", "b", parent="r1", base="f1"))  # fmt: skip
    plan = plan_queue(_abc(*events, base="f1", slots=_green("r1", "r2")))
    assert _one(plan, "queue-land").sha == "r2" and "queue-warn" not in _kinds(plan)


def test_an_unread_base_is_no_foreign_move() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"))
    plan = plan_queue(_abc(*events, base="", slots=_green("s1", "s2")))
    assert _one(plan, "queue-land").entries == ("a", "b")


# ------------------------------------------- ejection: red and conflicts (R6, R13)

FAIL = SlotCheck("failing", ("test",))


def _red_slot2(*extra: dict[str, Any], **kw: Any) -> QueuePlan:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), *extra)
    slots = {"s1": GREEN, "s2": FAIL, **{e["sha"]: FAIL for e in extra}}
    return plan_queue(_abc(*events, slots=slots, **kw))


def test_a_first_red_behind_a_green_slot_is_rebuilt_once_fresh_in_its_own_slot() -> None:
    plan = _red_slot2()
    assert _one(plan, "queue-land").entries == ("a",)
    build = _one(plan, "queue-build")
    assert build.fresh_entry == "b" and build.entries[0] == "b" and build.slots[0] == 2
    assert build.base == "s1"
    assert "queue-eject" not in _kinds(plan)


def test_a_second_red_at_the_same_tree_ejects_it_and_rebuilds_what_was_behind() -> None:
    plan = _red_slot2(_built(2, "s2b", "b", parent="s1", at="2026-11-20T10:30:00Z"),
                      sessions={"b": "idle"})  # fmt: skip
    eject = _one(plan, "queue-eject")
    assert (eject.entries, eject.reason, eject.sha, eject.checks) == (("b",), "red", "s2b",
                                                                      ("test",))  # fmt: skip
    assert eject.decision == "handback" and eject.batch == "b"
    build = _one(plan, "queue-build")  # c, on main+a
    assert (build.entries, build.base, build.fresh_entry) == (("c",), "s1", "")
    assert plan.entries == ("c",)


def test_only_the_retried_entry_is_named_fresh_not_the_ones_built_behind_it() -> None:
    # p2-r3: a, b at depth 3: b's combination is red once, so b is retried fresh and c is
    # built behind it for the first time; only b is the R13 same-tree retry.
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"))
    plan = plan_queue(_abc(*events, slots={"s1": GREEN, "s2": FAIL},
                           config=QueueConfig(depth=3)))  # fmt: skip
    build = _one(plan, "queue-build")
    assert build.entries == ("b", "c") and build.fresh_entry == "b"


def test_a_red_ejection_names_the_head_it_left_at() -> None:
    plan = _red_slot2(_built(2, "s2b", "b", parent="s1", at="2026-11-20T10:30:00Z"),
                      sessions={"b": "idle"})  # fmt: skip
    assert _one(plan, "queue-eject").head == "head-b"


def test_the_red_decision_reads_the_session_and_the_budget() -> None:
    again = _built(2, "s2b", "b", parent="s1", at="2026-11-20T10:30:00Z")
    assert _one(_red_slot2(again, sessions={"b": "working"}), "queue-eject").decision == "wait"
    assert _one(_red_slot2(again, sessions={"b": "absent"}), "queue-eject").decision == (
        "needs_you"
    )
    spent = _spent(101)
    snap = _abc()
    batches = tuple(
        b.model_copy(update={"events": [*b.events, *(Batch.model_validate(
            {"id": "z", "title": "z", "ids": ["super-fr#9"], "events": spent}).events)]})
        if b.id == "b" else b
        for b in snap.batches
    )  # fmt: skip
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), again)
    from dataclasses import replace

    plan = plan_queue(replace(_abc(*events, slots={"s1": GREEN, "s2": FAIL, "s2b": FAIL},
                                   sessions={"b": "idle"}), batches=batches))  # fmt: skip
    assert _one(plan, "queue-eject").decision == "needs_you"


def test_a_pending_rebuild_ejects_nothing_and_a_green_one_lands() -> None:
    again = _built(2, "s2b", "b", parent="s1", at="2026-11-20T10:30:00Z")
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), again)
    plan = plan_queue(_abc(*events, slots={"s1": GREEN, "s2": FAIL, "s2b": GREEN}))
    assert _one(plan, "queue-land").entries == ("a", "b")
    assert "queue-eject" not in _kinds(plan)


def test_a_conflict_met_at_build_ejects_the_entry_through_the_conflict_decision() -> None:
    from fr.triage.wave_queue import BuildConflict

    events = (_built(1, "s1", "a"),)
    plan = plan_queue(_abc(*events, conflicts={"b": BuildConflict("head-b", ("x.py",))}))
    eject = _one(plan, "queue-eject")
    assert (eject.entries, eject.reason, eject.paths, eject.decision) == (
        ("b",), "conflict", ("x.py",), "handback")  # fmt: skip
    build = _one(plan, "queue-build")
    assert build.entries == ("c",) and build.base == "s1"


def test_conflicts_sharing_a_path_wait_behind_the_first_and_a_stale_one_is_ignored() -> None:
    from fr.triage.wave_queue import BuildConflict

    conflicts = {"b": BuildConflict("head-b", ("x.py",)), "c": BuildConflict("head-c", ("x.py",))}
    plan = plan_queue(_abc(conflicts=conflicts))
    got = [(a.entries, a.decision) for a in plan.actions if a.kind == "queue-eject"]
    assert got == [(("b",), "handback"), (("c",), "wait-behind")]
    stale = plan_queue(_abc(conflicts={"b": BuildConflict("head-old", ("x.py",))}))
    assert "queue-eject" not in _kinds(stale)


def test_a_conflict_ejection_names_its_head_and_keeps_the_entry_out_at_that_head() -> None:
    # p2-r1: a conflict at build has no `queue_built` for that head; the eject event's own
    # head keeps it out, and it re-enters once the head moves.
    from fr.triage.wave_queue import BuildConflict

    met = {"b": BuildConflict("head-b", ("x.py",))}
    plan = plan_queue(_abc(_built(1, "s1", "a"), conflicts=met))
    assert _one(plan, "queue-eject").head == "head-b"
    events = (_built(1, "s1", "a"), _eject("b", "conflict", head="head-b"))
    after = plan_queue(_abc(*events, conflicts=met))  # the executor may still report it
    assert "b" not in after.entries and "queue-eject" not in _kinds(after)
    assert "b" not in after.waiting  # p2-r4: ejected, not waiting (R25)
    live = {"a": _live(100, "head-a"), "b": _live(101, "head-b2"), "c": _live(102, "head-c")}
    moved = plan_queue(_abc(*events, live=live, conflicts=met))
    assert moved.entries == ("a", "c", "b") and "queue-eject" not in _kinds(moved)


def test_a_conflict_ejection_without_a_head_reads_the_batchs_conflict_event() -> None:
    from dataclasses import replace

    conflict = {"kind": "conflict", "at": AT, "head": "head-b", "paths": ["x.py"],
                "delivered": "session", "handle": "h"}  # fmt: skip
    snap = _abc(_built(1, "s1", "a"), _eject("b", "conflict"))
    batches = tuple(
        b.model_copy(update={"events": [*b.events, Batch.model_validate(
            {"id": "z", "title": "z", "ids": ["super-fr#9"], "events": [conflict]}).events[0]]})
        if b.id == "b" else b for b in snap.batches
    )  # fmt: skip
    assert "b" not in plan_queue(replace(snap, batches=batches)).entries
    assert "b" in plan_queue(snap).entries  # no head anywhere: it is let back in


def test_an_ejected_entry_re_enters_only_when_its_head_moves() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), _eject("b"))
    kept_out = plan_queue(_abc(*events))
    assert kept_out.entries == ("a", "c") and kept_out.waiting == ()  # p2-r4
    live = {"a": _live(100, "head-a"), "b": _live(101, "head-b2"), "c": _live(102, "head-c")}
    assert plan_queue(_abc(*events, live=live)).entries == ("a", "c", "b")


# ----------------------------------------------- drain and stall proposals (R30)


def _wave1(stages: dict[str, str], *events: dict[str, Any], **kw: Any) -> QueuePlan:
    return plan_queue(_abc(*events, stages=stages, **kw))


def test_a_wave_whose_batches_are_all_terminal_drains_at_the_landed_main() -> None:
    deferred = {"kind": "deferred", "at": "2026-11-20T09:50:00Z", "wave": 1}
    snap = _abc(_built(1, "s1", "a"), _land("s1", "a"),
                stages={"a": "merged", "b": "cancelled", "c": "pr-open"}, base="s1")  # fmt: skip
    from dataclasses import replace

    batches = tuple(b.model_copy(update={"events": [*b.events, Batch.model_validate(
        {"id": "z", "title": "z", "ids": ["super-fr#9"], "events": [deferred]}).events[0]]})
        if b.id == "c" else b for b in snap.batches)  # fmt: skip
    for closeout in (None, True):
        plan = plan_queue(replace(snap, batches=batches, closeout_landed=closeout))
        drain = _one(plan, "queue-drain")
        assert drain.sha == "s1" and drain.wave == 1 and _kinds(plan) == ["queue-drain"]
    held = plan_queue(replace(snap, batches=batches, closeout_landed=False))
    assert "queue-drain" not in _kinds(held)


def test_a_wave_with_an_unfinished_batch_does_not_drain() -> None:
    plan = _wave1({"a": "merged", "b": "cancelled", "c": "dispatched"}, base=MAIN)
    assert "queue-drain" not in _kinds(plan)


def test_a_between_waves_queue_drains_once_its_one_entry_landed() -> None:
    batches = [_batch("x", 1, wave=None), _batch("y", 2, wave=None)]
    rec = _record(_open(), _built(1, "s1", "x"), _land("s1", "x"), wave=None)
    hold = Hold(state="open", scope=ME, wave=None, parent=MAIN)
    plan = plan_queue(_qs(batches, {"x": "merged", "y": "pr-open"}, records=(rec,), hold=hold,
                          base="s1", live={"y": _live(101, "head-y")}))  # fmt: skip
    assert _kinds(plan) == ["queue-drain"] and plan.waiting == ("y",)


def _loose(stages: dict[str, str], *events: dict[str, Any], **kw: Any) -> QueuePlan:
    """A between-waves queue for x (y another loose batch), opened at MAIN."""
    batches = [_batch("x", 1, wave=None), _batch("y", 2, wave=None)]
    rec = _record(_open(), *events, wave=None)
    hold = Hold(state="open", scope=ME, wave=None, parent=MAIN)
    kw.setdefault("live", {"x": _live(100, "head-x")})
    return plan_queue(_qs(batches, stages, records=(rec,), hold=hold, **kw))


def test_a_between_waves_queue_whose_one_entry_was_ejected_drains_at_its_base() -> None:
    # p2-r6: nothing landed and nothing left to land: it drains at the base it opened on
    # (like a wave drained by deferral, R29), so the hold reaches a release and is cleared.
    plan = _loose({"x": "pr-open", "y": "dispatched"},
                  _eject("x", "conflict", head="head-x"))  # fmt: skip
    assert _kinds(plan) == ["queue-drain"] and _one(plan, "queue-drain").sha == MAIN
    assert plan.entries == () and plan.waiting == ()


def test_a_between_waves_queue_whose_entry_left_before_it_was_built_drains() -> None:
    plan = _loose({"x": "cancelled", "y": "dispatched"}, live={})
    assert _kinds(plan) == ["queue-drain"]


def test_a_between_waves_queue_whose_built_entry_is_only_pending_keeps_waiting() -> None:
    # x pushed a new head after its build: not ready while its checks run, still its entry.
    live = {"x": _live(100, "head-x2", checks="pending")}
    plan = _loose({"x": "pr-open", "y": "dispatched"}, _built(1, "s1", "x"), live=live)
    assert "queue-drain" not in _kinds(plan)


def test_an_entry_ejected_from_a_between_waves_queue_opens_none_again_at_the_same_head() -> None:
    drained = _record(_open(), _eject("x", "conflict", head="head-x"),
                      {"kind": "queue_drain", "at": AT, "main": MAIN}, wave=None)  # fmt: skip
    batches = [_batch("x", 1, wave=None)]
    same = plan_queue(_qs(batches, {"x": "pr-open"}, records=(drained,)))
    assert same.actions == () and same.waiting == ()
    live = {"x": _live(100, "head-x2")}
    moved = plan_queue(_qs(batches, {"x": "pr-open"}, records=(drained,), live=live,
                           approvals={"x": First("head-x2")}))  # fmt: skip
    assert _one(moved, "queue-open").entries == ("x",)


def _spent(n: int) -> list[dict[str, Any]]:
    return [{"kind": "red_handback", "at": f"2026-11-20T09:4{i}:00Z", "pr": n, "head": f"r{i}",
             "checks": ["t"], "delivered": "session"} for i in range(2)]  # fmt: skip


def test_one_batch_with_a_spent_budget_blocking_the_drain_is_proposed_for_deferral() -> None:
    batches = [_batch("a", 1), _batch("b", 2), _batch("c", 3, events=_spent(102))]
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    stages = {"a": "merged", "b": "abandoned", "c": "pr-open"}
    live = {"c": _live(102, checks="failing")}
    plan = plan_queue(_qs(batches, stages, live=live, records=(_record(_open()),), hold=hold,
                          scope_args=("--repo", REPO)))  # fmt: skip
    (need,) = plan.actions
    assert need.kind == "queue-need" and need.batch == "c"
    assert f"fr triage batch defer c --repo {REPO}" in need.detail
    assert f"fr triage batch requeue c --repo {REPO}" in need.detail


def test_a_batch_with_no_progress_for_stall_hours_is_proposed_and_a_recent_one_is_not() -> None:
    batches = [_batch("a", 1), _batch("c", 3)]  # c's last event: its dispatch at 09:00
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    stages = {"a": "merged", "c": "dispatched"}
    snap = _qs(batches, stages, records=(_record(_open()),), hold=hold, live={},
               now=datetime(2026, 11, 20, 13, 1, tzinfo=UTC))  # fmt: skip
    assert _kinds(plan_queue(snap)) == ["queue-need"]
    from dataclasses import replace

    recent = {"c": datetime(2026, 11, 20, 12, 0, tzinfo=UTC)}  # a new head an hour ago
    assert plan_queue(replace(snap, head_changed=recent)).actions == ()
    assert plan_queue(replace(snap, now=datetime(2026, 11, 20, 12, 59, tzinfo=UTC))).actions == ()
    assert plan_queue(replace(snap, config=QueueConfig(stall_hours=5))).actions == ()


def test_no_proposal_while_two_batches_are_unfinished() -> None:
    batches = [_batch("b", 2, events=_spent(101)), _batch("c", 3, events=_spent(102))]
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    plan = plan_queue(_qs(batches, {"b": "dispatched", "c": "dispatched"}, hold=hold,
                          records=(_record(_open()),), live={}))  # fmt: skip
    assert plan.actions == ()


def test_the_cap_predicate_spares_a_pr_waiting_on_a_queue_that_is_not_open() -> None:
    from fr.triage.wave_queue import waits_on_queue

    w2 = _batch("w2", 1, wave=2)
    assert waits_on_queue(w2, "pr-open", open_wave=1)
    assert not waits_on_queue(w2, "pr-open", open_wave=2)
    assert not waits_on_queue(w2, "dispatched", open_wave=1)
    assert waits_on_queue(_batch("loose", 2, wave=None), "pr-open", open_wave=1)


# ------------------------------------------------------------- purity


def test_the_planner_reaches_no_git_forge_process_or_clock() -> None:
    import ast

    from tests.unit.triage_fixtures import forbidden_imports

    path = Path(__file__).resolve().parents[2] / "packages/fr/src/fr/triage/wave_queue.py"
    banned = ("fr_dispatch", "subprocess", "fr.triage.gitseam", "fr.ghclient", "fr.gh", "os",
              "time", "shutil", "fr.commands", "fr.triage.queue_exec")  # fmt: skip
    assert forbidden_imports(path, "fr.triage", banned) == []
    calls = {
        n.func.attr
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert not calls & {"now", "utcnow", "today"}


# ------------------------------------------------ a halted queue (R11, R22, R24, R34; p3-r1)


REFUSED = "the default branch refused the queue's push (GH013)"


def _halt(state: str = "held", *, land: str = "push", main: str = MAIN,
          detail: str = REFUSED) -> dict[str, Any]:  # fmt: skip
    return {"kind": "queue_halt", "at": AT, "state": state, "detail": detail, "land": land,
            "main": main}  # fmt: skip


@pytest.mark.parametrize("state", ["held", "stopped"])
def test_a_recorded_halt_lands_and_builds_nothing_and_is_a_need(state: str) -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), _halt(state))
    plan = plan_queue(_abc(*events, slots=_green("s1", "s2")))
    assert _kinds(plan) == ["queue-need"]
    need = _one(plan, "queue-need")
    assert "GH013" in need.detail and state in need.detail
    assert "queue.land" in need.detail  # what lifts it


def test_a_halt_lifts_when_the_operator_changes_queue_land() -> None:
    events = (_built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"), _halt("held"))
    plan = plan_queue(_abc(*events, slots=_green("s1", "s2"), config=QueueConfig(land="merge")))
    assert _one(plan, "queue-land").entries == ("a", "b")


def test_a_halt_lifts_when_the_default_branch_moves_and_the_queue_rebuilds() -> None:
    events = (_built(1, "s1", "a"), _halt("stopped", land="merge", main=MAIN))
    plan = plan_queue(_abc(*events, base="m1" * 20, slots=_green("s1"),
                           config=QueueConfig(land="merge")))  # fmt: skip
    assert "queue-need" not in _kinds(plan)
    assert _one(plan, "queue-rebuild").base == "m1" * 20


def test_a_halt_is_a_blocked_action_of_the_pass_so_needs_you_lists_it() -> None:
    from fr.triage.batch_drive import _queue_reports

    plan = plan_queue(_abc(_built(1, "s1", "a"), _halt("held"), slots=_green("s1")))
    (action,) = _queue_reports(plan)
    assert action.kind == "blocked" and "GH013" in action.detail


# ------------------------------------------------ a lost slot lease (R4, R24; p3-r8)


def test_a_combination_whose_slot_push_lost_its_lease_is_built_again() -> None:
    from fr.triage.wave_queue import replay, slot_leases

    lost = {"kind": "queue_slot_lost", "at": AT, "slot": 1, "sha": "s1", "found": "x9"}
    record = _record(_open(), _built(1, "s1", "a"), lost)
    assert 1 not in replay(record).combos
    assert slot_leases([record]) == {1: "x9"}
    plan = plan_queue(_abc(_built(1, "s1", "a"), lost, slots=_green("s1")))
    assert "queue-land" not in _kinds(plan)
    assert _one(plan, "queue-build").entries == ("a", "b")


def test_slot_leases_are_the_last_recorded_sha_of_each_slot_across_records() -> None:
    from fr.triage.wave_queue import slot_leases

    old = _record(_open(), _built(1, "s1", "a"), _built(2, "s2", "b", parent="s1"))
    new = _record(_open(), _built(1, "s3", "c"))
    assert slot_leases([old, new]) == {1: "s3", 2: "s2"}


# ------------------------------------------------ what the queue landed (R12; p3-r4)


def test_queue_landed_names_every_batch_a_queue_landed() -> None:
    from fr.triage.wave_queue import queue_landed

    one = _record(_open(), _built(1, "s1", "a"), _land("s1", "a"))
    two = _record(_open(), _land("s9", "b"), wave=2)
    assert queue_landed([one, two]) == frozenset({"a", "b"})


def test_a_conflict_with_a_reason_names_it_in_the_ejection() -> None:
    from fr.triage.wave_queue import BuildConflict

    why = "rebase would drop content from its merge commits"
    plan = plan_queue(_abc(conflicts={"a": BuildConflict("head-a", ("x.py",), why)}))
    eject = _one(plan, "queue-eject")
    assert why in eject.detail and eject.reason == "conflict"


# ------------------------------------------------ the hold handshake (R17-R19, R27)


def _hold(state: str = "open", *, scope: str = ME, ago: timedelta = timedelta(minutes=5),
          wave: int | None = 1, sha: str = "h1" * 20) -> Hold:  # fmt: skip
    return Hold(state=state, scope=scope, wave=wave, parent=MAIN,  # type: ignore[arg-type]
                opened=NOW - timedelta(hours=3), refreshed=NOW - ago, sha=sha)  # fmt: skip


def _open_queue(**kw: Any) -> QueueSnapshot:
    return _qs([_batch("a", 1)], {"a": "pr-open"}, records=(_record(_open()),), **kw)


def test_a_hold_message_round_trips_and_garbage_is_not_a_hold() -> None:
    at = datetime(2026, 11, 20, 9, 30, 5, tzinfo=UTC)
    text = hold_message("open", ME, 3, at, NOW)
    assert text == (
        f"fr-hold: open scope {ME} wave 3 opened 2026-11-20T09:30:05Z refreshed "
        "2026-11-20T12:00:00Z"
    )
    hold = parse_hold(text + "\n\nbody ignored")
    assert hold is not None
    assert (hold.state, hold.scope, hold.wave, hold.opened, hold.refreshed) == (
        "open",
        ME,
        3,
        at,
        NOW,
    )
    assert parse_hold(hold_message("drained", ME, None, at, NOW)) is not None
    assert parse_hold(hold_message("drained", ME, None, at, NOW)).wave is None  # type: ignore[union-attr]
    for bad in ("", "wip", "fr-hold: held scope s wave 1 opened x refreshed y",
                "fr-hold: open scope s wave 1 opened 2026-01-01 refreshed 2026-01-01"):  # fmt: skip
        assert parse_hold(bad) is None, bad


def test_a_fresh_open_hold_needs_no_write_and_an_old_one_is_refreshed() -> None:
    plan = plan_queue(_open_queue(hold=_hold()))
    assert "queue-hold" not in _kinds(plan)
    plan = plan_queue(_open_queue(hold=_hold(ago=timedelta(hours=2))))
    action = _one(plan, "queue-hold")
    assert action.reason == "refresh" and "queue-need" not in _kinds(plan)


def test_a_vanished_cleared_or_expired_hold_is_re_armed_with_one_need() -> None:
    cases = {
        "gone": dict(hold=None, hold_read=True),
        "cleared": dict(hold=_hold("cleared", scope=OTHER)),
        "expired": dict(hold=_hold(ago=timedelta(hours=25))),
    }
    for name, kw in cases.items():
        plan = plan_queue(_open_queue(**kw))
        assert _one(plan, "queue-hold").reason == "rearm", name
        need = _one(plan, "queue-need")
        assert name in need.detail or "cleared by the release" in need.detail, name
        assert "no release was cut" in need.detail, name


def test_the_rearm_need_names_a_release_cut_from_a_partly_landed_wave() -> None:
    plan = plan_queue(_open_queue(hold=None, hold_read=True, releases=("v8.3.0-rc.7 at abc123",)))
    assert "v8.3.0-rc.7 at abc123" in _one(plan, "queue-need").detail


def test_an_unread_hold_plans_no_hold_write() -> None:
    plan = plan_queue(_open_queue())
    assert not {"queue-hold", "queue-need"} & set(_kinds(plan))


def test_a_drained_hold_unreleased_past_release_wait_hours_is_a_need_with_the_command() -> None:
    drained = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN})
    cfg = QueueConfig(release_wait_hours=6)
    young = plan_queue(_qs([], {}, records=(drained,), config=cfg,
                           hold=_hold("drained", ago=timedelta(hours=5))))  # fmt: skip
    assert young.phase == "releasing" and young.actions == ()
    old = plan_queue(_qs([], {}, records=(drained,), config=cfg,
                         hold=_hold("drained", ago=timedelta(hours=7))))  # fmt: skip
    need = _one(old, "queue-need")
    assert "git push origin --delete fr-hold/queue" in need.detail and "drained" in need.detail


def test_under_release_none_a_drained_hold_is_cleared_by_the_driver() -> None:
    drained = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN})
    plan = plan_queue(_qs([], {}, records=(drained,), config=QueueConfig(release="none"),
                          hold=_hold("drained")))  # fmt: skip
    assert _kinds(plan) == ["queue-cleared"]


def test_a_drain_recorded_but_never_pushed_is_pushed_again() -> None:
    drained = _record(_open(), {"kind": "queue_drain", "at": AT, "main": "m1" * 20})
    plan = plan_queue(_qs([], {}, records=(drained,), hold=_hold("open")))
    action = _one(plan, "queue-drain")
    assert action.sha == "m1" * 20 and "queue-open" not in _kinds(plan)


def test_a_cleared_hold_after_our_drain_is_recorded_once() -> None:
    drained = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN})
    assert _kinds(plan_queue(_qs([], {}, records=(drained,), hold=None, hold_read=True))) == [
        "queue-cleared"
    ]
    done = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN},
                   {"kind": "queue_cleared", "at": AT})  # fmt: skip
    assert plan_queue(_qs([], {}, records=(done,), hold=None, hold_read=True)).actions == ()


_REFUSED = {"kind": "queue_halt", "at": "2026-11-20T11:50:00Z", "state": "held", "land": "push",
            "detail": "hold write refused: the open hold: GH013 non-fast-forward"}  # fmt: skip


def test_a_refused_hold_write_stops_the_open_queue_with_a_need_until_a_write_succeeds() -> None:
    record = _record(_open(), _REFUSED)
    plan = plan_queue(_qs([_batch("a", 1)], {"a": "pr-open"}, records=(record,),
                          hold=None, hold_read=True))  # fmt: skip
    kinds = _kinds(plan)
    assert "queue-land" not in kinds and "queue-build" not in kinds
    assert _one(plan, "queue-hold").reason == "rearm"  # the driver tries again each pass
    assert any("hold write refused" in a.detail for a in plan.actions if a.kind == "queue-need")
    # a hold write succeeded after the halt: it lifts (stamps are whole seconds)
    fresh = Hold(state="open", scope=ME, wave=1, parent=MAIN, opened=NOW - timedelta(hours=1),
                 refreshed=datetime(2026, 11, 20, 11, 55, tzinfo=UTC), sha="h2" * 20)  # fmt: skip
    plan = plan_queue(_qs([_batch("a", 1)], {"a": "pr-open"}, records=(record,), hold=fresh))
    assert not any("hold write refused" in a.detail for a in plan.actions)


def test_a_refused_drained_write_is_a_need_beside_the_retry() -> None:
    record = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN}, _REFUSED)
    old_open = _hold("open", ago=timedelta(hours=1))
    plan = plan_queue(_qs([], {}, records=(record,), hold=old_open))
    assert _one(plan, "queue-drain").sha == MAIN
    assert any("hold write refused" in a.detail for a in plan.actions if a.kind == "queue-need")


def test_a_refused_cleared_write_under_release_none_is_a_need() -> None:
    record = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN}, _REFUSED)
    plan = plan_queue(_qs([], {}, records=(record,), config=QueueConfig(release="none"),
                          hold=_hold("drained", ago=timedelta(hours=1))))  # fmt: skip
    assert _kinds(plan) == ["queue-need", "queue-cleared"]


# ------------------------------------------- other entries: close-out, archive, export (R32)


def _other(kind: str, n: int, *, wave: int | None = None, at: str = AT, batch: str = "") -> Any:
    from fr.triage.wave_queue import OtherEntry

    when = datetime.fromisoformat(at.replace("Z", "+00:00"))
    return OtherEntry(key=f"{kind}#{n}", kind=kind, pr=n, wave=wave, at=when,  # type: ignore[arg-type]
                      batch=batch)  # fmt: skip


def _o(kind: str, n: int, **kw: Any) -> tuple[Any, dict[str, LivePr]]:
    return _other(kind, n, **kw), {f"{kind}#{n}": _live(n, f"head-{kind}-{n}")}


def test_an_other_entry_opens_a_one_entry_queue_between_waves() -> None:
    entry, live = _o("export", 7)
    plan = plan_queue(_qs([], {}, live=live, others=(entry,)))
    opened = _one(plan, "queue-open")
    assert opened.wave is None and opened.entries == ("export#7",)


def test_an_other_entry_waits_while_a_waved_batch_is_unfinished() -> None:
    entry, live = _o("archive", 8)
    plan = plan_queue(_qs([_batch("w2", 1, wave=2)], {"w2": "dispatched"}, live=live,
                          others=(entry,)))  # fmt: skip
    assert plan.actions == () and plan.waiting == ("archive#8",)


def test_a_closeout_of_the_open_wave_joins_that_waves_queue_and_builds_behind_the_batches() -> None:
    batches = [_batch("a", 1), _batch("b", 2)]
    entry, live = _o("closeout", 9, wave=1, batch="a", at="2026-11-20T11:00:00Z")
    live |= {"b": _live(101, "head-b")}
    rec = _record(_open(), _built(1, "s1", "a"), _land("s1", "a"))
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    plan = plan_queue(_qs(batches, {"a": "merged", "b": "pr-open"}, records=(rec,), hold=hold,
                          base="s1", live=live, others=(entry,)))  # fmt: skip
    build = _one(plan, "queue-build")
    assert build.entries == ("b", "closeout#9")


def test_a_wave_does_not_drain_while_its_closeout_waits_and_drains_once_it_landed() -> None:
    entry, live = _o("closeout", 9, wave=1, batch="a")
    rec = _record(_open(), _built(1, "s1", "a"), _land("s1", "a"))
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    snap = _qs([_batch("a", 1)], {"a": "merged"}, records=(rec,), hold=hold, base="s1",
               live=live, others=(entry,), closeout_landed=False)  # fmt: skip
    assert "queue-drain" not in _kinds(plan_queue(snap))
    rec2 = _record(_open(), _built(1, "s1", "a"), _land("s1", "a"),
                   _built(1, "s2", "closeout#9"), _land("s2", "closeout#9"))  # fmt: skip
    from dataclasses import replace

    done = plan_queue(replace(snap, records=(rec2,), base="s2", live={}, others=(),
                              closeout_landed=True))  # fmt: skip
    assert _kinds(done) == ["queue-drain"]


def test_a_non_batch_entry_needs_an_open_pr_and_green_checks_whatever_its_rule_admitted() -> None:
    red, live_red = _o("export", 7)
    live_red[red.key] = _live(7, "head-export-7", checks="pending")
    assert plan_queue(_qs([], {}, live=live_red, others=(red,))).actions == ()
    closed, live_closed = _o("archive", 8)
    live_closed[closed.key] = _live(8, "head-archive-8", state="MERGED")
    assert plan_queue(_qs([], {}, live=live_closed, others=(closed,))).actions == ()


def test_the_oldest_between_waves_entry_opens_first_whatever_its_kind() -> None:
    old, live = _o("archive", 8, at="2026-11-20T09:00:00Z")
    new, live2 = _o("export", 7, at="2026-11-20T10:00:00Z")
    plan = plan_queue(_qs([], {}, live={**live, **live2}, others=(new, old)))
    assert _one(plan, "queue-open").entries == ("archive#8",) and plan.waiting == ("export#7",)


def test_a_between_waves_other_entry_lands_and_the_queue_drains() -> None:
    entry, live = _o("export", 7)
    rec = _record(_open(), _built(1, "s1", "export#7", head="head-export-7") | {
        "entry": {"pr": 7, "kind": "export"}}, wave=None)  # fmt: skip
    green = SlotCheck("green")
    hold = Hold(state="open", scope=ME, wave=None, parent=MAIN)
    plan = plan_queue(_qs([], {}, live=live, others=(entry,), records=(rec,), hold=hold,
                          slots={"s1": green}))  # fmt: skip
    land = _one(plan, "queue-land")
    assert land.entries == ("export#7",) and land.sha == "s1"


def test_an_other_entry_ejected_at_its_head_is_a_need_and_stays_out_until_its_head_moves() -> None:
    entry, live = _o("closeout", 9, wave=1, batch="a")
    eject = {"kind": "queue_eject", "at": AT, "entry": {"pr": 9, "kind": "closeout"},
             "reason": "conflict", "head": "head-closeout-9"}  # fmt: skip
    rec = _record(_open(), eject)
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    snap = _qs([_batch("a", 1)], {"a": "merged"}, records=(rec,), hold=hold, live=live,
               others=(entry,), closeout_landed=False)  # fmt: skip
    plan = plan_queue(snap)
    assert plan.entries == ()
    need = _one(plan, "queue-need")
    assert "closeout PR #9" in need.detail and need.batch == "a"
    from dataclasses import replace

    moved = replace(snap, live={entry.key: _live(9, "head-new")})
    assert _one(plan_queue(moved), "queue-build").entries == ("closeout#9",)


def test_a_wave_waiting_only_on_its_closeout_past_stall_hours_is_a_need() -> None:
    rec = _record(_open("2026-11-20T03:00:00Z"), _built(1, "s1", "a", at="2026-11-20T03:30:00Z"),
                  _land("s1", "a", at="2026-11-20T04:00:00Z"))  # fmt: skip
    hold = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    snap = _qs([_batch("a", 1)], {"a": "merged"}, records=(rec,), hold=hold, base="s1",
               live={}, closeout_landed=False)  # fmt: skip
    plan = plan_queue(snap)  # last landing 8 h ago, stall_hours is 4
    need = _one(plan, "queue-need")
    assert "waits on the wave's close-out" in need.detail and "queue-drain" not in _kinds(plan)
    from dataclasses import replace

    fresh = replace(snap, now=datetime(2026, 11, 20, 5, 0, tzinfo=UTC))
    assert "queue-need" not in _kinds(plan_queue(fresh))  # an hour in: still its time
