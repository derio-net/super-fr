"""Smoke for the wave merge queue (spec 2026-11-19-wave-merge-queue)."""

from __future__ import annotations

from fr.triage import model


def test_the_judgements_schema_is_an_int() -> None:
    assert isinstance(model.JUDGEMENTS_SCHEMA, int)


def test_the_judgements_schema_is_pinned_to_the_queues_version() -> None:
    """l-tests-r4: spec R24 writes schema 13; a bump is a decision, made here on purpose."""
    assert model.JUDGEMENTS_SCHEMA == 13
