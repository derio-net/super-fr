"""The DevOps barrier in the pure planner (spec 2026-11-19-wave-merge-queue R26, §J).

A PR that `gate:devops` holds before merge enters the queue only once its `fr-queue:release`
label is settled (`QueueSnapshot.released`), lands as the last entry of its push, and
lands nothing behind it until `queue_postmerge_done`; a combination behind it is built and
tested meanwhile. After it lands, a Need names `fr ops gate --run <id>`.
"""

from __future__ import annotations

from typing import Any

from fr.triage.batch_drive import LivePr
from fr.triage.wave_queue import Hold, QueueSnapshot, plan_queue

from tests.unit.test_wave_queue_planner import (
    MAIN,
    ME,
    _approved,
    _batch,
    _built,
    _green,
    _kinds,
    _land,
    _live,
    _one,
    _open,
    _qs,
    _record,
)

HELD = ("gate:devops",)


def _wave(*events: dict[str, Any], released: bool = True, queue: bool = True,
          **kw: Any) -> QueueSnapshot:  # fmt: skip
    """A wave-1 queue of a, d, e at depth 3 (open with *events*, or not yet); `d` is the
    gate:devops entry."""
    batches = [
        _batch("a", 1, events=[_approved(100, 10)]),
        _batch("d", 2, events=[_approved(101, 20)]),
        _batch("e", 3, events=[_approved(102, 30)]),
    ]
    numbers = {"a": 100, "d": 101, "e": 102}
    stages = kw.pop("stages", dict.fromkeys("ade", "pr-open"))
    live: dict[str, LivePr] = {
        "a": _live(100, "head-a"),
        "d": _live(101, "head-d", labels=HELD),
        "e": _live(102, "head-e"),
    }
    if queue:
        kw["records"] = (_record(_open(), *events),)
        kw["hold"] = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    kw.setdefault("config", _config())
    return _qs(batches, stages, numbers=numbers, live=live,
               released=frozenset({"d"}) if released else frozenset(), **kw)  # fmt: skip


def _config() -> Any:
    from fr.triage.wave_queue import QueueConfig

    return QueueConfig(depth=3)


def _release(bid: str = "d", at: str = "2026-11-20T10:00:00Z") -> dict[str, Any]:
    return {"kind": "queue_release", "at": at, "entry": {"batch": bid}, "head": f"head-{bid}",
            "patch_id": f"pid-{bid}"}  # fmt: skip


def _postmerge_done(bid: str = "d", at: str = "2026-11-20T11:30:00Z") -> dict[str, Any]:
    return {"kind": "queue_postmerge_done", "at": at, "entry": {"batch": bid}}


def _chain() -> list[dict[str, Any]]:
    return [_built(1, "s1", "a"), _built(2, "s2", "d", parent="s1"),
            _built(3, "s3", "e", parent="s2")]  # fmt: skip


def test_a_gate_devops_entry_is_not_ready_until_its_release_is_settled() -> None:
    held_only = {"d": "pr-open", "a": "merged", "e": "merged"}
    plan = plan_queue(_wave(released=False, queue=False, stages=held_only))
    assert plan.actions == () and plan.waiting == ()  # nothing is ready: no queue opens
    plan = plan_queue(_wave(released=True, queue=False, stages=held_only))
    assert _one(plan, "queue-open").wave == 1  # the settled release makes it ready


def test_an_unreleased_gate_devops_entry_is_never_built_into_the_queue() -> None:
    plan = plan_queue(_wave(released=False))
    assert plan.entries == ("a", "e")


def test_the_barrier_lands_as_the_last_entry_of_its_push_and_nothing_behind_it() -> None:
    plan = plan_queue(_wave(*_chain(), _release(), slots=_green("s1", "s2", "s3")))
    land = _one(plan, "queue-land")
    assert (land.entries, land.sha) == (("a", "d"), "s2")  # e is built on s2 but not landed
    assert plan.entries == ("e",)


def test_a_combination_behind_the_barrier_is_built_and_tested_meanwhile() -> None:
    plan = plan_queue(_wave(_built(1, "s1", "a"), _release()))
    build = _one(plan, "queue-build")
    assert build.entries == ("d", "e") and build.base == "s1"


def test_nothing_lands_after_the_barrier_until_its_post_merge_ops_are_done() -> None:
    events = [*_chain(), _release(), _land("s2", "a", "d")]
    plan = plan_queue(_wave(*events, slots=_green("s3"), base="s2"))
    assert "queue-land" not in _kinds(plan)
    assert plan.entries == ("e",)
    need = _one(plan, "queue-need")
    assert "fr ops gate --run <run-id>" in need.detail and "d landed" in need.detail
    plan = plan_queue(
        _wave(*events, slots=_green("s3"), base="s2", runs={"d": "2026-11-20-feat-x"})
    )
    assert "fr ops gate --run 2026-11-20-feat-x" in _one(plan, "queue-need").detail


def test_the_queue_lands_on_once_the_post_merge_ops_are_done() -> None:
    events = [*_chain(), _release(), _land("s2", "a", "d"), _postmerge_done()]
    plan = plan_queue(
        _wave(
            *events,
            slots=_green("s3"),
            base="s2",
            stages={"a": "merged", "d": "merged", "e": "pr-open"},
        )
    )
    land = _one(plan, "queue-land")
    assert land.entries == ("e",) and "queue-need" not in _kinds(plan)


def test_the_wave_does_not_drain_while_a_barrier_is_open() -> None:
    events = [_built(1, "s1", "d"), _release(), _land("s1", "d")]
    batches = [_batch("d", 2, events=[_approved(101, 20)])]
    qs = _qs(
        batches,
        {"d": "merged"},
        live={},
        records=(_record(_open(), *events),),
        base="s1",
        hold=Hold(state="open", scope=ME, wave=1, parent=MAIN),
        config=_config(),
    )
    plan = plan_queue(qs)
    assert "queue-drain" not in _kinds(plan) and "queue-need" in _kinds(plan)
    done = _qs(
        batches,
        {"d": "merged"},
        live={},
        base="s1",
        records=(_record(_open(), *events, _postmerge_done()),),
        hold=Hold(state="open", scope=ME, wave=1, parent=MAIN),
        config=_config(),
    )
    assert "queue-drain" in _kinds(plan_queue(done))


def test_a_voided_release_is_no_barrier_and_the_queue_lands_without_blocking() -> None:
    """p6-r9: a void is its own flag; an ungated entry (released=False) lands on."""
    from fr.triage.wave_queue import barrier_keys

    void = {**_release(), "voided": True}
    events = [*_chain(), _release(), void, _land("s2", "a", "d")]
    plan = plan_queue(_wave(*events, slots=_green("s3"), base="s2", released=False))
    assert "queue-need" not in _kinds(plan)
    rec = _wave(*events, released=False).records
    assert barrier_keys(rec) == frozenset()
    assert barrier_keys(_wave(_release(), void, _release(at="2026-11-20T10:45:00Z")).records) == {
        "d"
    }


def test_a_release_at_an_empty_diff_is_a_live_barrier() -> None:
    from fr.triage.wave_queue import barrier_keys

    empty = {**_release(), "patch_id": ""}
    assert barrier_keys(_wave(empty).records) == {"d"}
