"""The approval gate in the drive walk and the merge paths (spec
2026-10-11-merge-train-safety §A "Recording and voiding", "The walk", "Merging",
§B "How an update is recorded"; R1, R2, R3, R8).

Pure where the code is: `settle_approvals` and `merge_ready`/`merge_one` run over
in-memory fakes, `_walk_train` over a built `Snapshot`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.ghclient import UnsupportedForgeOperation
from fr.labels import APPROVED_FR
from fr.triage.approval import Approved, First, Unlabelled, Void, settle_approvals
from fr.triage.batch import MergeStep, QueueEntry
from fr.triage.batch_drive import LivePr, Snapshot, Train, drive_pass, train_line
from fr.triage.batch_merge import (
    MergeAttempt,
    MergeContext,
    MergeStopError,
    Slot,
    merge_one,
    merge_ready,
)
from fr.triage.model import ApprovalEvent, Batch, BatchEvent, PullRequest, UpdateEvent

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


# ------------------------------------------------------------------ the walk


def _pr(n: int, bid: str, head: str) -> PullRequest:
    return PullRequest(
        repo=REPO, number=n, title=bid, state="OPEN", is_draft=False, url="u",
        head_ref=f"feat/batch-{bid}", head_oid=head, author="operator", cross_repo=False,
    )  # fmt: skip


def _walk(
    members: list[tuple[str, bool, str]], approvals: dict[str, Any]
) -> tuple[Train, list[Any]]:
    """*members*: (batch id, draft, checks)."""
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
    )
    plan = drive_pass(snap)
    (train,) = plan.trains
    return train, [a for a in plan.actions if a.kind == "merge"]


def test_an_unapproved_green_member_awaits_and_never_stops_the_walk() -> None:
    train, merges = _walk(
        [("a", False, "green"), ("b", False, "green")],
        {"a": Unlabelled(), "b": Approved("h-b")},
    )
    assert train.awaiting == ("a",)
    assert train.head == "b" and train.candidates == ("b",)
    assert [m.batch for m in merges] == ["b"]
    assert "awaiting approval a (#100)" in train_line(train)


def test_a_missing_verdict_is_never_an_approval() -> None:
    train, merges = _walk([("a", False, "green")], {})
    assert (train.awaiting, merges) == (("a",), [])


def test_an_approved_or_first_draft_is_a_member_and_merges_when_green() -> None:
    train, merges = _walk(
        [("a", True, "green"), ("b", True, "green")], {"a": First("h-a"), "b": Approved("h-b")}
    )
    assert train.candidates == ("a", "b")
    assert [m.batch for m in merges] == ["a", "b"]


def test_an_unapproved_draft_is_not_a_member() -> None:
    train, merges = _walk(
        [("a", True, "green"), ("b", False, "green")], {"a": Void("x"), "b": Approved("h-b")}
    )
    assert train.awaiting == () and "a" not in train.numbers
    assert [m.batch for m in merges] == ["b"]


def test_a_pending_unapproved_member_does_not_wait_the_train() -> None:
    train, merges = _walk(
        [("a", False, "pending"), ("b", False, "green")],
        {"a": Unlabelled(), "b": Approved("h-b")},
    )
    assert train.head == "b" and train.awaiting == ("a",)
    assert [m.batch for m in merges] == ["b"]


# ------------------------------------------------------------------ merging (R1, R3)


class GateForge:
    def __init__(self, pr: dict[str, Any]) -> None:
        self.pr = {"state": "OPEN", "head_ref": "feat/batch-a", **pr}
        self.merged: list[tuple[int, str]] = []
        self.readied: list[int] = []
        self.ready_unsupported = False

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        return dict(self.pr)

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [{"name": "ci-ok", "bucket": "pass"}]

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return self.pr_required_checks(repo, number)

    def pr_ready(self, repo: str, number: int) -> None:
        if self.ready_unsupported:
            raise UnsupportedForgeOperation("pr_ready", "gitlab")
        self.readied.append(number)
        self.pr["draft"] = False

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        self.merged.append((number, head_sha))
        self.pr["state"] = "MERGED"


class UpToDate:
    """A clone where every head is current: `_land` merges, never updates."""

    path = Path("/nonexistent")

    def fetch(self) -> None: ...
    def default_branch(self) -> str:
        return "main"

    def show(self, ref: str, file: str) -> str | None:
        return None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return True

    def commits_behind(self, head: str, ref: str) -> tuple[Any, ...]:
        return ()

    def changed_paths(self, ref: str, head: str) -> frozenset[str]:
        return frozenset()

    def add_worktree(self, where: Path, ref: str) -> Any:
        raise AssertionError("no update expected")

    def remove_worktree(self, where: Path) -> None: ...

    def rev_parse(self, ref: str) -> str:
        return "m1"


def _slot(batch: Batch, head: str = "h1") -> Slot:
    pr = _pr(7, batch.id, head)
    return Slot(step=MergeStep(batch=batch, pr=pr, reserved_version=None, shared=[]), head=head,
                slot=None)  # fmt: skip


def _ctx(forge: GateForge, tmp_path: Path, checkout: Any = None) -> MergeContext:
    return MergeContext(
        client=forge,  # type: ignore[arg-type]
        checkout=checkout or UpToDate(),
        repo=REPO,
        version=None,
        scratch_root=tmp_path,
        method="squash",
        say=lambda line: None,
    )


@pytest.mark.parametrize(
    ("labels", "events"),
    [([], [_approval(7, "h1")]), ([LABEL], []), ([LABEL], [_approval(7, "h0")])],
    ids=["unlabelled", "never-recorded", "void"],
)
def test_merge_ready_and_merge_one_refuse_without_a_valid_approval(
    tmp_path: Path, labels: list[str], events: list[ApprovalEvent]
) -> None:
    forge = GateForge({"draft": False, "head_oid": "h1", "labels": labels})
    slot = _slot(_batch("a", *events))
    assert merge_ready(_ctx(forge, tmp_path), slot, None).outcome == "unapproved"
    held = merge_one(_ctx(forge, tmp_path), slot, None)
    assert held is not None and (held.outcome, held.head) == ("unapproved", "h1")
    assert forge.merged == []


def test_an_approved_green_draft_is_readied_then_merged(tmp_path: Path) -> None:
    forge = GateForge({"draft": True, "head_oid": "h1", "labels": [LABEL]})
    slot = _slot(_batch("a", _approval(7, "h1")))
    attempt = merge_ready(_ctx(forge, tmp_path), slot, None)
    assert attempt.outcome == "merged"
    assert forge.readied == [7] and forge.merged == [(7, "h1")]


def test_merge_one_readies_an_approved_draft_too(tmp_path: Path) -> None:
    forge = GateForge({"draft": True, "head_oid": "h1", "labels": [LABEL]})
    slot = _slot(_batch("a", _approval(7, "h1")))
    assert merge_one(_ctx(forge, tmp_path), slot, None) is None
    assert forge.readied == [7] and forge.merged == [(7, "h1")]


def test_a_forge_that_cannot_ready_leaves_the_draft_unready(tmp_path: Path) -> None:
    forge = GateForge({"draft": True, "head_oid": "h1", "labels": [LABEL]})
    forge.ready_unsupported = True
    slot = _slot(_batch("a", _approval(7, "h1")))
    attempt = merge_ready(_ctx(forge, tmp_path), slot, None)
    assert attempt.outcome == "unready"
    assert "pr_ready" in attempt.reason
    assert forge.merged == []


def test_run_queue_stops_on_an_unapproved_pr(tmp_path: Path) -> None:
    from fr.triage.batch_merge import run_queue

    forge = GateForge({"draft": False, "head_oid": "h1", "labels": []})
    with pytest.raises(MergeStopError, match="approved-fr"):
        run_queue(_ctx(forge, tmp_path), [_slot(_batch("a"))])


def test_an_approval_recorded_this_run_counts(tmp_path: Path) -> None:
    """`batch merge --yes` settles first; the context carries what it recorded."""
    forge = GateForge({"draft": False, "head_oid": "h1", "labels": [LABEL]})
    ctx = _ctx(forge, tmp_path)
    ctx.recorded.setdefault("a", []).append(_approval(7, "h1"))
    assert merge_ready(ctx, _slot(_batch("a")), None).outcome == "merged"


# ------------------------------------------------------------------ updates (R8)


class Behind(UpToDate):
    def __init__(self, forge: GateForge) -> None:
        self.forge = forge
        self.pushed: list[str] = []

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return descendant != "h1"

    def commits_behind(self, head: str, ref: str) -> tuple[Any, ...]:
        return (("c1", (("M", "x.py"),)),)

    def changed_paths(self, ref: str, head: str) -> frozenset[str]:
        return frozenset({"x.py"})

    def add_worktree(self, where: Path, ref: str) -> Any:
        clone = self

        class _Wt:
            path = where

            def merge(self, ref: str) -> list[str]:
                return []

            def commit_all(self, message: str, version_files: list[str]) -> str | None:
                return "h2"

            def push(self, branch: str) -> None:
                clone.pushed.append(branch)
                clone.forge.pr["head_oid"] = "h2"

        return _Wt()

    def rev_parse(self, ref: str) -> str:
        assert ref == "origin/main"
        return "m7"


def test_an_update_is_recorded_with_the_fetched_base_and_keeps_the_approval(
    tmp_path: Path,
) -> None:
    forge = GateForge({"draft": False, "head_oid": "h1", "labels": [LABEL]})
    calls: list[tuple[int, str, str, str]] = []
    ctx = _ctx(forge, tmp_path, Behind(forge))
    ctx.on_update = lambda *a: calls.append(a)
    slot = _slot(_batch("a", _approval(7, "h1")))
    attempt = merge_ready(ctx, slot, None)
    assert attempt == MergeAttempt("updated", head="h2")
    assert calls == [(7, "h1", "h2", "m7")]
    (event,) = ctx.recorded["a"]
    assert isinstance(event, UpdateEvent) and (event.head_before, event.base) == ("h1", "m7")
    # the next attempt sees the new head as approved through fr's own update
    forge.pr["head_oid"] = "h2"
    again = merge_ready(ctx, _slot(_batch("a", _approval(7, "h1")), "h2"), None)
    assert again.outcome == "merged"
