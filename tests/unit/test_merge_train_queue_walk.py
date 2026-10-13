"""Queue mode in the pure walk (spec 2026-10-11-merge-train-safety §D "Queue mode", R13):
a repo whose base requires a merge queue picks no head; every approved, green, unqueued
member is enqueued; queued members are in the merge queue; an ejected one is re-enqueued
(base moved), needs you (base unmoved) or goes down the red path; a `version:` block or
`forge.api rest` holds the repo. A repo with no queue is `test_merge_train_gate.py`'s."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fr.ghclient import QueueState
from fr.triage.approval import Approved, Unlabelled
from fr.triage.batch import QueueEntry
from fr.triage.batch_drive import (
    LivePr,
    Snapshot,
    drive_pass,
    train_line,
)
from fr.triage.kanban import action_phrase
from fr.triage.model import Batch, EnqueueEvent, PullRequest
from fr.triage.views import NEED_LABELS, queue_needs

REPO = "derio-net/super-fr"
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def _enq(
    pr: int, head: str, base: str, outcome: str = "enqueued", detail: str = ""
) -> EnqueueEvent:
    return EnqueueEvent(
        kind="enqueue",
        at=NOW,
        pr=pr,
        head=head,
        base=base,
        outcome=outcome,
        detail=detail,  # type: ignore[arg-type]
    )


def _batch(bid: str, *events: Any) -> Batch:
    return Batch.model_validate(
        {
            "id": bid,
            "title": bid,
            "ids": [f"super-fr#{ord(bid[0])}"],
            "events": [
                {"kind": "dispatch", "at": "2026-10-11T10:00:00Z", "runner": "herdr",
                 "handle": "h", "branch": f"feat/batch-{bid}"},
                *[e.model_dump() for e in events],
            ],
        }
    )  # fmt: skip


def _pr(n: int, bid: str, head: str) -> PullRequest:
    return PullRequest(
        repo=REPO, number=n, title=bid, state="OPEN", is_draft=False, url="u",
        head_ref=f"feat/batch-{bid}", head_oid=head, author="operator", cross_repo=False,
    )  # fmt: skip


def _snap(
    members: list[tuple[str, str, Any, QueueState | None, list[Any]]],
    *,
    queue_repos: frozenset[str] = frozenset({REPO}),
    **extra: Any,
) -> Snapshot:
    """*members*: (batch id, checks, approval verdict, queue state, events)."""
    batches = [_batch(bid, *events) for bid, _, _, _, events in members]
    queue = tuple(
        QueueEntry(batch=b, pr=_pr(100 + i, b.id, f"h-{b.id}")) for i, b in enumerate(batches)
    )
    live = {
        b.id: LivePr(number=100 + i, state="OPEN", draft=False, head=f"h-{b.id}", checks=m[1])  # type: ignore[arg-type]
        for i, (b, m) in enumerate(zip(batches, members, strict=True))
    }
    return Snapshot(
        batches=tuple(batches),
        stages={b.id: "pr-open" for b in batches},
        queue=queue,
        live=live,
        repos={b.id: REPO for b in batches},
        now=NOW,
        approvals={m[0]: m[2] for m in members},
        queue_repos=queue_repos,
        queue_states={m[0]: m[3] for m in members if m[3] is not None},
        bases={REPO: "base-2"},
        **extra,
    )


def _kinds(snap: Snapshot) -> list[tuple[str, str]]:
    return [(a.kind, a.batch) for a in drive_pass(snap).actions]


def test_every_approved_green_unqueued_member_is_enqueued_and_none_is_merged() -> None:
    snap = _snap(
        [
            ("a", "green", Approved("h-a"), None, []),
            ("b", "green", Approved("h-b"), None, []),
            ("c", "green", Unlabelled(), None, []),
        ]
    )
    plan = drive_pass(snap)
    assert [(a.kind, a.batch) for a in plan.actions] == [("enqueue", "a"), ("enqueue", "b")]
    assert plan.actions[0].head == "h-a" and plan.actions[0].pr == 100
    (train,) = plan.trains
    assert train.head is None and train.candidates == () and train.awaiting == ("c",)
    assert train.enqueue == ("a", "b")
    assert "enqueue a (#100), b (#101)" in train_line(train)
    assert action_phrase(plan.actions[0]) == "enqueue PR #100"


def test_a_pending_member_waits_and_a_moved_head_is_judged_next_pass() -> None:
    snap = _snap([("a", "pending", Approved("h-a"), None, [])])
    assert _kinds(snap) == []
    moved = _snap([("a", "green", Approved("h-a"), None, [])])
    other = LivePr(100, "OPEN", False, "other", "green")
    moved = Snapshot(**{**moved.__dict__, "live": {"a": other}})
    assert _kinds(moved) == []


def test_a_queued_member_is_in_the_merge_queue_whichever_flag_says_so() -> None:
    snap = _snap(
        [
            ("a", "green", Approved("h-a"), QueueState(True, True), [_enq(100, "h-a", "base-1")]),
            ("b", "green", Approved("h-b"), QueueState(None, True), [_enq(101, "h-b", "base-1")]),
            ("c", "green", Approved("h-c"), QueueState(False, True), [_enq(102, "h-c", "base-1")]),
        ]
    )
    plan = drive_pass(snap)
    assert plan.actions == ()
    assert plan.trains[0].in_merge_queue == ("a", "b", "c")


def test_a_pr_waiting_to_enter_the_queue_is_never_taken_for_ejected() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, True), [_enq(100, "h-a", "base-1")])]
    )
    assert _kinds(snap) == []


def test_ejected_green_with_the_base_moved_is_enqueued_again() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, False), [_enq(100, "h-a", "base-1")])]
    )
    plan = drive_pass(snap)
    assert [(a.kind, a.batch) for a in plan.actions] == [("enqueue", "a")]


def test_ejected_green_with_the_base_unmoved_is_recorded_then_a_need_from_events() -> None:
    members = [
        ("a", "green", Approved("h-a"), QueueState(False, False), [_enq(100, "h-a", "base-2")])
    ]
    plan = drive_pass(_snap(members))
    (action,) = plan.actions
    assert action.kind == "warn" and not action.red and action.ejected and action.head == "h-a"
    assert action.detail == "PR #100 left the merge queue unmerged"
    # the driver records it (an `ejected` event); the walk then says nothing, and the Need
    # is read from the events, so the facts-only needs_you shows it
    recorded = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, False),
          [_enq(100, "h-a", "base-2"), _enq(100, "h-a", "base-2", "ejected")])]
    )  # fmt: skip
    assert drive_pass(recorded).actions == ()
    (need,) = [n for n in queue_needs(recorded) if n.kind == "queue-ejected"]
    assert need.ref == "a" and "left the merge queue unmerged" in need.text
    assert NEED_LABELS["queue-ejected"]


def test_an_ejected_event_with_the_base_moved_since_enqueues_again() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, False),
          [_enq(100, "h-a", "base-1"), _enq(100, "h-a", "base-1", "ejected")])]
    )  # fmt: skip
    assert _kinds(snap) == [("enqueue", "a")]


def test_a_dequeued_pr_is_enqueued_afresh_when_it_is_approved_again() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, False),
          [_enq(100, "h-a", "base-2"), _enq(100, "h-a", "base-2", "dequeued")])]
    )  # fmt: skip
    assert _kinds(snap) == [("enqueue", "a")]


def test_a_merged_pr_read_after_the_view_is_never_taken_for_ejected() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), QueueState(False, False, open=False),
          [_enq(100, "h-a", "base-2")])]
    )  # fmt: skip
    assert _kinds(snap) == []


def test_two_refusals_at_a_head_stop_the_retries_and_are_a_need() -> None:
    one = [_enq(100, "h-a", "base-2", "refused", "not mergeable")]
    assert _kinds(_snap([("a", "green", Approved("h-a"), None, one)])) == [("enqueue", "a")]
    two = [*one, _enq(100, "h-a", "base-2", "refused", "not mergeable")]
    snap = _snap([("a", "green", Approved("h-a"), None, two)])
    assert _kinds(snap) == []
    (need,) = queue_needs(snap)
    assert need.kind == "enqueue-refused" and "not mergeable" in need.text
    assert queue_needs(_snap([("a", "green", Approved("h-a"), None, one)])) == []


def test_a_new_head_resets_the_refusals() -> None:
    old = [_enq(100, "old", "base-2", "refused"), _enq(100, "old", "base-2", "refused")]
    assert _kinds(_snap([("a", "green", Approved("h-a"), None, old)])) == [("enqueue", "a")]


def test_ejected_red_goes_down_the_red_path() -> None:
    snap = _snap(
        [("a", "failing", Approved("h-a"), QueueState(False, False), [_enq(100, "h-a", "base-1")])]
    )
    (action,) = drive_pass(snap).actions
    assert action.kind == "warn" and action.red


def test_a_red_member_still_in_the_queue_is_left_to_the_queue() -> None:
    snap = _snap(
        [("a", "failing", Approved("h-a"), QueueState(True, True), [_enq(100, "h-a", "base-1")])]
    )
    plan = drive_pass(snap)
    assert plan.actions == () and plan.trains[0].in_merge_queue == ("a",)


def test_a_version_block_holds_the_repo() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), None, []), ("b", "green", Approved("h-b"), None, [])],
        queue_versioned=frozenset({REPO}),
    )
    plan = drive_pass(snap)
    assert [(a.kind, a.batch) for a in plan.actions] == [("held", "a")]
    assert plan.actions[0].detail == (
        f"{REPO} requires a merge queue, and fr does not reserve versions through one"
    )
    assert plan.trains[0].enqueue == ()
    assert "merge queue" in action_phrase(plan.actions[0])


def test_forge_api_rest_holds_the_repo() -> None:
    snap = _snap([("a", "green", Approved("h-a"), None, [])], queue_rest=True)
    (action,) = drive_pass(snap).actions
    assert action.kind == "held"
    assert action.detail == (f"{REPO} requires a merge queue, and forge.api rest cannot enqueue")


def test_a_repo_without_a_queue_keeps_its_train() -> None:
    snap = _snap([("a", "green", Approved("h-a"), None, [])], queue_repos=frozenset())
    plan = drive_pass(snap)
    assert [(a.kind, a.batch) for a in plan.actions] == [("merge", "a")]
    assert plan.trains[0].head == "a" and plan.trains[0].enqueue == ()


def test_a_held_queue_repo_still_reports_a_red_member_so_recovery_runs() -> None:
    snap = _snap(
        [("a", "failing", Approved("h-a"), None, []), ("b", "green", Approved("h-b"), None, [])],
        queue_rest=True,
    )
    kinds = [(a.kind, a.batch, a.red) for a in drive_pass(snap).actions]
    assert kinds == [("held", "a", False), ("warn", "a", True)]


def test_an_unknown_default_branch_holds_the_repo_with_its_words() -> None:
    snap = _snap([("a", "green", Approved("h-a"), None, [])], queue_unknown=frozenset({REPO}))
    (action,) = drive_pass(snap).actions
    assert action.kind == "held"
    assert action.detail == f"cannot tell {REPO}'s default branch: queue mode unknown"


def test_facts_only_views_show_an_enqueued_pr_in_the_merge_queue_not_merge_ready() -> None:
    snap = _snap(
        [("a", "green", Approved("h-a"), None, [_enq(100, "h-a", "base-1")]),
         ("b", "green", Approved("h-b"), None, [])],
        queue_repos=frozenset(),
        queue_inferred=True,
    )  # fmt: skip
    plan = drive_pass(snap)
    assert [(a.kind, a.batch) for a in plan.actions] == [("merge", "b")]
    assert plan.trains[0].in_merge_queue == ("a",)
    assert "in merge queue a (#100)" in train_line(plan.trains[0])
    live = _snap([("a", "green", Approved("h-a"), None, [_enq(100, "h-a", "base-1")])],
                 queue_repos=frozenset())  # fmt: skip
    assert [a.kind for a in drive_pass(live).actions] == ["merge"]  # a live pass reads the rules
