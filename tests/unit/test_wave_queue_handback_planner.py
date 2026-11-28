"""The planner's hand-back onto the stack target, the re-issue and the carry hold (spec
2026-11-24-wave-queue-gaps R1, R2, R4, R5, R6; §A).

Pure: each test builds a `QueueSnapshot` by hand, with the `leads` and `carries` git would
have answered, and reads the plan.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from fr.triage.model import Batch
from fr.triage.wave_queue import BuildConflict, OtherEntry, QueueConfig, QueueSnapshot, plan_queue

from tests.unit.test_wave_queue_planner import (
    AT,
    MAIN,
    _abc,
    _built,
    _eject,
    _kinds,
    _live,
    _one,
)

PUSH_SQUASH = {"config": QueueConfig(land="push"), "method": "squash"}


def _with_conflict(snap: QueueSnapshot, bid: str, **event: Any) -> QueueSnapshot:
    doc = {"kind": "conflict", "at": AT, "head": f"head-{bid}", "paths": ["x.py"],
           "delivered": "session", "handle": "h", **event}  # fmt: skip
    extra = Batch.model_validate({"id": "z", "title": "z", "ids": ["super-fr#9"],
                                  "events": [doc]}).events[0]  # fmt: skip
    batches = tuple(b.model_copy(update={"events": [*b.events, extra]}) if b.id == bid else b
                    for b in snap.batches)  # fmt: skip
    return replace(snap, batches=batches)


# ------------------------------------------------------------- (a) the eject's target (R1)


def test_a_conflict_ejection_names_the_last_standing_combination_and_its_slot() -> None:
    plan = plan_queue(
        _abc(
            _built(1, "s1", "a"), conflicts={"b": BuildConflict("head-b", ("x.py",))}, **PUSH_SQUASH
        )
    )
    eject = _one(plan, "queue-eject")
    assert (eject.base, eject.slots) == ("s1", (1,))


def test_a_conflict_ejection_with_nothing_standing_names_the_base() -> None:
    plan = plan_queue(_abc(conflicts={"a": BuildConflict("head-a", ("x.py",))}, **PUSH_SQUASH))
    eject = _one(plan, "queue-eject")
    assert (eject.base, eject.slots) == (MAIN, ())


# ------------------------------------------------------------- (b) the re-issue (R2)


def _ejected_b(**kw: Any) -> QueueSnapshot:
    events = (_built(1, "s1", "a"), _eject("b", "conflict", head="head-b"))
    return _with_conflict(_abc(*events, **kw), "b", onto="s0")


def test_an_ejected_entry_whose_onto_no_longer_leads_is_reissued_once_on_the_new_target() -> None:
    plan = plan_queue(_ejected_b(leads={"b": False}, **PUSH_SQUASH))
    reissue = _one(plan, "queue-reissue")
    assert reissue.entries == ("b",) and reissue.batch == "b" and reissue.head == "head-b"
    assert (reissue.base, reissue.slots) == ("s1", (1,))
    assert reissue.paths == ("x.py",)
    assert "b" not in plan.entries


def test_an_ejected_entry_whose_onto_still_leads_is_not_reissued() -> None:
    plan = plan_queue(_ejected_b(leads={"b": True}, **PUSH_SQUASH))
    assert "queue-reissue" not in _kinds(plan)


def test_an_unreadable_lead_holds_the_entry_with_a_warning() -> None:
    plan = plan_queue(_ejected_b(leads={"b": None}, **PUSH_SQUASH))
    assert "queue-reissue" not in _kinds(plan)
    warn = _one(plan, "queue-warn")
    assert "b" in warn.detail and warn.key


# ------------------------------------------------------------- (c) the carry hold (R4)


def test_a_carrying_entry_is_not_built_and_yields_one_carry_action() -> None:
    plan = plan_queue(_abc(_built(1, "s1", "a"), carries={"b": ("dead" * 10,)}, **PUSH_SQUASH))
    assert "b" not in plan.entries
    build = _one(plan, "queue-build")
    assert "b" not in build.entries
    carry = _one(plan, "queue-carry")
    assert carry.entries == ("b",) and carry.batch == "b" and carry.head == "head-b"
    assert carry.carried == ("dead" * 10,)
    assert carry.base == "s1" and carry.slots == (1,)


def test_a_carrying_head_already_briefed_is_held_without_a_second_brief() -> None:
    snap = _with_conflict(_abc(carries={"b": ("dead" * 10,)}, **PUSH_SQUASH), "b",
                          onto="s1", reissue=True)  # fmt: skip
    plan = plan_queue(snap)
    assert "b" not in plan.entries and "queue-carry" not in _kinds(plan)


def test_an_empty_carry_builds_as_today() -> None:
    plan = plan_queue(_abc(carries={"a": (), "b": ()}, **PUSH_SQUASH))
    assert _one(plan, "queue-build").entries == ("a", "b")


# ------------------------------------------------------------- (d) unreadable (R5)


@pytest.mark.parametrize("field", ["carries", "leads"])
def test_an_unreadable_carry_or_lead_drops_the_entry_with_a_warning(field: str) -> None:
    plan = plan_queue(_abc(**{field: {"a": None}}, **PUSH_SQUASH))
    assert "a" not in plan.entries
    assert _one(plan, "queue-build").entries == ("b", "c")
    warn = _one(plan, "queue-warn")
    assert "a" in warn.detail and "held" in warn.detail


def test_an_unreadable_lineage_already_warned_is_held_silently() -> None:
    first = plan_queue(_abc(carries={"a": None}, **PUSH_SQUASH))
    key = _one(first, "queue-warn").key
    again = plan_queue(_abc(carries={"a": None}, warned=frozenset({key}), **PUSH_SQUASH))
    assert "a" not in again.entries and "queue-warn" not in _kinds(again)


# ------------------------------------------------------------- (e) main mode


@pytest.mark.parametrize(
    "mode",
    [{"config": QueueConfig(land="merge"), "method": "squash"},
     {"config": QueueConfig(land="push"), "method": "rebase"}],
)  # fmt: skip
def test_under_land_merge_or_rebase_nothing_fires_and_the_eject_names_the_base(
    mode: dict[str, Any],
) -> None:
    plan = plan_queue(
        _abc(
            _built(1, "s1", "a"),
            carries={"c": ("dead" * 10,)},
            conflicts={"b": BuildConflict("head-b", ("x.py",))},
            **mode,
        )
    )
    eject = _one(plan, "queue-eject")
    assert (eject.base, eject.slots) == (MAIN, ())
    assert "queue-carry" not in _kinds(plan) and "queue-warn" not in _kinds(plan)
    reissue = plan_queue(_ejected_b(leads={"b": False}, **mode))
    assert "queue-reissue" not in _kinds(reissue)


# ------------------------------------------------------------- R6: a non-batch entry


def _with_other(snap: QueueSnapshot, **kw: Any) -> QueueSnapshot:
    other = OtherEntry("housekeeping#7", "housekeeping", 7, wave=1, at=snap.now)
    live = {**snap.live, "housekeeping#7": _live(7, "head-hk")}
    return replace(snap, others=(other,), live=live, **kw)


def test_a_carrying_non_batch_entry_is_a_need_naming_the_commit() -> None:
    snap = _with_other(_abc(_built(1, "s1", "a"), **PUSH_SQUASH),
                       carries={"housekeeping#7": ("dead" * 10,)})  # fmt: skip
    plan = plan_queue(snap)
    need = next(a for a in plan.actions if a.kind == "queue-need" and "PR #7" in a.detail)
    assert "s1" in need.detail and "housekeeping#7" not in plan.entries


def test_an_ejected_non_batch_entry_need_names_the_commit_to_merge() -> None:
    events = (_built(1, "s1", "a"),
              {"kind": "queue_eject", "at": AT, "entry": {"pr": 7, "kind": "housekeeping"},
               "reason": "conflict", "head": "head-hk"})  # fmt: skip
    plan = plan_queue(_with_other(_abc(*events, **PUSH_SQUASH)))
    need = next(a for a in plan.actions if a.kind == "queue-need" and "PR #7" in a.detail)
    assert "merge `s1`" in need.detail and "fr-queue/" in need.detail


# ------------------------------------------------------------- review findings of phase 1


def test_a_budget_held_handback_is_not_reissued_when_its_onto_stops_leading() -> None:  # p1-r2
    events = (_built(1, "s1", "a"), _eject("b", "conflict", head="head-b"))
    snap = _with_conflict(_abc(*events, leads={"b": False}, **PUSH_SQUASH), "b", onto="s0",
                          delivered="held", handle=None)  # fmt: skip
    assert "queue-reissue" not in _kinds(plan_queue(snap))


def test_a_carrying_entry_is_not_rebuilt_when_main_moved() -> None:  # p1-r5
    snap = _abc(_built(1, "s1", "a"), carries={"a": ("dead" * 10,)}, base="moved" * 8,
                **PUSH_SQUASH)  # fmt: skip
    plan = plan_queue(snap)
    rebuild = _one(plan, "queue-rebuild")
    assert "a" not in rebuild.entries and rebuild.entries == ("b", "c")
    assert rebuild.slots == (1, 2)
    assert "a" not in plan.entries
    assert _one(plan, "queue-carry").batch == "a"


# ------------------------------------------------------------- lens review (tests)


def test_a_foreign_move_of_main_reissues_once_naming_the_rebuilt_target() -> None:  # l-tests-r3
    """R2's other cause: `main` moved outside the queue, so the hand-back's `onto` (slot 1 on
    the old base) no longer leads. The rebuild pass re-briefs nothing while nothing stands on
    the moved base; the next pass, with the rebuilt combinations recorded, re-issues once on
    the last of them."""
    moved = "mv" * 20
    ejected = (_built(1, "s1", "a"), _eject("b", "conflict", head="head-b"))
    rebuilt = (_built(1, "r1", "a", base=moved, parent=moved),
               _built(2, "r2", "c", base=moved, parent="r1"))  # fmt: skip
    passes = [
        _with_conflict(_abc(*ejected, base=moved, leads={"b": False}, **PUSH_SQUASH), "b",
                       onto="s1"),
        _with_conflict(_abc(*ejected, *rebuilt, base=moved, leads={"b": False}, **PUSH_SQUASH),
                       "b", onto="s1"),
    ]  # fmt: skip
    plans = [plan_queue(p) for p in passes]
    assert "queue-rebuild" in _kinds(plans[0])
    reissues = [a for p in plans for a in p.actions if a.kind == "queue-reissue"]
    assert [(a.batch, a.base, a.slots) for a in reissues] == [("b", "r2", (2,))]


# ------------------------------------------------------------- lens review (errors): R5's hold
# escalates after stall_hours


def test_an_unreadable_onto_held_past_stall_hours_is_a_need_naming_the_commit_and_batch() -> None:
    """l-errors-r4: the hand-back's `onto` git cannot read (a dead slot commit a fresh clone
    lacks) holds the entry each pass; after `stall_hours` from the hand-back it is a Need."""
    young = plan_queue(_ejected_b(leads={"b": None}, config=QueueConfig(land="push"),
                                  method="squash"))  # fmt: skip
    assert "queue-warn" in _kinds(young) and "queue-need" not in _kinds(young)
    old = plan_queue(_ejected_b(leads={"b": None}, config=QueueConfig(land="push",
                                stall_hours=1), method="squash"))  # fmt: skip
    need = _one(old, "queue-need")
    assert need.batch == "b" and need.entries == ("b",) and "s0" in need.detail
    assert "queue-warn" not in _kinds(old) and "queue-reissue" not in _kinds(old)


def test_an_unreadable_head_held_past_stall_hours_is_a_need_naming_the_head() -> None:
    from datetime import timedelta

    from tests.unit.test_wave_queue_planner import NOW

    snap = _abc(carries={"a": None}, head_changed={"a": NOW - timedelta(hours=2)},
                config=QueueConfig(land="push", stall_hours=1), method="squash")  # fmt: skip
    plan = plan_queue(snap)
    need = _one(plan, "queue-need")
    assert need.batch == "a" and "head-a" in need.detail and "a" not in plan.entries
    recent = replace(snap, head_changed={"a": NOW - timedelta(minutes=10)})
    assert "queue-need" not in _kinds(plan_queue(recent))
