"""Smoke: the gate vocabulary exists (spec 2026-10-14 R2)."""

from __future__ import annotations


def test_gate_vocabulary() -> None:
    import fr.gates as g

    assert set(g.GATES) == {"developer", "reviewer", "tester", "devops", "owner", "security"}
    assert set(g.POST_MERGE_GATES) == {"tester", "devops"}
