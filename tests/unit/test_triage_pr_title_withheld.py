"""Where a withheld PR title shows, and what replaces it (spec 2026-11-28-triage-privacy R7)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fr.triage.batch_drive_types import LivePr
from fr.triage.kanban import GatedCard
from fr.triage.model import Batch, PullRequest
from fr.triage.render import TITLE_WITHHELD, _pr_cell, _pr_row


def _pr(title: str) -> PullRequest:
    return PullRequest(
        repo="example-org/outside",
        number=12,
        title=title,
        state="OPEN",
        is_draft=False,
        url="https://github.com/example-org/outside/pull/12",
    )


def test_a_pr_row_without_a_title_shows_the_withheld_note() -> None:
    row = _pr_row(_pr(""), None, 0, "2026-11-01T00:00:00+00:00")
    assert TITLE_WITHHELD in row and "outside#12" in row


def test_a_pr_row_with_a_title_shows_it() -> None:
    assert "a fix" in _pr_row(_pr("a fix"), None, 0, "2026-11-01T00:00:00+00:00")


def test_a_pr_cell_without_a_title_shows_the_withheld_note_and_the_link() -> None:
    cell = _pr_cell(_pr(""))
    assert TITLE_WITHHELD in cell and "pull/12" in cell


def test_a_gated_card_without_a_title_shows_the_withheld_note() -> None:
    from fr.triage.kanban import ColumnView
    from fr.triage.kanban_render import _gated_card

    card = GatedCard("example-org/outside", 12, "", "https://github.com/x/pull/12", "why")
    column = ColumnView(key="needs-tester", title="t", cards=(), gated=(card,))  # type: ignore[arg-type]
    assert TITLE_WITHHELD in _gated_card(card, column)


def test_the_text_check_prints_key_url_and_a_withheld_note(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fr.commands.triage_cmd import _pr_line
    from rich.console import Console

    Console().print(_pr_line(_pr("")))
    out = capsys.readouterr().out
    assert "outside#12" in out and "pull/12" in out and "title withheld" in out


def test_the_json_row_keeps_key_and_url_with_an_empty_title() -> None:
    from fr.triage.check import CheckResult

    result = CheckResult([], [_pr("")], [], [], [])
    (row,) = result.to_json()["unranked_prs"]
    assert (row["key"], row["title"]) == ("outside#12", "")
    assert row["url"].endswith("/pull/12")


def test_the_queue_subject_of_a_batch_pr_with_no_title_uses_the_batchs_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.commands import triage_batch_cmd
    from fr.triage.queue_exec import _subject

    batch = Batch(id="lifecycle", title="Lifecycle fixes", ids=["outside#1"])
    pr = _pr("").model_copy(update={"head_ref": "feat/x"})
    monkeypatch.setattr(triage_batch_cmd, "batch_pr", lambda b, f: pr)
    me: Any = SimpleNamespace(
        _queue_live={"lifecycle": LivePr(12, "OPEN", False, "abc", head_ref="feat/x")},
        _queue_batch=lambda key: batch,
    )
    entry = triage_batch_cmd._Driver._queue_entry(me, None, "lifecycle")  # type: ignore[arg-type]
    assert entry is not None
    assert _subject(entry, "squash") == "Lifecycle fixes (#12)"  # type: ignore[arg-type]
