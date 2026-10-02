"""fr-goal's prose after spec 2026-10-02-opencode-observe-2 (§F, §H, R7, R9):
OpenCode's question tool and reviewer ids are verified, and the reviewer's
prompt carries the brief's `review_findings` text with distinct letters."""

from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).parents[2] / "plugins/super-fr/skills/fr-goal/SKILL.md"


def _text() -> str:
    return " ".join(SKILL.read_text().split())


def test_the_questions_clause_has_opencode_use_its_question_tool_and_fr_verify_it() -> None:
    text = _text()
    assert (
        "OpenCode takes the same labelling and sequencing rules through its `question` tool" in text
    )
    assert "fr verifies the answers there" in text
    assert "Hermes has no question tool" in text
    assert "There is no default `answered_by`" in text


def test_the_spec_reviewer_clause_says_fr_verifies_the_id_on_opencode_too() -> None:
    assert "fr verifies the reviewer id there too" in _text()


def test_review_phase_puts_review_findings_in_each_prompt_with_distinct_letters() -> None:
    text = _text()
    assert "Put the brief's `review_findings` text verbatim into each reviewer's prompt" in text
    assert "give each its own letter" in text
    # p3-r6: it follows the scope definitions, never splits them.
    assert text.index("**out of scope** — true, but not caused by this change.") < text.index(
        "Put the brief's `review_findings` text verbatim"
    )
