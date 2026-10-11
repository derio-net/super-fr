"""Synthetic audit events preserve the real dispatch's lifecycle identity."""

from datetime import UTC, datetime

import pytest
from fr.triage.batch import derive_batch_stage, last_dispatch, save_batches
from fr.triage.model import (
    Batch,
    CancelEvent,
    Facts,
    Judgements,
    Launch,
    ReplacementEvent,
    load_judgements,
)
from pydantic import ValidationError


def audit(result="attempt"):
    return ReplacementEvent(
        kind="replacement",
        at=datetime(2026, 10, 10, tzinfo=UTC),
        attempt="a1",
        result=result,
        reason="operator change",
        old=Launch(harness="claude", model="old"),
        new=Launch(harness="opencode", model="openai/new"),
        handle="pane-1",
        pane="pane-1",
        name="fr-batch",
        branch="feat/original",
    )


def batch():
    return Batch(
        id="one",
        title="One",
        ids=["repo#1"],
        events=[
            {
                "kind": "dispatch",
                "at": datetime(2026, 10, 9, tzinfo=UTC),
                "runner": "herdr",
                "handle": "pane-1",
                "branch": "feat/original",
                "reserved_version": "6.0.0",
            }
        ],
    )


@pytest.mark.parametrize("result", ["attempt", "success", "failure"])
def test_replacement_schema_roundtrip_and_original_dispatch(tmp_path, result):
    b = batch()
    original = last_dispatch(b)
    b = b.model_copy(update={"events": [*b.events, audit(result)]})
    path = tmp_path / "judgements.yaml"
    path.write_text("schema: 2\ntiers: [{n: 1, title: Now}]\nissues:\n  repo#1: {tier: 1}\n")
    save_batches(path, [b], read=[])
    loaded = load_judgements(path)
    assert loaded.schema_ == 8
    assert loaded.batches == [b]
    assert last_dispatch(b) == original
    assert (
        derive_batch_stage(
            b,
            Facts(
                scope="org",
                kind="org",
                collected_at=audit().at.isoformat(),
                repos=["org/repo"],
                issues=[],
            ),
        )
        == "dispatched"
    )


@pytest.mark.parametrize("schema", range(1, 7))
def test_old_schema_loads_but_rejects_replacement(schema):
    assert Judgements.model_validate({"schema": schema}).schema_ == schema
    b = batch().model_copy(update={"events": [audit()]})
    with pytest.raises(ValidationError):
        Judgements.model_validate(
            {
                "schema": schema,
                "tiers": [{"n": 1, "title": "Now"}],
                "issues": {"repo#1": {"tier": 1}},
                "batches": [b],
            }
        )


def test_audit_does_not_uncancel_batch():
    b = batch()
    b = b.model_copy(
        update={"events": [*b.events, CancelEvent(kind="cancel", at=audit().at), audit("failure")]}
    )
    # Validate dict events as a real file reader would.
    b = Batch.model_validate(b.model_dump())
    assert (
        derive_batch_stage(
            b,
            Facts(
                scope="org", kind="org", collected_at=audit().at.isoformat(), repos=[], issues=[]
            ),
        )
        == "cancelled"
    )
