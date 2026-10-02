"""Waves and dependencies on a triage batch (spec 2026-10-02-wave-driver §A, R1)."""

from __future__ import annotations

from fr.triage.model import Batch


def test_a_batch_carries_a_wave() -> None:
    batch = Batch.model_validate({"id": "a", "title": "A", "ids": ["super-fr#1"], "wave": 2})
    assert batch.wave == 2
    assert Batch.model_validate({"id": "a", "title": "A", "ids": ["super-fr#1"]}).wave is None
