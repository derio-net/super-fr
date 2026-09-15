"""Spec 2026-09-14-ste-output-tone §5.C: warn-only prose lint for fr artifacts."""

from __future__ import annotations

import pytest
from fr.prose_lint import MAX_SENTENCE_WORDS, lint_prose

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
