"""Spec 2026-09-14-ste-output-tone §5.C: warn-only prose lint for fr artifacts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.prose_lint import FILLER_WORDS, MAX_SENTENCE_WORDS, lint_prose

LONG = " ".join(["word"] * 30) + "."


def _sentence(n: int) -> str:
    return " ".join(["word"] * n) + "."


def test_the_limit_is_25_words() -> None:
    assert MAX_SENTENCE_WORDS == 25


def test_a_25_word_sentence_passes() -> None:
    assert lint_prose(_sentence(25)) == []


def test_a_26_word_sentence_warns() -> None:
    issues = lint_prose(_sentence(26))
    assert [(i.kind, i.words) for i in issues] == [("long-sentence", 26)]


def test_sentences_are_counted_separately() -> None:
    assert lint_prose(_sentence(20) + " " + _sentence(20)) == []


def test_list_items_are_counted_separately() -> None:
    words = " ".join(["word"] * 20)
    assert lint_prose(f"- {words}\n- {words}") == []


@pytest.mark.parametrize(
    "text",
    [
        "```\n" + LONG + "\n```",
        "BEGIN tests/x.py\n" + LONG + "\nEND tests/x.py",
        "`" + LONG + "`",
        '"' + LONG + '"',
        "<!-- " + LONG + " -->",
        "## " + LONG,
        "| " + LONG + " |",
        "---\ntitle: " + LONG + "\n---\n",
    ],
    ids=["fence", "embed", "inline-code", "quoted", "comment", "heading", "table", "front-matter"],
)
def test_non_prose_is_not_counted(text: str) -> None:
    assert lint_prose(text) == []


def test_a_url_does_not_count_as_words() -> None:
    text = " ".join(["word"] * 24) + " https://example.com/one-two/three-four/five."
    assert lint_prose(text) == []


def test_a_filler_word_warns() -> None:
    issues = lint_prose("This is just a test.")
    assert [(i.kind, i.excerpt) for i in issues] == [("filler", "just")]


def test_a_quoted_filler_word_is_ignored() -> None:
    assert lint_prose('Do not write "just".') == []


def test_filler_matches_whole_words_only() -> None:
    assert lint_prose("Adjust the value.") == []


def test_a_two_word_filler_matches_across_a_line_break() -> None:
    issues = lint_prose("I\nthink it works.")
    assert [i.excerpt for i in issues] == ["I think"]


STYLE = (
    Path(__file__).resolve().parents[2]
    / "plugins/super-fr/output-styles/simplified-technical-english.md"
)


def test_filler_words_match_the_ste_style_list() -> None:
    """The lint and the opt-in style name the same filler words (spec §5.C)."""
    text = " ".join(STYLE.read_text().split())
    bullet = text.split("Do not use filler", 1)[1].split(" - ", 1)[0]
    quoted = [w.lower() for w in re.findall(r'"([^"]+)"', bullet)]
    assert quoted == [w.lower() for w in FILLER_WORDS]


def test_the_filler_tripwire_can_fail(monkeypatch) -> None:
    import fr.prose_lint as lint

    monkeypatch.setattr(lint, "FILLER_WORDS", ("just",))
    text = " ".join(STYLE.read_text().split())
    bullet = text.split("Do not use filler", 1)[1].split(" - ", 1)[0]
    quoted = [w.lower() for w in re.findall(r'"([^"]+)"', bullet)]
    assert quoted != [w.lower() for w in lint.FILLER_WORDS]
