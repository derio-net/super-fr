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
    forge: _Forge,
    batch: Batch,
    patch_ids: dict[str, str],
    *,
    fresh_ids: dict[str, str] | None = None,
    said: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], list[tuple[str, BatchEvent]], list[tuple[int, str]]]:
    """Settle *batch*'s PR #7 with a reader that answers *patch_ids*, or *fresh_ids* once
    asked to re-read against a refetched default branch (asked: `(pr, "fresh:" + head)`)."""
    written: list[tuple[str, BatchEvent]] = []
    asked: list[tuple[int, str]] = []

    def patch_id_of(pr: int, head: str, *, fresh: bool = False) -> str | None:
        asked.append((pr, f"fresh:{head}" if fresh else head))
        ids = fresh_ids if fresh and fresh_ids is not None else patch_ids
        return ids.get(head)

    got = settle_approvals(
        forge, lambda bid, ev: written.append((bid, ev)), REPO, [(batch, 7)],
        (said.append if said is not None else lambda _: None),
        now=NOW, patch_id_of=patch_id_of, dry_run=dry_run,
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


# ------------------------------------------------------------------ a stale default branch (p1-r3)


def test_a_mismatch_is_read_again_against_a_refetched_default_before_voiding() -> None:
    """The first read ran against `origin/<default>` as last fetched; the PR merged a newer
    `main`, so its merge base is newer than the clone knows. The re-read after a fetch
    sees the same diff, and the approval holds."""
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    got, written, asked = _settle(
        forge, _batch(_approval("h1", "p1")), {"h2": "p-stale"}, fresh_ids={"h2": "p1"}
    )

    assert got == {"a": Approved("h1")}
    assert written == [] and forge.label_edits == []
    assert asked == [(7, "h2"), (7, "fresh:h2")]


def test_a_mismatch_that_survives_the_refetch_voids() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    got, _, asked = _settle(
        forge, _batch(_approval("h1", "p1")), {"h2": "p2"}, fresh_ids={"h2": "p2"}
    )

    assert got == {"a": Unlabelled()}
    assert forge.label_edits == [(7, frozenset(), frozenset({LABEL}))]
    assert asked == [(7, "h2"), (7, "fresh:h2")]


def test_a_matching_read_is_never_read_again() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    _, _, asked = _settle(forge, _batch(_approval("h1", "p1")), {"h2": "p1"})

    assert asked == [(7, "h2")]


# ------------------------------------------------------------------ fr's own updates (p1-r7)


def _update(before: str, after: str, patch_id: str | None, *, minute: int = 30) -> UpdateEvent:
    return UpdateEvent(
        kind="update", at=datetime(2026, 11, 19, 11, minute, tzinfo=UTC), pr=7,
        head_before=before, head_after=after, base="b1", patch_id=patch_id,
    )  # fmt: skip


def test_a_clean_merge_of_main_after_an_fr_update_keeps_the_approval() -> None:
    """fr's update moved the patch-id (its version slot, say) and recorded the new one; a
    later merge of `main` with no conflict resolution keeps that id, so it keeps the
    approval though `reaches` no longer leads to the head."""
    events = [_approval("h1", "p1"), _update("h1", "h2", "p2")]

    assert approval_verdict(events, 7, "h3", [LABEL], patch_id="p2") == Approved("h1")


def test_an_update_recorded_before_the_approval_does_not_count() -> None:
    events = [
        _approval("h0", "p0"),
        _update("h0", "h1", "p9", minute=5),
        ApprovalEvent(
            kind="approval", at=datetime(2026, 11, 19, 11, 10, tzinfo=UTC), pr=7, head="h0",
            voided_at="h1", patch_id="p0",
        ),
        ApprovalEvent(
            kind="approval", at=datetime(2026, 11, 19, 11, 20, tzinfo=UTC), pr=7, head="h1",
            patch_id="p1",
        ),
    ]  # fmt: skip

    assert approval_verdict(events, 7, "h3", [LABEL], patch_id="p9") == Void("h1")


def test_another_prs_update_does_not_count() -> None:
    other = UpdateEvent(
        kind="update", at=datetime(2026, 11, 19, 11, 30, tzinfo=UTC), pr=8, head_before="x",
        head_after="y", base="b1", patch_id="p2",
    )  # fmt: skip

    assert approval_verdict([_approval("h1", "p1"), other], 7, "h3", [LABEL], patch_id="p2") == (
        Void("h1")
    )


def test_a_change_after_an_fr_update_voids_saying_the_diff_changed() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h3", "labels": [LABEL]})
    said: list[str] = []

    _settle(forge, _batch(_approval("h1", "p1"), _update("h1", "h2", "p2")), {"h3": "p3"},
            said=said)  # fmt: skip

    assert said == ["approval of PR #7 at h1 voided: its diff changed at h3"]


# ------------------------------------------------------------------ an approval with no id (p1-r8)


def test_an_approval_with_no_patch_id_gains_one_while_it_still_holds() -> None:
    """Recorded with no id (unreadable then, or before schema 13): once its head is still
    the live one and the id is readable, settle records it, so R12 applies from then on."""
    forge = _Forge({"state": "OPEN", "head_oid": "h1", "labels": [LABEL]})
    said: list[str] = []

    got, written, _ = _settle(forge, _batch(_approval("h1")), {"h1": "p1"}, said=said)

    ((_, event),) = written
    assert isinstance(event, ApprovalEvent)
    assert (event.pr, event.head, event.patch_id, event.voided_at) == (7, "h1", "p1", None)
    assert got == {"a": Approved("h1")}
    assert forge.label_edits == []
    assert said == ["approval of PR #7 at h1 pinned to its patch-id"]


def test_the_refreshed_approval_then_survives_a_clean_merge_of_main() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h1", "labels": [LABEL]})
    _, written, _ = _settle(forge, _batch(_approval("h1")), {"h1": "p1"})
    ((_, refreshed),) = written
    assert isinstance(refreshed, ApprovalEvent)
    events = [_approval("h1"), refreshed]

    assert approval_verdict(events, 7, "h9", [LABEL], patch_id="p1") == Approved("h1")


def test_an_approval_held_by_reaches_gains_the_id_at_the_live_head() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    _, written, _ = _settle(forge, _batch(_approval("h1"), _update("h1", "h2", None)),
                            {"h2": "p2"})  # fmt: skip

    ((_, event),) = written
    assert isinstance(event, ApprovalEvent) and (event.head, event.patch_id) == ("h2", "p2")


def test_an_unreadable_id_records_nothing_and_a_dry_run_only_says_so() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h1", "labels": [LABEL]})
    _, written, _ = _settle(forge, _batch(_approval("h1")), {})
    assert written == []

    said: list[str] = []
    _, written, _ = _settle(forge, _batch(_approval("h1")), {"h1": "p1"}, said=said,
                            dry_run=True)  # fmt: skip
    assert written == []
    assert said == ["would pin approval of PR #7 at h1 to its patch-id"]


def test_an_approval_that_has_an_id_is_never_refreshed() -> None:
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})

    _, written, _ = _settle(forge, _batch(_approval("h1", "p1")), {"h2": "p1"})

    assert written == []


# ------------------------------------------------------------------ a landed PR (R12, R35; p3-r4)


def test_a_pr_the_queue_landed_is_never_settled_though_the_forge_reads_it_open() -> None:
    """R12: a landed PR's approval is never read again. A forge that has not marked it
    merged yet (R35) still reads it OPEN, and its patch-id against the new main is "":
    settling it would void the approval and strip the label."""
    forge = _Forge({"state": "OPEN", "head_oid": "h2", "labels": [LABEL]})
    written: list[tuple[str, BatchEvent]] = []

    got = settle_approvals(
        forge, lambda bid, ev: written.append((bid, ev)), REPO,
        [(_batch(_approval("h1", "p1")), 7)], lambda _: None, now=NOW,
        patch_id_of=lambda pr, head, fresh=False: "", landed=frozenset({"a"}),
    )  # fmt: skip

    assert written == [] and forge.label_edits == [] and got == {}
