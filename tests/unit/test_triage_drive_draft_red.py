"""batch-train-truth R15-R17, on the wave merge queue: an unapproved draft batch PR with
failing checks is reported red, never awaits approval and is never ready for the queue; a
batch PR the forge reads as conflicting, draft or ready, approved or not, is probed early
unless the queue holds it as an entry. An unapproved green draft stays invisible."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fr.triage.approval import Approved, Unlabelled
from fr.triage.batch import QueueEntry
from fr.triage.batch_drive import LivePr, Pass, Snapshot, _conflict_probes, drive_pass
from fr.triage.model import Batch, CursorPosition, PullRequest

DELIVERED = CursorPosition(run="r", step="deliver", kind="deliver-done")

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


def _snap(rows: list[tuple[str, bool, str, Any]], **live_extra: Any) -> Snapshot:
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
    return Snapshot(
        batches=tuple(batches),
        stages={b.id: "pr-open" for b in batches},
        queue=entries,
        live=live,
        repos={b.id: REPO for b in batches},
        now=NOW,
        approvals={r[0]: r[3] for r in rows},
        cursors={bid: (p.head, DELIVERED, "read") for bid, p in live.items()},
    )


def walk(rows: list[tuple[str, bool, str, Any]], **live_extra: Any) -> Pass:
    return drive_pass(_snap(rows, **live_extra))


def reds(plan: Pass) -> list[str]:
    return [a.batch for a in plan.actions if a.kind == "warn" and a.red]


def test_a_red_unapproved_draft_alone_is_reported_and_stepped_over() -> None:
    """Reported red for the red recovery, and stepped over: never awaiting approval, never
    ready for the queue (the name the acceptance row `drive-red-drafts` cites)."""
    plan = walk([("a", True, "failing", Unlabelled())])
    (warn,) = [a for a in plan.actions if a.kind == "warn"]
    assert warn.red and warn.batch == "a" and warn.pr == 100 and warn.head == "h-a"
    assert warn.checks == ("ci",)
    assert "a" not in plan.awaiting and "a" not in plan.ready


def test_a_red_draft_beside_a_ready_member_never_becomes_ready() -> None:
    plan = walk([("a", True, "failing", Unlabelled()), ("b", False, "green", Approved("h-b"))])
    assert reds(plan) == ["a"]
    assert plan.ready == frozenset({"b"}) and "a" not in plan.awaiting


def test_a_green_or_pending_unapproved_draft_yields_nothing_new() -> None:
    for checks in ("green", "pending"):
        plan = walk([("a", True, checks, Unlabelled())])
        assert reds(plan) == [] and plan.awaiting == frozenset() and plan.ready == frozenset()
        assert [a for a in plan.actions if a.kind == "conflict-probe"] == []


# ------------------------------------------------------------ R17: the conflict probe

DIRTY: dict[str, Any] = {"mergeable": "CONFLICTING", "merge_state": "DIRTY"}


def probes(plan: Pass) -> list[str]:
    return [a.batch for a in plan.actions if a.kind == "conflict-probe"]


def test_a_conflicting_unapproved_draft_is_probed_whatever_its_checks() -> None:
    for checks in ("green", "pending", "failing"):
        plan = walk([("a", True, checks, Unlabelled())], a=DIRTY)
        assert probes(plan) == ["a"], checks
        (probe,) = [a for a in plan.actions if a.kind == "conflict-probe"]
        assert (probe.pr, probe.head) == (100, "h-a")
    plan = walk([("a", True, "failing", Unlabelled())], a=DIRTY)
    assert reds(plan) == ["a"] and probes(plan) == ["a"]  # red AND conflicting


def test_a_conflicting_ready_pr_approved_or_not_is_probed() -> None:
    plan = walk(
        [("a", False, "green", Approved("h-a")), ("b", False, "green", Unlabelled())],
        a=DIRTY,
        b=DIRTY,
    )
    assert probes(plan) == ["a", "b"]


def test_clean_and_unknown_prs_are_never_probed() -> None:
    plan = walk(
        [("a", False, "green", Approved("h-a")), ("b", True, "green", Unlabelled())],
        b={"mergeable": "MERGEABLE", "merge_state": "CLEAN"},
    )
    assert probes(plan) == []
    unknown = walk([("a", True, "green", Unlabelled())], a={"mergeable": "UNKNOWN"})
    assert probes(unknown) == []


def test_a_conflicting_pr_stepped_over_red_is_probed() -> None:
    plan = walk([("a", False, "failing", Approved("h-a"))], a=DIRTY)
    assert reds(plan) == ["a"] and probes(plan) == ["a"]


def test_an_entry_the_queue_holds_is_left_to_the_queue() -> None:
    snap = _snap(
        [("a", False, "green", Approved("h-a")), ("b", False, "green", Approved("h-b"))],
        a=DIRTY,
        b=DIRTY,
    )
    out = _conflict_probes(snap.queue, snap, frozenset({"a"}))
    assert [a.batch for a in out] == ["b"]
