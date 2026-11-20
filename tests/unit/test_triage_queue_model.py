"""Judgements schema 13: the `queues:` list and its events (spec 2026-11-19-wave-merge-queue
R24), and a batch's `deferred` and `requeued` events (R29)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.triage.batch import save_batches
from fr.triage.model import (
    _EVENT_SCHEMAS,
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    DeferredEvent,
    Judgements,
    QueueApprovalEvent,
    QueueRecord,
    RequeuedEvent,
    load_judgements,
)
from pydantic import ValidationError

SHA = "a" * 40
MAIN = "b" * 40
QUEUE_KINDS = (
    "queue_open",
    "queue_built",
    "queue_eject",
    "queue_land",
    "queue_drain",
    "queue_cleared",
    "queue_release",
    "queue_postmerge_done",
    "queue_halt",
    "queue_slot_lost",
)


def _queue_events() -> list[dict[str, Any]]:
    at = "2026-11-19T10:{:02d}:00Z"
    batch = {"batch": "b"}
    closeout = {"pr": 7, "kind": "closeout"}
    return [
        {"kind": "queue_open", "at": at.format(0)},
        {
            "kind": "queue_built",
            "at": at.format(1),
            "slot": 1,
            "sha": SHA,
            "entry": batch,
            "head": SHA,
            "patch_id": "c" * 40,
            "base": MAIN,
        },
        {"kind": "queue_eject", "at": at.format(2), "entry": batch, "reason": "red"},
        {
            "kind": "approval",
            "at": at.format(3),
            "entry": closeout,
            "head": SHA,
            "patch_id": "d" * 40,
        },  # fmt: skip
        {"kind": "queue_land", "at": at.format(4), "main": MAIN, "entries": [closeout]},
        {
            "kind": "queue_release",
            "at": at.format(5),
            "entry": closeout,
            "head": SHA,
            "patch_id": "d" * 40,
        },  # fmt: skip
        {"kind": "queue_postmerge_done", "at": at.format(6), "entry": closeout},
        {"kind": "queue_slot_lost", "at": at.format(7), "slot": 2, "sha": SHA, "found": MAIN},
        {
            "kind": "queue_halt",
            "at": at.format(7),
            "state": "held",
            "detail": "GH013",
            "land": "push",
            "main": MAIN,
        },  # fmt: skip
        {"kind": "queue_drain", "at": at.format(7), "main": MAIN},
        {"kind": "queue_cleared", "at": at.format(8)},
    ]


def _doc(schema: int, **extra: Any) -> dict[str, Any]:
    return {
        "schema": schema,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"super-fr#1": {"tier": 1}},
        "batches": [
            {
                "id": "b",
                "title": "t",
                "ids": ["super-fr#1"],
                "wave": 1,
                "events": extra.pop("batch_events", []),
            }
        ],
        **extra,
    }


def _queue(**over: Any) -> dict[str, Any]:
    return {
        "repo": "derio-net/super-fr",
        "wave": 1,
        "scope": "derio-net",
        "base": MAIN,
        "events": _queue_events(),
        **over,
    }


def test_judgements_schema_is_13_and_reads_1_to_13() -> None:
    assert JUDGEMENTS_SCHEMA == 13
    assert JUDGEMENTS_READS == tuple(range(1, 14))


def test_a_queue_record_round_trips_every_kind_of_r24() -> None:
    judgements = Judgements.model_validate(_doc(13, queues=[_queue()]))

    (queue,) = judgements.queues
    assert isinstance(queue, QueueRecord)
    assert {e.kind for e in queue.events} == {*QUEUE_KINDS, "approval"}
    approval = next(e for e in queue.events if e.kind == "approval")
    assert isinstance(approval, QueueApprovalEvent)
    assert approval.entry.pr == 7 and approval.entry.kind == "closeout"
    dumped = judgements.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    assert Judgements.model_validate(dumped) == judgements


def test_a_queue_with_no_wave_is_a_between_waves_queue() -> None:
    judgements = Judgements.model_validate(_doc(13, queues=[_queue(wave=None)]))

    assert judgements.queues[0].wave is None


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"batch": "b", "pr": 3, "kind": "export"},
        {"pr": 3},
        {"kind": "archive"},
        {"pr": 3, "kind": "release"},
    ],  # fmt: skip
)
def test_an_entry_names_a_batch_or_a_pr_and_its_kind(entry: dict[str, Any]) -> None:
    events = [{"kind": "queue_postmerge_done", "at": "2026-11-19T10:00:00Z", "entry": entry}]

    with pytest.raises(ValidationError):
        Judgements.model_validate(_doc(13, queues=[_queue(events=events)]))


def test_queue_events_must_be_time_ordered() -> None:
    with pytest.raises(ValidationError, match="time-ordered"):
        Judgements.model_validate(_doc(13, queues=[_queue(events=_queue_events()[::-1])]))


def test_a_batch_deferred_and_requeued_events_round_trip() -> None:
    events = [
        {"kind": "deferred", "at": "2026-11-19T10:00:00Z", "wave": 1},
        {"kind": "requeued", "at": "2026-11-19T10:01:00Z", "wave": 2},
        {"kind": "requeued", "at": "2026-11-19T10:02:00Z"},
    ]
    judgements = Judgements.model_validate(_doc(13, batch_events=events))

    deferred, requeued, later = judgements.batches[0].events
    assert isinstance(deferred, DeferredEvent) and deferred.wave == 1
    assert isinstance(requeued, RequeuedEvent) and requeued.wave == 2
    assert isinstance(later, RequeuedEvent) and later.wave is None


def test_every_new_kind_is_registered_at_13() -> None:
    at_13 = next(kinds for needs, kinds in _EVENT_SCHEMAS if needs == 13)

    assert at_13 >= {*QUEUE_KINDS, "deferred", "requeued"}


def test_a_schema_12_file_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_doc(12)))

    assert load_judgements(path).schema_ == 12


@pytest.mark.parametrize("kind", ["deferred", "requeued"])
def test_a_schema_13_batch_kind_in_a_file_stamped_12_is_refused(kind: str) -> None:
    events = [{"kind": kind, "at": "2026-11-19T10:00:00Z", "wave": 1}]

    with pytest.raises(ValidationError, match=f"`{kind}` events need schema 13"):
        Judgements.model_validate(_doc(12, batch_events=events))


def test_queues_in_a_file_stamped_12_are_refused() -> None:
    with pytest.raises(ValidationError, match="schema 13"):
        Judgements.model_validate(_doc(12, queues=[_queue()]))


def test_writing_stamps_13(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_doc(12)))
    batches = load_judgements(path).batches

    save_batches(path, batches, read=batches)

    assert "\nschema: 13\n" in path.read_text("utf-8")
    assert load_judgements(path).schema_ == 13


# ------------------------------------------------------------------ patch-ids (R12; p1-r5, p1-r7)

_APPROVAL = {"kind": "approval", "at": "2026-11-19T10:00:00Z", "pr": 7, "head": SHA}
_UPDATE = {
    "kind": "update", "at": "2026-11-19T10:01:00Z", "pr": 7, "head_before": SHA,
    "head_after": MAIN, "base": MAIN,
}  # fmt: skip


@pytest.mark.parametrize("schema", [9, 12])
def test_an_approval_patch_id_in_a_file_stamped_below_13_is_refused(schema: int) -> None:
    events = [{**_APPROVAL, "patch_id": "p1"}]

    with pytest.raises(ValidationError, match="an approval's `patch_id` needs schema 13"):
        Judgements.model_validate(_doc(schema, batch_events=events))


@pytest.mark.parametrize("schema", [9, 12])
def test_an_update_patch_id_in_a_file_stamped_below_13_is_refused(schema: int) -> None:
    events = [{**_UPDATE, "patch_id": "p1"}]

    with pytest.raises(ValidationError, match="an update's `patch_id` needs schema 13"):
        Judgements.model_validate(_doc(schema, batch_events=events))


def test_approval_and_update_patch_ids_load_at_13_and_are_optional() -> None:
    events = [{**_APPROVAL, "patch_id": "p1"}, {**_UPDATE, "patch_id": "p2"}, _UPDATE]
    judgements = Judgements.model_validate(_doc(13, batch_events=events))

    approval, update, bare = judgements.batches[0].events
    assert getattr(approval, "patch_id") == "p1"
    assert getattr(update, "patch_id") == "p2"
    assert getattr(bare, "patch_id") is None
    # the same events with no id still load at 12
    Judgements.model_validate(_doc(12, batch_events=[_APPROVAL, _UPDATE]))
