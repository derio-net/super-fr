"""Spec 2026-09-14-ste-output-tone §5.C: warn-only prose lint for fr artifacts."""

from __future__ import annotations

import re
from pathlib import Path

import fr.prose_lint as lint
import pytest
from fr.prose_lint import MAX_SENTENCE_WORDS, ProseIssue, lint_prose

LONG = " ".join(["word"] * 30) + "."


def _words(n: int) -> str:
    return " ".join(["word"] * n)


def _sentence(n: int) -> str:
    return _words(n) + "."


def _long_counts(text: str) -> list[int | None]:
    return [i.words for i in lint_prose(text) if i.kind == "long-sentence"]


def test_the_limit_is_25_words() -> None:
    assert MAX_SENTENCE_WORDS == 25


def test_a_25_word_sentence_passes() -> None:
    assert lint_prose(_sentence(25)) == []


def test_a_26_word_sentence_warns() -> None:
    issues = lint_prose(_sentence(26))
    assert [(i.kind, i.words) for i in issues] == [("long-sentence", 26)]


def test_sentences_are_counted_separately() -> None:
    assert lint_prose(_sentence(20) + " " + _sentence(20)) == []


@pytest.mark.parametrize("mark", ["?", "!"])
def test_question_and_exclamation_marks_end_a_sentence(mark: str) -> None:
    assert lint_prose(_words(20) + mark + " " + _sentence(20)) == []


def test_a_blank_line_ends_an_item() -> None:
    assert lint_prose(_words(20) + "\n\n" + _sentence(20)) == []


def test_list_items_are_counted_separately() -> None:
    words = _words(20)
    assert lint_prose(f"- {words}\n- {words}") == []


@pytest.mark.parametrize("marker", ["1.", "1)"])
def test_numbered_list_items_are_counted_separately(marker: str) -> None:
    second = marker.replace("1", "2")
    assert lint_prose(f"{marker} {_words(20)}\n{second} {_words(20)}") == []


@pytest.mark.parametrize("closer", ["**", ")", '"', "`", "_"])
def test_a_closer_after_the_period_still_ends_the_sentence(closer: str) -> None:
    opener = {"**": "**", ")": "(", '"': "", "`": "", "_": "_"}[closer]
    text = f"{opener}Short lead.{closer} {_sentence(24)}"
    assert _long_counts(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "```\n" + LONG + "\n```",
        "```python\n" + LONG + "\n```",
        "~~~\n" + LONG + "\n~~~",
        "- item\n  ```\n  " + LONG + "\n  ```\nAfter.",
        "````\n```\n" + LONG + "\n```\n" + LONG + "\n````",
        "BEGIN tests/x.py\n" + LONG + "\nEND tests/x.py",
        "BEGIN replacement\n" + LONG + "\nEND",
        "`" + LONG + "`",
        '"' + LONG + '"',
        "<!-- " + LONG + " -->",
        "## " + LONG,
        "| " + LONG + " |",
        "---\ntitle: " + LONG + "\n---\n",
        "---\r\ntitle: " + LONG + "\r\n---\r\nShort.",
    ],
    ids=[
        "fence",
        "fence-with-language",
        "tilde-fence",
        "indented-fence",
        "four-backtick-fence",
        "embed",
        "embed-bare-end",
        "inline-code",
        "quoted",
        "comment",
        "heading",
        "table",
        "front-matter",
        "front-matter-crlf",
    ],
)
def test_non_prose_is_not_counted(text: str) -> None:
    assert lint_prose(text) == []


def test_an_embed_ends_only_at_its_own_end_line() -> None:
    """A code line that starts with END must not close the embed early."""
    text = "BEGIN tests/x.py\nEND = 1\n" + LONG + "\nEND tests/x.py"
    assert lint_prose(text) == []


def test_a_hash_without_a_space_is_prose_not_a_heading() -> None:
    assert _long_counts("#123 " + LONG) == [31]


def test_a_quote_across_a_line_wrap_is_stripped_whole() -> None:
    text = f'Replace "{_words(10)}\n{_words(10)}" with "{_words(8)} `a |\nb` {_words(8)}" now.'
    assert lint_prose(text) == []


def test_inline_code_across_a_line_wrap_is_stripped_whole() -> None:
    text = f"Run `{_words(15)}\n{_words(15)}` now."
    assert lint_prose(text) == []


def test_a_quoted_sentence_end_still_ends_the_sentence() -> None:
    assert lint_prose(f'He wrote "stop." {_sentence(24)}') == []


def test_a_url_does_not_count_as_words() -> None:
    text = _words(24) + " https://example.com/one-two/three-four/five."
    assert lint_prose(text) == []


def test_a_path_counts_as_one_word() -> None:
    assert lint_prose(_words(24) + " packages/fr/src/fr/isolation/local.py.") == []
    assert _long_counts(_words(25) + " packages/fr/src/fr/isolation/local.py.") == [26]


def test_a_lone_dash_is_not_a_word() -> None:
    assert lint_prose(_words(12) + " - " + _words(13) + ".") == []


def test_a_filler_word_warns() -> None:
    issues = lint_prose("This is just a test.")
    assert [(i.kind, i.excerpt) for i in issues] == [("filler", "just")]


def test_a_quoted_filler_word_is_ignored() -> None:
    assert lint_prose('Do not write "just".') == []


def test_filler_matches_whole_words_only() -> None:
    assert lint_prose("Adjust the value.") == []


@pytest.mark.parametrize("text", ["See src/just/file.py now.", "Use just-in-time loading."])
def test_filler_inside_a_path_or_hyphenated_word_is_ignored(text: str) -> None:
    assert lint_prose(text) == []


def test_a_two_word_filler_matches_across_a_line_break() -> None:
    issues = lint_prose("I\nthink it works.")
    assert [i.excerpt for i in issues] == ["I think"]


def test_long_sentences_come_before_fillers() -> None:
    kinds = [i.kind for i in lint_prose("It is just so. " + LONG)]
    assert kinds == ["long-sentence", "filler"]


def test_a_long_excerpt_is_truncated_to_80_characters() -> None:
    issue = lint_prose(" ".join(["longerword"] * 30) + ".")[0]
    assert len(issue.excerpt) == 80
    assert issue.excerpt.endswith("…")


def test_issue_strings_are_one_line_messages() -> None:
    assert str(ProseIssue("long-sentence", "a b c", 30)) == "sentence of 30 words (max 25): a b c"
    assert str(ProseIssue("filler", "just")) == "filler word 'just'"


STYLE = (
    Path(__file__).resolve().parents[2]
    / "plugins/super-fr/output-styles/simplified-technical-english.md"
)


def _style_filler_list() -> list[str]:
    text = " ".join(STYLE.read_text().split())
    bullet = text.split("Do not use filler", 1)[1].split(" - ", 1)[0]
    return [w.lower() for w in re.findall(r'"([^"]+)"', bullet)]


def test_filler_words_match_the_ste_style_list() -> None:
    """The lint and the opt-in style name the same filler words (spec §5.C)."""
    assert _style_filler_list() == [w.lower() for w in lint.FILLER_WORDS]


def test_the_filler_tripwire_can_fail(monkeypatch) -> None:
    monkeypatch.setattr(lint, "FILLER_WORDS", ("just",))
    with pytest.raises(AssertionError):
        test_filler_words_match_the_ste_style_list()
