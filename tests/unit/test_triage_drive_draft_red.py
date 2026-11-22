"""R15/R16: an unapproved draft batch PR with failing checks is reported red by both walks
(merge train and queue mode), sits in `Train.stepped`, and is never a member, merge
candidate or stop. An unapproved green draft stays invisible."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fr.ghclient import QueueState
from fr.triage.approval import Approved, Unlabelled
from fr.triage.batch import QueueEntry
from fr.triage.batch_drive import LivePr, Pass, Snapshot, drive_pass, train_line
from fr.triage.model import Batch, PullRequest

REPO = "derio-net/super-fr"
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


def _batch(bid: str) -> Batch:
    return Batch.model_validate(
        {
            "id": bid,
            "title": bid,
            "ids": [f"super-fr#{ord(bid[0])}"],
            "events": [
                {"kind": "dispatch", "at": "2026-11-19T10:00:00Z", "runner": "herdr",
                 "handle": "h", "branch": f"feat/batch-{bid}"},
            ],
        }
    )  # fmt: skip


def _pr(n: int, bid: str, head: str) -> PullRequest:
    return PullRequest(
        repo=REPO, number=n, title=bid, state="OPEN", is_draft=False, url="u",
        head_ref=f"feat/batch-{bid}", head_oid=head, author="operator", cross_repo=False,
    )  # fmt: skip


def walk(rows: list[tuple[str, bool, str, Any]], *, queue: bool = False, **live_extra: Any) -> Pass:
    """*rows*: (batch id, draft, checks, approval verdict)."""
    batches = [_batch(bid) for bid, *_ in rows]
    entries = tuple(
        QueueEntry(batch=b, pr=_pr(100 + i, b.id, f"h-{b.id}")) for i, b in enumerate(batches)
    )
    live = {
        b.id: LivePr(
            number=100 + i, state="OPEN", draft=r[1], head=f"h-{b.id}", checks=r[2],  # type: ignore[arg-type]
            failing=("ci",) if r[2] == "failing" else (), **live_extra.get(b.id, {}),
        )
        for i, (b, r) in enumerate(zip(batches, rows, strict=True))
    }  # fmt: skip
    extra: dict[str, Any] = {}
    if queue:
        extra = {
            "queue_repos": frozenset({REPO}),
            "queue_states": {b.id: QueueState(False, False) for b in batches},
            "bases": {REPO: "base-2"},
        }
    snap = Snapshot(
        batches=tuple(batches),
        stages={b.id: "pr-open" for b in batches},
        queue=entries,
        live=live,
        repos={b.id: REPO for b in batches},
        now=NOW,
        approvals={r[0]: r[3] for r in rows},
        **extra,
    )
    return drive_pass(snap)


@pytest.mark.parametrize("queue", [False, True])
def test_a_red_unapproved_draft_alone_is_reported_and_stepped_over(queue: bool) -> None:
    plan = walk([("a", True, "failing", Unlabelled())], queue=queue)
    (warn,) = [a for a in plan.actions if a.kind == "warn"]
    assert warn.red and warn.batch == "a" and warn.pr == 100 and warn.head == "h-a"
    assert warn.checks == ("ci",)
    (train,) = plan.trains
    assert train.stepped == ("a",) and train.head is None and train.candidates == ()
    assert "a (#100)" in train_line(train)


@pytest.mark.parametrize("queue", [False, True])
def test_a_red_draft_beside_members_never_becomes_a_candidate_or_a_stop(queue: bool) -> None:
    plan = walk(
        [("a", True, "failing", Unlabelled()), ("b", False, "green", Approved("h-b"))],
        queue=queue,
    )
    kinds = [(a.kind, a.batch) for a in plan.actions]
    assert ("warn", "a") in kinds
    assert ("enqueue" if queue else "merge", "b") in kinds
    (train,) = plan.trains
    assert train.stepped == ("a",) and train.numbers["a"] == 100
    assert train.queued == ()
    if not queue:
        assert train.head == "b" and train.candidates == ("b",)


@pytest.mark.parametrize("queue", [False, True])
def test_a_green_or_pending_unapproved_draft_yields_nothing_new(queue: bool) -> None:
    for checks in ("green", "pending"):
        plan = walk([("a", True, checks, Unlabelled())], queue=queue)
        assert plan.actions == () and plan.trains == ()


# ------------------------------------------------------------ R17: the conflict probe

DIRTY: dict[str, Any] = {"mergeable": "CONFLICTING", "merge_state": "DIRTY"}


def probes(plan: Pass) -> list[str]:
    return [a.batch for a in plan.actions if a.kind == "conflict-probe"]


@pytest.mark.parametrize("queue", [False, True])
def test_a_conflicting_unapproved_draft_is_probed_whatever_its_checks(queue: bool) -> None:
    for checks in ("green", "pending", "failing"):
        plan = walk([("a", True, checks, Unlabelled())], queue=queue, a=DIRTY)
        assert probes(plan) == ["a"], checks
        (probe,) = [a for a in plan.actions if a.kind == "conflict-probe"]
        assert (probe.pr, probe.head) == (100, "h-a")
    plan = walk([("a", True, "failing", Unlabelled())], queue=queue, a=DIRTY)
    assert [a.kind for a in plan.actions] == ["warn", "conflict-probe"]  # red AND conflicting
    (train,) = plan.trains
    assert train.stepped == ("a",)


def test_a_conflicting_member_that_is_not_the_candidate_is_probed() -> None:
    plan = walk(
        [
            ("a", False, "green", Approved("h-a")),
            ("b", False, "green", Unlabelled()),  # awaiting approval
            ("c", False, "green", Approved("h-c")),  # queued behind the head
        ],
        b=DIRTY,
        c=DIRTY,
    )
    assert [a.batch for a in plan.actions if a.kind == "merge"] == ["a", "c"]
    assert probes(plan) == ["b"]  # c is a candidate too: the merge path owns it


def test_the_merge_candidate_and_clean_prs_are_never_probed() -> None:
    plan = walk(
        [("a", False, "green", Approved("h-a")), ("b", True, "green", Unlabelled())],
        a=DIRTY,
        b={"mergeable": "MERGEABLE", "merge_state": "CLEAN"},
    )
    assert probes(plan) == []
    unknown = walk([("a", True, "green", Unlabelled())], a={"mergeable": "UNKNOWN"})
    assert probes(unknown) == [] and unknown.trains == ()


def test_a_conflicting_member_stepped_over_red_is_probed() -> None:
    plan = walk([("a", False, "failing", Approved("h-a"))], a=DIRTY)
    assert [a.kind for a in plan.actions] == ["warn", "conflict-probe"]
