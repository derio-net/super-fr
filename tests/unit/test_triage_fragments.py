"""Shared page chrome and fragments (spec 2026-10-05-triage-pages-goal, §A, §C)."""

from __future__ import annotations

from fr.triage.components import PAGES


def test_pages_registry_lists_the_four_pages() -> None:
    assert tuple(p.key for p in PAGES) == ("board", "origins", "architecture", "history")
    assert tuple(p.file for p in PAGES) == (
        "triage.html",
        "origins.html",
        "architecture.html",
        "history.html",
    )
    assert all(p.goal.endswith("?") and p.title for p in PAGES)
