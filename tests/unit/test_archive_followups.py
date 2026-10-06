"""`fr archive` does its own follow-ups (spec 2026-10-06-archive-followups-design)."""

from __future__ import annotations


def test_the_followup_seams_import() -> None:
    from fr.archive import MoveLog, recording_moves

    assert MoveLog is not None and recording_moves is not None
