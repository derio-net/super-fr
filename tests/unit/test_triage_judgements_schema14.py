"""Judgements schema 14: the `conflict` event's `onto` and `reissue` (spec
2026-11-24-wave-queue-gaps R16, §D)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.triage.batch import save_batches
from fr.triage.model import (
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    ConflictEvent,
    Judgements,
    load_judgements,
)
from pydantic import ValidationError

SHA = "a" * 40
ONTO = "b" * 40


def _conflict(**over: Any) -> dict[str, Any]:
    return {
        "kind": "conflict",
        "at": "2026-11-24T10:00:00Z",
        "head": SHA,
        "paths": ["a.py"],
        "delivered": "session",
        **over,
    }


def _doc(schema: int, *events: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": schema,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"super-fr#1": {"tier": 1}},
        "batches": [
            {"id": "b", "title": "t", "ids": ["super-fr#1"], "wave": 1, "events": list(events)}
        ],  # fmt: skip
    }


def test_judgements_schema_is_14_and_reads_1_to_14() -> None:
    assert JUDGEMENTS_SCHEMA == 14
    assert JUDGEMENTS_READS == tuple(range(1, 15))


def test_a_conflict_event_defaults_to_no_onto_and_no_reissue() -> None:
    event = ConflictEvent.model_validate(_conflict())

    assert event.onto is None and event.reissue is False


@pytest.mark.parametrize(
    "over", [{"onto": ONTO}, {"reissue": True}, {"onto": ONTO, "reissue": True}]
)
def test_a_conflict_onto_or_reissue_in_a_file_stamped_13_is_refused(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="schema 14"):
        Judgements.model_validate(_doc(13, _conflict(**over)))


def test_a_schema_14_conflict_round_trips() -> None:
    judgements = Judgements.model_validate(_doc(14, _conflict(onto=ONTO, reissue=True)))

    (event,) = judgements.batches[0].events
    assert isinstance(event, ConflictEvent) and event.onto == ONTO and event.reissue
    dumped = judgements.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    assert Judgements.model_validate(dumped) == judgements


@pytest.mark.parametrize("schema", range(5, 14))
def test_a_plain_conflict_in_files_stamped_5_to_13_still_loads(schema: int) -> None:
    assert Judgements.model_validate(_doc(schema, _conflict())).schema_ == schema


@pytest.mark.parametrize("schema", range(3, 15))
def test_files_stamped_3_to_14_still_load(tmp_path: Path, schema: int) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_doc(schema)))

    assert load_judgements(path).schema_ == schema


def test_writing_stamps_14(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_doc(13)))
    batches = load_judgements(path).batches

    save_batches(path, batches, read=batches)

    assert "\nschema: 14\n" in path.read_text("utf-8")
