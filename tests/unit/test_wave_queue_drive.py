"""`drive_pass` with the wave merge queue wired in (spec 2026-11-19-wave-merge-queue §A, R36).

A repo in `Snapshot.wave_queues` is planned by `fr.triage.wave_queue.plan_queue` in place of
its merge train; until the queue's executor lands, the driver runs only the queue's report
actions (held, Needs, warns) and says the rest.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fr.triage.batch_drive import Snapshot, drive_pass
from fr.triage.model import QueueRecord
from fr.triage.wave_queue import Hold, QueueConfig

from tests.unit.test_triage_batch_drive import REPO, SID, _batch, _dispatched, _kinds, _snap

OTHER = "s-22222222"
MAIN = "m" * 40


def _record(wave: int | None = 1) -> QueueRecord:
    return QueueRecord.model_validate(
        {
            "repo": REPO,
            "wave": wave,
            "scope": SID,
            "base": MAIN,
            "events": [{"kind": "queue_open", "at": "2026-10-02T10:00:00Z"}],
        }  # fmt: skip
    )


def _queued(snap: Snapshot, **kw: Any) -> Snapshot:
    return replace(snap, wave_queues={REPO: QueueConfig()}, bases={REPO: MAIN}, **kw)


def test_a_queue_repo_walks_no_train_and_merges_nothing() -> None:
    batches = [_dispatched("a", 1)]
    plain = drive_pass(_snap(batches, {"a": "pr-open"}))
    assert ("merge", "a") in _kinds(plain.actions) and plain.queues == ()
    got = drive_pass(_queued(_snap(batches, {"a": "pr-open"})))
    assert "merge" not in {a.kind for a in got.actions} and got.trains == ()
    (plan,) = got.queues
    assert plan.repo == REPO and [a.kind for a in plan.actions] == ["queue-open"]


def test_an_open_queue_plans_a_build_and_no_report_reaches_the_actions() -> None:
    batches = [_dispatched("a", 1)]
    hold = Hold(state="open", scope=SID, wave=1, parent=MAIN)
    got = drive_pass(_queued(_snap(batches, {"a": "pr-open"}), queue_records=(_record(),),
                             queue_holds={REPO: hold}))  # fmt: skip
    (plan,) = got.queues
    assert [a.kind for a in plan.actions] == ["queue-build"] and plan.entries == ("a",)
    assert not any(a.kind.startswith("queue-") for a in got.actions)


def test_another_scopes_hold_is_a_held_action_of_the_pass() -> None:
    hold = Hold(state="open", scope=OTHER, wave=1, parent=MAIN)
    got = drive_pass(_queued(_snap([_dispatched("a", 1)], {"a": "pr-open"}),
                             queue_holds={REPO: hold}))  # fmt: skip
    (held,) = [a for a in got.actions if a.kind == "held"]
    assert held.batch == REPO and OTHER in held.detail


def test_a_stall_proposal_is_a_blocked_action_the_summary_counts() -> None:
    spent = [
        {"kind": "red_handback", "at": f"2026-10-01T11:0{i}:00Z", "pr": 1000, "head": f"r{i}",
         "checks": ["t"], "delivered": "session"}
        for i in range(2)
    ]  # fmt: skip
    batches = [_dispatched("a", 1, events=spent), _dispatched("b", 2)]
    hold = Hold(state="open", scope=SID, wave=1, parent=MAIN)
    snap = _snap(batches, {"a": "pr-open", "b": "merged"})
    live = {"a": replace(snap.live["a"], checks="failing")}
    got = drive_pass(_queued(snap, live=live, queue_records=(_record(),),
                             queue_holds={REPO: hold}))  # fmt: skip
    (need,) = [a for a in got.actions if a.kind == "blocked"]
    assert need.batch == "a" and "fr triage batch defer a" in need.detail
    assert got.summary.blocked == 1


def test_later_waves_waiting_prs_take_no_in_flight_slot_while_the_queue_is_open() -> None:
    batches = [
        _dispatched("w1a", 1, wave=1),
        _dispatched("w2a", 2, wave=2),
        _dispatched("w2b", 3, wave=2),
        _batch("w1b", 4, wave=1),
    ]
    stages = {"w1a": "dispatched", "w2a": "pr-open", "w2b": "pr-open", "w1b": "proposed"}
    hold = Hold(state="open", scope=SID, wave=1, parent=MAIN)
    # unapproved, so no train merges them: they wait, as delivered PRs do on a later queue
    capped = drive_pass(_snap(batches, stages, max_inflight=2, approvals={}))
    assert ("dispatch", "w1b") not in _kinds(capped.actions)
    got = drive_pass(_queued(_snap(batches, stages, max_inflight=2, approvals={}),
                             queue_records=(_record(),), queue_holds={REPO: hold}))  # fmt: skip
    assert ("dispatch", "w1b") in _kinds(got.actions)
    # an idle queue (none open) spares nothing: R36 holds only while the queue is open
    idle = drive_pass(_queued(_snap(batches, stages, max_inflight=2, approvals={})))
    assert ("dispatch", "w1b") not in _kinds(idle.actions)
