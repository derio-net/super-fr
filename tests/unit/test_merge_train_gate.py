"""The approval gate in the drive pass (spec 2026-10-11-merge-train-safety §A "Recording
and voiding", "The walk"; R1, R2; wave-merge-queue R3, R22).

Pure where the code is: `settle_approvals` runs over in-memory fakes, the pass's reports
and the queue's entries over a built `Snapshot`. The retired train's merge and update
paths (`merge_ready`, `merge_one`) are gone: an approval reaches a merge only as a queue
entry, and `reaches` only reads the `update` events an older `judgements.yaml` carries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fr.labels import APPROVED_FR
from fr.triage.approval import Approved, First, Unlabelled, Void, settle_approvals
from fr.triage.batch import QueueEntry
from fr.triage.batch_drive import LivePr, Pass, Snapshot, drive_pass
from fr.triage.model import ApprovalEvent, Batch, BatchEvent, PullRequest, UpdateEvent
from fr.triage.wave_queue import QueueConfig

REPO = "derio-net/super-fr"
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
LABEL = APPROVED_FR.name


def _batch(bid: str = "a", *events: BatchEvent) -> Batch:
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


def _approval(pr: int, head: str, voided_at: str | None = None) -> ApprovalEvent:
    return ApprovalEvent(
        kind="approval", at=datetime(2026, 10, 11, 11, tzinfo=UTC), pr=pr, head=head,
        voided_at=voided_at,
    )  # fmt: skip


# ------------------------------------------------------------------ settle (R2)


class LabelForge:
    def __init__(self, prs: dict[int, dict[str, Any]]) -> None:
        self.prs = prs
        self.label_edits: list[tuple[int, frozenset[str], frozenset[str]]] = []
        self.files: dict[str, str] = {}  # the default branch's files (contents API, R9)

    def read_file(self, repo: str, path: str) -> str:
        from fr.gh import GhError

        if path not in self.files:
            raise GhError("gh: Not Found (HTTP 404)", stderr="gh: Not Found (HTTP 404)")
        return self.files[path]

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        return dict(self.prs[number])

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.label_edits.append((number, add, remove))
        self.prs[number]["labels"] = [x for x in self.prs[number]["labels"] if x not in remove]


def _settle(
    forge: LabelForge, batches: list[tuple[Batch, int]], *, dry_run: bool = False
) -> tuple[dict[str, Any], list[tuple[str, BatchEvent]], list[str]]:
    written: list[tuple[str, BatchEvent]] = []
    said: list[str] = []
    got = settle_approvals(
        forge, lambda bid, ev: written.append((bid, ev)), REPO, batches, said.append,
        now=NOW, dry_run=dry_run,
    )  # fmt: skip
    return got, written, said


def test_settle_records_first_at_the_current_head_whatever_the_checks() -> None:
    forge = LabelForge({7: {"state": "OPEN", "head_oid": "h1", "labels": [LABEL]}})
    got, written, said = _settle(forge, [(_batch(), 7)])
    ((bid, event),) = written
    assert bid == "a" and isinstance(event, ApprovalEvent)
    assert (event.pr, event.head, event.voided_at, event.at) == (7, "h1", None, NOW)
    assert got == {"a": Approved("h1")}
    assert said == ["approval of PR #7 recorded at h1"]
    assert forge.label_edits == []


def test_settle_voids_a_head_the_chain_does_not_reach_and_removes_the_label() -> None:
    forge = LabelForge({7: {"state": "OPEN", "head_oid": "h9", "labels": [LABEL, "x"]}})
    got, written, said = _settle(forge, [(_batch("a", _approval(7, "h1")), 7)])
    assert forge.label_edits == [(7, frozenset(), frozenset({LABEL}))]
    ((_, event),) = written
    assert isinstance(event, ApprovalEvent)
    assert (event.head, event.voided_at) == ("h1", "h9")
    assert got == {"a": Unlabelled()}
    assert said == ["approval of PR #7 at h1 voided: head moved to h9"]


def test_p3_r2_labels_off_leaves_the_label_and_records_no_void() -> None:
    """R9: under `forge.labels: off` fr removes no `approved-fr` label, so it records no
    void either (the void and the removal stand together) and approves nothing."""
    forge = LabelForge({7: {"state": "OPEN", "head_oid": "h9", "labels": [LABEL, "x"]}})
    forge.files[".fr/settings.yaml"] = "forge:\n  labels: 'off'\n"
    got, written, said = _settle(forge, [(_batch("a", _approval(7, "h1")), 7)])
    assert forge.label_edits == [] and written == []
    assert said[0].startswith("approval of PR #7 at h1 not voided: forge.labels: off")
    assert got["a"] != Approved("h1")


def test_settle_is_a_no_op_on_an_approved_or_unlabelled_pr() -> None:
    forge = LabelForge(
        {
            7: {"state": "OPEN", "head_oid": "h2", "labels": [LABEL]},
            8: {"state": "OPEN", "head_oid": "h3", "labels": []},
        }
    )
    update = UpdateEvent(
        kind="update", at=datetime(2026, 10, 11, 11, 30, tzinfo=UTC), pr=7,
        head_before="h1", head_after="h2", base="m1",
    )  # fmt: skip
    got, written, said = _settle(
        forge, [(_batch("a", _approval(7, "h1"), update), 7), (_batch("b"), 8)]
    )
    assert got == {"a": Approved("h1"), "b": Unlabelled()}
    assert (written, said, forge.label_edits) == ([], [], [])


def test_settle_skips_a_pr_that_is_no_longer_open() -> None:
    forge = LabelForge({7: {"state": "MERGED", "head_oid": "h1", "labels": [LABEL]}})
    got, written, _ = _settle(forge, [(_batch(), 7)])
    assert (got, written) == ({}, [])


def test_a_preview_says_what_it_would_record_or_void_and_writes_nothing() -> None:
    forge = LabelForge(
        {
            7: {"state": "OPEN", "head_oid": "h1", "labels": [LABEL]},
            8: {"state": "OPEN", "head_oid": "h9", "labels": [LABEL]},
        }
    )
    got, written, said = _settle(
        forge, [(_batch("a"), 7), (_batch("b", _approval(8, "h1")), 8)], dry_run=True
    )
    assert (written, forge.label_edits) == ([], [])
    assert got == {"a": First("h1"), "b": Void("h1")}
    assert said == [
        "would record approval of PR #7 at h1",
        "would void approval of PR #8 at h1: head moved to h9",
    ]


# ------------------------------------------------------------------ the pass's members


def _pr(n: int, bid: str, head: str) -> PullRequest:
    return PullRequest(
        repo=REPO, number=n, title=bid, state="OPEN", is_draft=False, url="u",
        head_ref=f"feat/batch-{bid}", head_oid=head, author="operator", cross_repo=False,
    )  # fmt: skip


def _walk(
    members: list[tuple[str, bool, str]], approvals: dict[str, Any]
) -> tuple[Pass, list[str]]:
    """*members*: (batch id, draft, checks). The pass, and the batches the queue opens for
    or holds as ready entries."""
    batches = [_batch(bid) for bid, _, _ in members]
    queue = tuple(
        QueueEntry(batch=b, pr=_pr(100 + i, b.id, f"h-{b.id}")) for i, b in enumerate(batches)
    )
    live = {
        b.id: LivePr(number=100 + i, state="OPEN", draft=draft, head=f"h-{b.id}", checks=checks)  # type: ignore[arg-type]
        for i, (b, (_, draft, checks)) in enumerate(zip(batches, members, strict=True))
    }
    snap = Snapshot(
        batches=tuple(batches),
        stages={b.id: "pr-open" for b in batches},
        queue=queue,
        live=live,
        repos={b.id: REPO for b in batches},
        now=NOW,
        approvals=approvals,
        wave_queues={REPO: QueueConfig()},
    )
    plan = drive_pass(snap)
    (queue_plan,) = plan.queues
    ready = [k for a in queue_plan.actions for k in a.entries] + list(queue_plan.waiting)
    return plan, ready


def test_an_unapproved_green_member_awaits_and_never_stops_the_queue() -> None:
    plan, ready = _walk(
        [("a", False, "green"), ("b", False, "green")],
        {"a": Unlabelled(), "b": Approved("h-b")},
    )
    assert plan.awaiting == frozenset({"a"})
    assert ready == ["b"]


def test_a_missing_verdict_is_never_an_approval() -> None:
    plan, ready = _walk([("a", False, "green")], {})
    assert (plan.awaiting, ready) == (frozenset({"a"}), [])


def test_an_approved_or_first_draft_is_a_member_and_is_ready_when_green() -> None:
    plan, ready = _walk(
        [("a", True, "green"), ("b", True, "green")], {"a": First("h-a"), "b": Approved("h-b")}
    )
    assert plan.awaiting == frozenset()
    assert sorted(ready) == ["a", "b"]  # one opens a between-waves queue, the other waits


def test_an_unapproved_draft_is_not_a_member() -> None:
    plan, ready = _walk(
        [("a", True, "green"), ("b", False, "green")], {"a": Void("x"), "b": Approved("h-b")}
    )
    assert plan.awaiting == frozenset() and ready == ["b"]


def test_a_pending_unapproved_member_does_not_hold_the_queue() -> None:
    plan, ready = _walk(
        [("a", False, "pending"), ("b", False, "green")],
        {"a": Unlabelled(), "b": Approved("h-b")},
    )
    assert plan.awaiting == frozenset({"a"}) and ready == ["b"]


def test_a_failing_member_is_reported_red_and_is_no_entry() -> None:
    plan, ready = _walk(
        [("a", False, "failing"), ("b", False, "green")],
        {"a": Approved("h-a"), "b": Approved("h-b")},
    )
    (red,) = [a for a in plan.actions if a.kind == "warn" and a.red]
    assert red.batch == "a" and ready == ["b"]


def test_reaches_follows_only_frs_own_updates() -> None:
    from fr.triage.approval import reaches

    update = UpdateEvent(
        kind="update", at=datetime(2026, 10, 11, 11, 30, tzinfo=UTC), pr=7,
        head_before="h1", head_after="h2", base="m1",
    )  # fmt: skip
    assert reaches([update], 7, "h1", "h2") and reaches([], 7, "h1", "h1")
    assert not reaches([update], 7, "h1", "h9") and not reaches([update], 8, "h1", "h2")
