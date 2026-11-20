"""The DevOps stage's two labels settled on the queue's events (spec
2026-11-19-wave-merge-queue R26): `fr-queue:release` into `queue_release` at the head and
patch-id, void (label off) when the diff moved after it, and `fr-queue:postmerge-done` into
`queue_postmerge_done`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fr.triage.approval import settle_postmerge_done, settle_release
from fr.triage.model import QueueEntryRef, QueuePostmergeDoneEvent, QueueReleaseEvent

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
REPO = "derio-net/super-fr"
ENTRY = QueueEntryRef(batch="d")


class Client:
    def __init__(self) -> None:
        self.edits: list[tuple[int, frozenset[str], frozenset[str]]] = []

    def edit_issue_labels(self, repo: str, n: int, *, add: frozenset[str],
                          remove: frozenset[str]) -> None:  # fmt: skip
        self.edits.append((n, add, remove))

    def label_exists(self, repo: str, name: str) -> bool:
        return True


def _event(patch_id: str, head: str = "h1") -> QueueReleaseEvent:
    return QueueReleaseEvent(kind="queue_release", at=NOW, entry=ENTRY, head=head,
                             patch_id=patch_id)  # fmt: skip


def _view(*labels: str, head: str = "h1") -> dict[str, Any]:
    return {"labels": list(labels), "head_oid": head}


@pytest.fixture(autouse=True)
def _labels_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fr.triage.approval._labels_off", lambda *a: None)


def _settle(
    events: list[QueueReleaseEvent],
    view: dict[str, Any],
    patch: str | None,
    *,
    dry_run: bool = False,
) -> tuple[bool, list[Any], Client, list[str]]:
    client = Client()
    got: list[Any] = []
    said: list[str] = []

    def reader(pr: int, head: str, *, fresh: bool = False) -> str | None:
        return patch

    ok = settle_release(client, got.append, REPO, ENTRY, 7, events, view, said.append,
                        now=NOW, dry_run=dry_run, patch_id_of=reader)  # fmt: skip
    return ok, got, client, said


def test_no_label_is_no_release() -> None:
    ok, got, client, _ = _settle([], _view("gate:devops"), "p1")
    assert not ok and got == [] and client.edits == []


def test_a_first_release_is_recorded_at_the_head_and_patch_id() -> None:
    ok, got, _, said = _settle([], _view("fr-queue:release"), "p1")
    assert ok
    (event,) = got
    assert (event.kind, event.entry, event.head, event.patch_id) == (
        "queue_release",
        ENTRY,
        "h1",
        "p1",
    )
    assert any("recorded" in line for line in said)


def test_a_recorded_release_at_the_same_patch_id_stands_even_at_a_new_head() -> None:
    ok, got, client, _ = _settle([_event("p1")], _view("fr-queue:release", head="h2"), "p1")
    assert ok and got == [] and client.edits == []


def test_a_diff_that_moved_after_the_release_voids_it_and_removes_the_label() -> None:
    ok, got, client, said = _settle([_event("p1")], _view("fr-queue:release", head="h2"), "p2")
    assert not ok
    assert client.edits == [(7, frozenset(), frozenset({"fr-queue:release"}))]
    (event,) = got
    assert event.patch_id == "" and event.head == "h2"  # the void
    assert any("voided" in line and "fr ops gate" in line for line in said)


def test_after_a_void_the_label_back_is_a_new_release() -> None:
    ok, got, _, _ = _settle([_event("p1"), _event("", head="h2")],
                            _view("fr-queue:release", head="h2"), "p2")  # fmt: skip
    assert ok and got[0].patch_id == "p2"


def test_an_unreadable_patch_id_changes_nothing() -> None:
    ok, got, client, _ = _settle([_event("p1")], _view("fr-queue:release"), None)
    assert ok and got == [] and client.edits == []  # the recorded release stands
    ok, got, client, _ = _settle([], _view("fr-queue:release"), None)
    assert not ok and got == []  # nothing to pin a first release to


def test_a_dry_run_writes_nothing() -> None:
    ok, got, client, said = _settle([_event("p1")], _view("fr-queue:release"), "p2", dry_run=True)
    assert not ok and got == [] and client.edits == [] and "would void" in said[0]
    ok, got, _, said = _settle([], _view("fr-queue:release"), "p1", dry_run=True)
    assert ok and got == [] and "would record" in said[0]


def test_the_postmerge_done_label_is_recorded_once_it_is_there() -> None:
    got: list[QueuePostmergeDoneEvent] = []
    said: list[str] = []
    assert not settle_postmerge_done(got.append, ENTRY, _view("gate:devops"), said.append, now=NOW)
    assert got == []
    assert settle_postmerge_done(got.append, ENTRY, _view("fr-queue:postmerge-done"),
                                 said.append, now=NOW)  # fmt: skip
    assert [e.kind for e in got] == ["queue_postmerge_done"]
    assert settle_postmerge_done(lambda e: got.append(e), ENTRY,
                                 _view("fr-queue:postmerge-done"), said.append, now=NOW,
                                 dry_run=True)  # fmt: skip
    assert len(got) == 1
