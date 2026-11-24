"""Tests for `fr.triage.queue_handback` (spec 2026-11-24-wave-queue-gaps R1-R6)."""

from __future__ import annotations

from fr.triage import queue_handback


def test_the_module_names_its_spec() -> None:
    assert "2026-11-24-wave-queue-gaps" in (queue_handback.__doc__ or "")
    assert "R1-R6" in (queue_handback.__doc__ or "")
