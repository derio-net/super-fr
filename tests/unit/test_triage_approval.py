"""Approval pinned to content (spec 2026-11-19-wave-merge-queue R12, §E): the verdict reads
the PR's patch-id, never git itself."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fr.labels import APPROVED_FR
from fr.triage.approval import Approved, First, Unlabelled, Void, approval_verdict, settle_approvals
from fr.triage.model import ApprovalEvent, Batch, BatchEvent, UpdateEvent

REPO = "derio-net/super-fr"
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
LABEL = APPROVED_FR.name


def _approval(head: str, patch_id: str | None = None, *, pr: int = 7) -> ApprovalEvent:
    return ApprovalEvent(
        kind="approval", at=datetime(2026, 11, 19, 11, tzinfo=UTC), pr=pr, head=head,
        patch_id=patch_id,
    )  # fmt: skip


def _batch(*events: BatchEvent) -> Batch:
    return Batch.model_validate(
        {
            "id": "a",
            "title": "a",
            "ids": ["super-fr#1"],
            "events": [
                {"kind": "dispatch", "at": "2026-11-19T10:00:00Z", "runner": "herdr",
                 "handle": "h", "branch": "feat/batch-a"},
                *[e.model_dump() for e in events],
            ],
        }
    )  # fmt: skip


class _Forge:
    def __init__(self, view: dict[str, Any]) -> None:
        self.view = view
        self.label_edits: list[tuple[int, frozenset[str], frozenset[str]]] = []

    def read_file(self, repo: str, path: str) -> str:
        from fr.gh import GhError

        raise GhError("gh: Not Found (HTTP 404)", stderr="gh: Not Found (HTTP 404)")

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        return dict(self.view)

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.label_edits.append((number, add, remove))


def _settle(
    forge: _Forge, batch: Batch, patch_ids: dict[str, str]
) -> tuple[dict[str, Any], list[tuple[str, BatchEvent]], list[tuple[int, str]]]:
    written: list[tuple[str, BatchEvent]] = []
    asked: list[tuple[int, str]] = []

    def patch_id_of(pr: int, head: str) -> str | None:
        asked.append((pr, head))
        return patch_ids.get(head)

    got = settle_approvals(
        forge, lambda bid, ev: written.append((bid, ev)), REPO, [(batch, 7)], lambda _: None,
        now=NOW, patch_id_of=patch_id_of,
    )  # fmt: skip
    return got, written, asked


# ------------------------------------------------------------------ the verdict


def test_the_same_patch_id_at_another_head_is_approved() -> None:
    verdict = approval_verdict([_approval("h1", "p1")], 7, "h2", [LABEL], patch_id="p1")

    assert verdict == Approved("h1")


def test_the_approved_head_itself_stays_approved_whatever_its_patch_id() -> None:
    """The content at the approved head is what was approved; a patch-id that moved with
    the merge base alone does not void it."""
    verdict = approval_verdict([_approval("h1", "p1")], 7, "h1", [LABEL], patch_id="p2")

    assert verdict == Approved("h1")


def test_an_fr_update_keeps_the_approval_though_the_patch_id_moved() -> None:
    """The legacy train's own update of the PR branch (an `update` event) is fr's push."""
    update = UpdateEvent(
        kind="update", at=datetime(2026, 11, 19, 11, 30, tzinfo=UTC), pr=7, head_before="h1",
        head_after="h2", base="b1",
    )  # fmt: skip
    verdict = approval_verdict([_approval("h1", "p1"), update], 7, "h2", [LABEL], patch_id="p2")

    assert verdict == Approved("h1")


def test_another_patch_id_at_another_head_is_void() -> None:
    verdict = approval_verdict([_approval("h1", "p1")], 7, "h2", [LABEL], patch_id="p2")

    assert verdict == Void("h1")


def test_an_approval_with_no_patch_id_falls_back_to_reaches() -> None:
    events = [_approval("h1")]

    assert approval_verdict(events, 7, "h1", [LABEL], patch_id="p9") == Approved("h1")
    assert approval_verdict(events, 7, "h2", [LABEL], patch_id="p9") == Void("h1")


def test_an_unknown_live_patch_id_falls_back_to_reaches() -> None:
    events = [_approval("h1", "p1")]

    assert approval_verdict(events, 7, "h1", [LABEL]) == Approved("h1")
    assert approval_verdict(events, 7, "h2", [LABEL]) == Void("h1")


def test_no_label_is_unlabelled_whatever_the_patch_id() -> None:
    assert approval_verdict([_approval("h1", "p1")], 7, "h2", [], patch_id="p1") == Unlabelled()


def test_a_first_label_is_first_whatever_the_patch_id() -> None:
    assert approval_verdict([], 7, "h1", [LABEL], patch_id="p1") == First("h1")


# ------------------------------------------------------------------ settling


def test_settle_records_the_patch_id_it_is_given_for_a_first_verdict() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h1", "labels": [LABEL]})

    got, written, asked = _settle(forge, _batch(), {"h1": "p1"})

    ((bid, event),) = written
    assert bid == "a" and isinstance(event, ApprovalEvent)
    assert (event.head, event.patch_id, event.voided_at) == ("h1", "p1", None)
    assert got == {"a": Approved("h1")}
    assert asked == [(7, "h1")]


def test_settle_keeps_an_approval_whose_patch_id_holds_at_a_new_head() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    got, written, _ = _settle(forge, _batch(_approval("h1", "p1")), {"h2": "p1"})

    assert written == []
    assert forge.label_edits == []
    assert got == {"a": Approved("h1")}


def test_settle_voids_on_a_patch_id_change_removing_the_label() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    got, written, _ = _settle(forge, _batch(_approval("h1", "p1")), {"h2": "p2"})

    assert forge.label_edits == [(7, frozenset(), frozenset({LABEL}))]
    ((_, event),) = written
    assert isinstance(event, ApprovalEvent)
    assert (event.head, event.patch_id, event.voided_at) == ("h1", "p1", "h2")
    assert got == {"a": Unlabelled()}


def test_settle_with_no_patch_id_reader_records_none() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h1", "labels": [LABEL]})
    written: list[tuple[str, BatchEvent]] = []

    settle_approvals(
        forge, lambda bid, ev: written.append((bid, ev)), REPO, [(_batch(), 7)], lambda _: None,
        now=NOW,
    )  # fmt: skip

    ((_, event),) = written
    assert isinstance(event, ApprovalEvent) and event.patch_id is None
