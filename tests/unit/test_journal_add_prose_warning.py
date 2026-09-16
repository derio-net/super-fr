"""Spec 2026-09-14-ste-output-tone §5.C: journal add warns, never fails."""

from __future__ import annotations

from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

from tests.unit.test_journal_cmd import _init_repo

runner = CliRunner()
LONG = " ".join(["word"] * 30) + "."


def _add(title: str, body: str, entry_id: str):
    return runner.invoke(
        app,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            title,
            "--body",
            body,
            "--id",
            entry_id,
        ],
    )


def test_a_long_sentence_warns_and_exits_zero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(_init_repo(tmp_path))
    result = _add("Short title", LONG, "e1")
    assert result.exit_code == 0, result.output
    assert "warning: journal entry e1: body: sentence of 30 words" in result.output


def test_each_warning_is_one_physical_line(tmp_path: Path, monkeypatch) -> None:
    """Rich wraps at 80 columns off a TTY, so a five-warning cap printed 11
    lines (phase 7 review, finding I1). soft_wrap keeps one line per warning."""
    monkeypatch.chdir(_init_repo(tmp_path))
    result = _add("Short title", LONG, "e5")
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1, lines


def test_a_filler_in_both_title_and_body_names_its_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(_init_repo(tmp_path))
    result = _add("It is just a title", "It is just a body.", "e6")
    warnings = [line for line in result.output.splitlines() if line.startswith("warning:")]
    assert warnings == [
        "warning: journal entry e6: title: filler word 'just'",
        "warning: journal entry e6: body: filler word 'just'",
    ]


def test_a_clean_entry_prints_no_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(_init_repo(tmp_path))
    result = _add("Short title", "The test passes.", "e2")
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.output


def test_an_idempotent_re_add_prints_no_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(_init_repo(tmp_path))
    _add("Short title", LONG, "e3")
    result = _add("Short title", LONG, "e3")
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.output


def test_warnings_stop_after_five_lines(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(_init_repo(tmp_path))
    result = _add("Short title", " ".join([LONG] * 8), "e4")
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert all(line.startswith("warning:") for line in lines), lines
    assert len(lines) == 6
    assert lines[-1] == "warning: journal entry e4: … 3 more"
