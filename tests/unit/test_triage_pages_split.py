"""The Backlog and Issues split and the render stamp (spec 2026-11-18-triage-pages-ux
R4, R5; §B, §C). Every input is an in-memory fixture; nothing is read from disk."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fr.triage import render as render_mod
from fr.triage.fragments import Entry, Resolved, resolve_manifest
from fr.triage.render import (
    BACKLOG_GENERATED,
    BACKLOG_MOVED,
    FILTER_BAR,
    ISSUES_GENERATED,
    ISSUES_MOVED,
    render_backlog,
    render_issues,
)

from tests.unit.triage_board_fixtures import busy

AT = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)


def _ids(page: str) -> list[str]:
    body = page[page.index('<p class="goal">') :]
    return re.findall(r'<(?:section|details)[^>]*\bid="([a-z-]+)"', body)


def test_the_backlog_holds_the_decisions_only() -> None:
    assert BACKLOG_GENERATED == ("since", "needs", "next-up", "waves", "batches")
    page = render_backlog(*busy(), rendered_at=AT)
    top = [i for i in _ids(page) if i in {
        "since-last-report", "needs-you-now", "next-up", "waves", "batches", "prs", "debt",
        "backlog-by-tier", "ranked-features", "parked", "possible-duplicates",
    }]  # fmt: skip
    assert top == ["since-last-report", "needs-you-now", "next-up", "waves", "batches"]
    assert 'class="stage-filter"' in page
    assert FILTER_BAR not in page
    assert "STAGE_FILTER_SCRIPT" not in page and render_mod.STAGE_FILTER_SCRIPT in page
    assert not hasattr(render_mod, "FOLD_SCRIPT") and not hasattr(render_mod, "render")


def test_the_issues_page_holds_the_lists_only() -> None:
    assert ISSUES_GENERATED == (
        "possible-duplicates", "backlog", "features", "parked", "awaiting-live",
        "closed-in-progress", "patterns", "debt", "prs",
    )  # fmt: skip
    page = render_issues(*busy(), rendered_at=AT)
    ids = _ids(page)
    for gone in ("since-last-report", "needs-you-now", "next-up", "waves", "batches"):
        assert gone not in ids
    assert "backlog-by-tier" in ids and "prs" in ids and "debt" in ids
    assert FILTER_BAR in page and 'class="stage-filter"' not in page
    assert '<a href="issues.html" aria-current="page">Issues</a>' in page
    assert 'class="goal">What is open, and how is it ranked?<' in page


def test_each_page_names_the_others_sections_as_moved() -> None:
    assert BACKLOG_MOVED == dict.fromkeys(ISSUES_GENERATED, "issues")
    assert ISSUES_MOVED == dict.fromkeys(BACKLOG_GENERATED, "backlog")


def test_a_backlog_manifest_naming_prs_gets_the_issues_note(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text("sections: [prs, since]\n", encoding="utf-8")
    resolved = resolve_manifest(tmp_path, BACKLOG_GENERATED, BACKLOG_MOVED)
    page = render_backlog(*busy(), resolved=resolved, rendered_at=AT)
    assert "manifest names `prs`, which is now on the Issues page; skipped" in page
    assert 'id="prs"' not in page


# ------------------------------------------------------------- the render stamp (R5)


def _backlog(at: datetime) -> str:
    return render_backlog(*busy(), rendered_at=at)


def _issues(at: datetime) -> str:
    return render_issues(*busy(), rendered_at=at)


def _board(at: datetime) -> str:
    from fr.triage.kanban import build_board
    from fr.triage.kanban_render import render_board

    f, jd = busy()
    return render_board(
        build_board(f, jd, {}), scope_args=["--repo", "x/y"], rendered_at=at, refresh=0, notes=[]
    )


def _origins(at: datetime) -> str:
    from fr.triage.origins import Origins, OriginsFacts, render_origins

    facts = OriginsFacts(
        scope="example-org/widgets", since="2026-09-01", collected_at="2026-11-18T08:00:00Z",
        issues=[],
    )  # fmt: skip
    return render_origins(facts, Origins(), rendered_at=at)


def _architecture(at: datetime) -> str:
    from fr.triage.architecture import GENERATED, render_architecture

    from tests.unit.test_triage_architecture import _subsystems

    f, jd = busy()
    return render_architecture(
        f, jd, subsystems=_subsystems(), measured={},
        resolved=Resolved(order=[Entry(g) for g in GENERATED]), rendered_at=at,
    )  # fmt: skip


def _history(at: datetime) -> str:
    from fr.triage.history import GENERATED, render_history

    f, jd = busy()
    return render_history(
        f, jd, snapshots=[], resolved=Resolved(order=[Entry(g) for g in GENERATED]),
        rendered_at=at,
    )  # fmt: skip


RENDERERS: dict[str, Callable[[datetime], str]] = {
    "backlog": _backlog,
    "issues": _issues,
    "batches": _board,
    "origins": _origins,
    "architecture": _architecture,
    "history": _history,
}


@pytest.mark.parametrize("name", sorted(RENDERERS))
def test_every_page_states_when_it_was_rendered_beside_the_collected_time(name: str) -> None:
    page = RENDERERS[name](AT)
    mast = page[: page.index('<nav class="pages"')]
    assert "rendered 2026-11-18 09:30 UTC" in mast
    assert "collected" in mast
    assert RENDERERS[name](AT) == page, "same inputs, same bytes"


@pytest.mark.parametrize("name", ["backlog", "issues", "batches"])
def test_each_footer_names_the_command_by_its_new_name(name: str) -> None:
    """R1, R2: a page names the command that writes it by its one name."""
    footer = RENDERERS[name](AT).rsplit("<footer", 1)[1]
    want = "fr triage batches" if name == "batches" else "fr triage backlog"
    assert want in footer
    assert "fr triage board" not in footer and "fr triage render" not in footer
