"""Smoke for the wave merge queue (spec 2026-11-19-wave-merge-queue)."""

from __future__ import annotations

from fr.triage import model


def test_the_judgements_schema_is_an_int() -> None:
    assert isinstance(model.JUDGEMENTS_SCHEMA, int)
