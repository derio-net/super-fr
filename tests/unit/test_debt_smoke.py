"""Smoke test for the debt-engine branch (spec 2026-10-11-debt-engine)."""

from __future__ import annotations


def test_debt_status_vocabulary_is_importable() -> None:
    from typing import get_args

    from fr.acceptance.model import Status

    assert "ci" in get_args(Status)
