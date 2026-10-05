"""Shared page chrome and fragments (spec 2026-10-05-triage-pages-goal, §A, §C)."""

from __future__ import annotations

import re

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


def test_page_header_marks_the_current_page_and_states_the_goal() -> None:
    from fr.triage.components import page_header

    h = page_header("origins")
    assert "<nav" in h
    for p in PAGES:
        assert f'href="{p.file}"' in h
    assert h.count('aria-current="page"') == 1
    assert re.search(r'<a [^>]*href="origins.html"[^>]*aria-current="page"', h) or re.search(
        r'<a [^>]*aria-current="page"[^>]*href="origins.html"', h
    )
    assert re.search(r'class="goal"[^>]*>[^<]*Where do defects come from', h)


def test_collapsed_renders_a_closed_fold_with_title_and_count() -> None:
    from fr.triage.components import collapsed

    h = collapsed("x", "A <Title>", 3, "<p>b</p>")
    assert h.startswith('<details id="x" class="fold">')
    assert " open" not in h.split(">")[0]
    assert "<summary>A &lt;Title&gt;" in h and '<span class="count">3</span>' in h
    assert "<p>b</p>" in h
    assert 'class="count"' not in collapsed("y", "T", None, "")
