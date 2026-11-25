"""The pure planner's operator entries (spec 2026-11-24-wave-queue-gaps R12, R14, R15, §C,
§F 8, 10): an `operator` entry joins whichever queue is open, opens a between-waves one while
idle, holds a wave's drain while pending and stalls it into a Need, and is ejected with reason
`operator` when removed from a combination."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from fr.triage.approval import First
from fr.triage.batch_drive import LivePr
from fr.triage.model import Batch, QueueRecord
from fr.triage.wave_queue import (
    Hold,
    OtherEntry,
    QueueAction,
    QueueConfig,
    QueuePlan,
    QueueSnapshot,
    SlotCheck,
    operator_work,
    plan_queue,
    replay,
)

REPO = "derio-net/super-fr"
ME = "s-11111111"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
AT = "2026-11-20T10:00:00Z"
MAIN = "m0" * 20
OP = "operator#7"


def _batch(bid: str, n: int, *, wave: int | None = 1) -> Batch:
    return Batch.model_validate({
        "id": bid, "title": bid, "ids": [f"super-fr#{n}"], "wave": wave,
        "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": f"feat/batch-{bid}"}],
    })  # fmt: skip


def _live(n: int, head: str = "", checks: str = "green") -> LivePr:
    return LivePr(number=n, state="OPEN", draft=False, head=head or f"head-{n}", checks=checks)


def _ref(key: str) -> dict[str, Any]:
    if "#" in key:
        kind, n = key.split("#")
        return {"pr": int(n), "kind": kind}
    return {"batch": key}


def _record(*events: dict[str, Any], wave: int | None = 1) -> QueueRecord:
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": wave, "scope": ME, "base": MAIN,
         "events": [{"kind": "queue_open", "at": AT}, *events]}
    )  # fmt: skip


def _built(slot: int, sha: str, key: str, *, parent: str = MAIN) -> dict[str, Any]:
    return {"kind": "queue_built", "at": AT, "slot": slot, "sha": sha, "entry": _ref(key),
            "head": f"head-{key}", "patch_id": f"pid-{key}", "base": MAIN,
            "parent": parent}  # fmt: skip


def _land(main: str, *keys: str, at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_land", "at": at, "main": main, "entries": [_ref(k) for k in keys]}


def _operator(n: int = 7, *, checks: str = "green") -> tuple[OtherEntry, dict[str, LivePr]]:
    key = f"operator#{n}"
    entry = OtherEntry(key=key, kind="operator", pr=n, wave=None, at=NOW - timedelta(hours=1))
    return entry, {key: _live(n, f"head-{key}", checks)}


def _qs(batches: Sequence[Batch], stages: dict[str, str], live: dict[str, LivePr],
        **kw: Any) -> QueueSnapshot:  # fmt: skip
    kw.setdefault("approvals", {b.id: First(live[b.id].head) for b in batches if b.id in live})
    kw.setdefault("base", MAIN)
    return QueueSnapshot(repo=REPO, scope=ME, config=kw.pop("config", QueueConfig()), now=NOW,
                         batches=tuple(batches), stages=stages, live=live,  # type: ignore[arg-type]
                         **kw)  # fmt: skip


def _kinds(plan: QueuePlan) -> list[str]:
    return [a.kind for a in plan.actions]


def _one(plan: QueuePlan, kind: str) -> QueueAction:
    (got,) = [a for a in plan.actions if a.kind == kind]
    return got


OPEN1 = Hold(state="open", scope=ME, wave=1, parent=MAIN)


# ------------------------------------------------------------------ R14: which queue


def test_an_operator_entry_joins_the_open_queue_whatever_its_wave() -> None:
    entry, live = _operator()
    b = _batch("b", 2, wave=2)
    live |= {"b": _live(102, "head-b")}
    rec = _record(wave=2)
    plan = plan_queue(_qs([b], {"b": "pr-open"}, live, records=(rec,), others=(entry,),
                          hold=replace(OPEN1, wave=2)))  # fmt: skip
    assert set(_one(plan, "queue-build").entries) == {"b", OP}


def test_while_idle_a_ready_operator_entry_opens_a_between_waves_queue_at_once() -> None:
    entry, live = _operator()
    plan = plan_queue(_qs([_batch("a", 1)], {"a": "dispatched"}, live, others=(entry,)))
    opened = _one(plan, "queue-open")
    assert opened.wave is None and opened.entries == (OP,)


def test_when_the_lowest_wave_has_a_ready_entry_that_wave_opens_and_the_entry_joins_it() -> None:
    entry, live = _operator()
    a = _batch("a", 1)
    live |= {"a": _live(101, "head-a")}
    snap = _qs([a], {"a": "pr-open"}, live, others=(entry,))
    opened = _one(plan_queue(snap), "queue-open")
    assert opened.wave == 1
    joined = plan_queue(replace(snap, records=(_record(),), hold=OPEN1))
    assert set(_one(joined, "queue-build").entries) == {"a", OP}


def test_a_red_operator_entry_opens_nothing() -> None:
    entry, live = _operator(checks="failing")
    plan = plan_queue(_qs([_batch("a", 1)], {"a": "dispatched"}, live, others=(entry,)))
    assert "queue-open" not in _kinds(plan)


def test_an_operator_entry_lands_like_any_entry() -> None:
    entry, live = _operator()
    rec = _record(_built(1, "s1", OP), wave=None)
    hold = replace(OPEN1, wave=None)
    plan = plan_queue(_qs([], {}, live, records=(rec,), others=(entry,), hold=hold,
                          slots={"s1": SlotCheck("green")}))  # fmt: skip
    assert _one(plan, "queue-land").entries == (OP,)


# ------------------------------------------------------------------ R15: drain and stall


def _landed_wave(**kw: Any) -> QueueSnapshot:
    a = _batch("a", 1)
    rec = _record(_built(1, "s1", "a"), _land("s1", "a", at=kw.pop("land_at", AT)))
    return _qs([a], {"a": "merged"}, kw.pop("live", {}), records=(rec,), hold=OPEN1, base="s1",
               **kw)  # fmt: skip


def test_a_wave_queue_drains_once_nothing_is_pending() -> None:
    assert "queue-drain" in _kinds(plan_queue(_landed_wave()))


def test_a_wave_queue_does_not_drain_while_an_operator_entry_is_pending() -> None:
    plan = plan_queue(_landed_wave(pending_operator={OP: NOW - timedelta(hours=1)}))
    assert "queue-drain" not in _kinds(plan) and "queue-need" not in _kinds(plan)


def test_a_pending_entry_that_held_the_drain_for_stall_hours_is_a_need_naming_remove() -> None:
    plan = plan_queue(_landed_wave(pending_operator={OP: NOW - timedelta(hours=5)},
                                   scope_args=("--repo", REPO),
                                   config=QueueConfig(stall_hours=1)))  # fmt: skip
    need = _one(plan, "queue-need")
    assert "fr triage queue remove --pr 7 --repo derio-net/super-fr" in need.detail
    assert "queue-drain" not in _kinds(plan)


def test_a_pending_entry_is_the_drivers_work_until_its_stall_need_makes_it_the_operators(
) -> None:  # fmt: skip
    """Review p2-r2: the drive counts a pending entry as pending work, and a stalled one not
    again (its Need is already blocked)."""
    waiting = {OP: NOW - timedelta(hours=1)}
    stalled = {OP: NOW - timedelta(hours=5)}
    assert operator_work({REPO: waiting}, [plan_queue(_landed_wave(pending_operator=waiting))]) == 1
    plan = plan_queue(_landed_wave(pending_operator=stalled, config=QueueConfig(stall_hours=1)))
    assert _one(plan, "queue-need").entries == (OP,)
    assert operator_work({REPO: stalled}, [plan]) == 0
    assert operator_work({REPO: waiting}, []) == 1  # no queue planned: still work


def test_the_stall_counts_from_the_later_of_the_add_and_the_last_landing() -> None:
    recent = (NOW - timedelta(hours=1)).isoformat()
    plan = plan_queue(_landed_wave(pending_operator={OP: NOW - timedelta(hours=9)},
                                   land_at=recent))  # fmt: skip
    assert "queue-need" not in _kinds(plan) and "queue-drain" not in _kinds(plan)


def test_a_landed_operator_entry_is_never_pending() -> None:
    a = _batch("a", 1)
    rec = _record(_built(1, "s1", "a"), _built(2, "s2", OP, parent="s1"), _land("s2", "a", OP))
    plan = plan_queue(_qs([a], {"a": "merged"}, {}, records=(rec,), hold=OPEN1, base="s2",
                          pending_operator={OP: NOW - timedelta(hours=1)}))  # fmt: skip
    assert "queue-drain" in _kinds(plan)


def test_a_between_waves_queue_drains_by_its_own_rule() -> None:
    rec = _record(_built(1, "s1", OP), _land("s1", OP), wave=None)
    plan = plan_queue(_qs([], {}, {}, records=(rec,), hold=replace(OPEN1, wave=None), base="s1",
                          pending_operator={"operator#8": NOW - timedelta(hours=9)},
                          config=QueueConfig(stall_hours=1)))  # fmt: skip
    assert "queue-drain" in _kinds(plan)  # operator#8 holds no between-waves drain, but it
    assert _one(plan, "queue-need").entries == ("operator#8",)  # has a Need (l-errors-r2)


# ------------------------------------------------------------------ l-errors-r2: every pending
# operator entry has a Need, whatever the queue's state


def test_a_trust_refused_entry_is_a_need_at_once_whatever_the_queue_state() -> None:
    snap = _qs([_batch("a", 1)], {"a": "dispatched"}, {}, scope_args=("--repo", REPO),
               pending_operator={OP: NOW - timedelta(minutes=1)},
               refused_operator={OP: "its branch is in another repository"})  # fmt: skip
    plan = plan_queue(snap)
    assert plan.phase == "idle"
    need = _one(plan, "queue-need")
    assert need.entries == (OP,) and "another repository" in need.detail
    assert "fr triage queue remove --pr 7 --repo derio-net/super-fr" in need.detail
    assert operator_work({REPO: snap.pending_operator}, [plan]) == 0  # blocked: the loop can end


def test_an_entry_that_never_becomes_ready_is_a_need_after_stall_hours_with_no_queue() -> None:
    fresh = _qs([], {}, {}, pending_operator={OP: NOW - timedelta(minutes=30)},
                config=QueueConfig(stall_hours=1))  # fmt: skip
    assert "queue-need" not in _kinds(plan_queue(fresh))
    assert operator_work({REPO: fresh.pending_operator}, [plan_queue(fresh)]) == 1
    stale = replace(fresh, pending_operator={OP: NOW - timedelta(hours=2)})
    plan = plan_queue(stale)
    need = _one(plan, "queue-need")
    assert need.entries == (OP,) and "fr triage queue remove --pr 7" in need.detail
    assert operator_work({REPO: stale.pending_operator}, [plan]) == 0


def test_an_entry_waiting_in_a_wave_queue_still_gets_its_need() -> None:
    entry, live = _operator(checks="pending")
    a = _batch("a", 1)
    live |= {"a": _live(101, "head-a")}
    plan = plan_queue(_qs([a], {"a": "pr-open"}, live, records=(_record(),), others=(entry,),
                          hold=OPEN1, pending_operator={OP: NOW - timedelta(hours=9)}))  # fmt: skip
    (need,) = [x for x in plan.actions if x.kind == "queue-need" and x.entries == (OP,)]
    assert "fr triage queue remove --pr 7" in need.detail


# ------------------------------------------------------------------ R12: remove ejects


def test_a_removed_entry_in_a_combination_is_ejected_with_reason_operator() -> None:
    a = _batch("a", 1)
    live = {"a": _live(101, "head-a")}
    rec = _record(_built(1, "s1", "a"), _built(2, "s2", OP, parent="s1"))
    plan = plan_queue(_qs([a], {"a": "pr-open"}, live, records=(rec,), hold=OPEN1,
                          removed=frozenset({OP})))  # fmt: skip
    eject = _one(plan, "queue-eject")
    assert (eject.entries, eject.reason, eject.head) == ((OP,), "operator", f"head-{OP}")


def test_an_operator_ejection_is_no_verdict_on_its_head() -> None:
    eject = {"kind": "queue_eject", "at": AT, "entry": _ref(OP), "reason": "operator",
             "head": f"head-{OP}"}  # fmt: skip
    rep = replay(_record(_built(1, "s1", OP), eject, wave=None))
    assert OP not in rep.order and OP not in rep.ejected


def test_the_executor_records_an_operator_eject_and_hands_nothing_back() -> None:
    from types import SimpleNamespace

    from fr.triage.model import QueueEjectEvent
    from fr.triage.queue_exec import QueueExecutor

    written: list[Any] = []
    handed: list[Any] = []
    ports = SimpleNamespace(record=written.append, now=lambda: NOW,
                            hand_back=lambda action: handed.append(action) or "handed")  # fmt: skip
    action = QueueAction("queue-eject", REPO, f"eject {OP}: removed", entries=(OP,),
                         reason="operator", head=f"head-{OP}")  # fmt: skip
    said = QueueExecutor(ports)._eject(action, _record(_built(1, "s1", OP)))  # type: ignore[arg-type]

    (event,) = written
    assert isinstance(event, QueueEjectEvent) and event.reason == "operator"
    assert event.entry.kind == "operator" and event.entry.pr == 7
    assert said == "ejected" and handed == []
