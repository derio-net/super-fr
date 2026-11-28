"""Operator queue requests: the `queue_add` / `queue_remove` events, their schema-14 stamp
and the pure fold (spec 2026-11-24-wave-queue-gaps R11, R16, §C)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.triage.batch import save_queue_requests
from fr.triage.errors import TriageError
from fr.triage.model import (
    Judgements,
    QueueAddEvent,
    QueueEntryRef,
    QueueRemoveEvent,
    load_judgements,
)
from fr.triage.queue_requests import Added, added
from pydantic import ValidationError

T0 = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 24, 11, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def _add(pr: int = 7, at: datetime = T0, **over: Any) -> QueueAddEvent:
    base: dict[str, Any] = {
        "kind": "queue_add", "at": at, "repo": "derio-net/super-fr", "scope": "derio-net",
        "pr": pr, "by": "alice",
    }  # fmt: skip
    return QueueAddEvent.model_validate({**base, **over})


def _remove(pr: int = 7, at: datetime = T1, **over: Any) -> QueueRemoveEvent:
    base: dict[str, Any] = {
        "kind": "queue_remove", "at": at, "repo": "derio-net/super-fr", "scope": "derio-net",
        "pr": pr, "by": "bob",
    }  # fmt: skip
    return QueueRemoveEvent.model_validate({**base, **over})


def _doc(schema: int, *requests: dict[str, Any]) -> dict[str, Any]:
    return {"schema": schema, "queue_requests": list(requests)}


def test_an_add_defaults_to_not_preapproved_and_a_remove_has_no_preapproval() -> None:
    assert _add().preapproved is False
    with pytest.raises(ValidationError):
        _remove(preapproved=True)


def test_an_operator_entry_ref_is_a_pr_kind() -> None:
    assert QueueEntryRef(pr=3, kind="operator").kind == "operator"


def test_judgements_default_to_no_queue_requests() -> None:
    assert Judgements.model_validate({"schema": 14}).queue_requests == []


@pytest.mark.parametrize("schema", [12, 13])
def test_queue_requests_below_schema_14_are_refused(schema: int) -> None:
    doc = _doc(schema, _add().model_dump(mode="json"))
    with pytest.raises(ValidationError, match="needs schema 14"):
        Judgements.model_validate(doc)


def test_schema_14_queue_requests_round_trip() -> None:
    doc = _doc(14, _add(preapproved=True).model_dump(mode="json"),
               _remove().model_dump(mode="json"))  # fmt: skip
    judgements = Judgements.model_validate(doc)

    first, second = judgements.queue_requests
    assert isinstance(first, QueueAddEvent) and first.preapproved
    assert isinstance(second, QueueRemoveEvent) and second.by == "bob"
    dumped = judgements.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    assert Judgements.model_validate(dumped) == judgements


def test_queue_requests_must_be_time_ordered() -> None:
    doc = _doc(14, _add(at=T1).model_dump(mode="json"), _remove(at=T0).model_dump(mode="json"))
    with pytest.raises(ValidationError, match="time-ordered"):
        Judgements.model_validate(doc)


def test_added_gives_each_pr_whose_latest_event_is_an_add() -> None:
    requests = [_add(7, T0, preapproved=True), _add(8, T1, by="carol")]

    assert added(requests, "derio-net/super-fr", "derio-net") == {
        7: Added(pr=7, preapproved=True, at=T0, by="alice"),
        8: Added(pr=8, preapproved=False, at=T1, by="carol"),
    }


def test_added_ignores_other_repos_and_scopes() -> None:
    requests = [_add(7, repo="derio-net/other"), _add(8, scope="someone-else")]

    assert added(requests, "derio-net/super-fr", "derio-net") == {}


def test_a_remove_after_an_add_drops_it_and_a_later_add_restores_it() -> None:
    assert added([_add(7, T0), _remove(7, T1)], "derio-net/super-fr", "derio-net") == {}
    again = added([_add(7, T0), _remove(7, T1), _add(7, T2, by="dan")],
                  "derio-net/super-fr", "derio-net")  # fmt: skip
    assert again == {7: Added(pr=7, preapproved=False, at=T2, by="dan")}


def test_save_queue_requests_writes_and_stamps_14(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text("# keep me\nschema: 13\ntiers: []\n")

    save_queue_requests(path, [_add()], read=[])

    text = path.read_text("utf-8")
    assert "# keep me" in text and "\nschema: 14\n" in text
    assert load_judgements(path).queue_requests == [_add()]


def test_save_queue_requests_refuses_a_file_changed_since_read(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_doc(14, _add().model_dump(mode="json"))))
    before = path.read_bytes()

    with pytest.raises(TriageError, match="changed since it was read"):
        save_queue_requests(path, [_add(8)], read=[])
    assert path.read_bytes() == before
