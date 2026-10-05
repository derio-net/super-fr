"""`fr.run.review_return` — the `review-findings` block a phase reviewer ends
its return with, read out of its final message (spec
2026-10-02-opencode-observe-2 §E, R7)."""

from __future__ import annotations

import pytest
from fr.run.review_return import (
    ReviewFindingsBlockError,
    parse_review_findings,
    review_findings_rule,
)


def test_a_block_parses_to_id_scope_summary() -> None:
    text = "Reviewed phase 2.\n\n```review-findings\np2a-r1 | in | x\np2a-r2 | out | y | z\n```\n"
    assert parse_review_findings(text) == [("p2a-r1", "in", "x"), ("p2a-r2", "out", "y | z")]


def test_none_is_an_empty_block_and_no_block_is_none() -> None:
    assert parse_review_findings("Done.\n\n```review-findings\nnone\n```") == []
    assert parse_review_findings("Reviewed phase 2 and found nothing to raise.") is None


def test_a_plain_findings_fence_is_not_the_block() -> None:
    """`findings` is the step's DERIVED evidence; the reviewer's fence is
    `review-findings`, so the two are never confused (spec §E)."""
    assert parse_review_findings("```findings\np2-r1 | in | x\n```") is None


def test_the_trailing_block_is_the_one_read() -> None:
    text = (
        "```review-findings\np1-r1 | in | old\n```\nthen\n```review-findings\np2-r1 | in | new\n```"
    )
    assert parse_review_findings(text) == [("p2-r1", "in", "new")]


@pytest.mark.parametrize(
    "line",
    [
        "p2-r1 | maybe | bad scope",
        "p2-r1 | in",
        "p2-r1 in x",
        "finding-1 | in | not the brief's id",
        "p2ab-r1 | in | two letters",
        "p2-r1 | in |",
    ],
)
def test_a_malformed_line_raises_naming_it(line: str) -> None:
    with pytest.raises(ReviewFindingsBlockError, match="review-findings block"):
        parse_review_findings(f"```review-findings\n{line}\n```")


def test_an_empty_block_is_malformed() -> None:
    with pytest.raises(ReviewFindingsBlockError, match="review-findings block"):
        parse_review_findings("```review-findings\n```")


def test_the_rule_names_the_fence_and_this_phases_ids() -> None:
    rule = review_findings_rule(3)
    assert "```review-findings" in rule
    assert "p3-r<k>" in rule and "p3a-r<k>" in rule
    assert "none" in rule
    # p2-r3: the check accepts a finding journaled against this phase OR LATER.
    assert "for phase 3 or a later phase" in " ".join(rule.split())
    # The rule's own example parses with the parser it prescribes for.
    example = rule[rule.index("```review-findings") :]
    assert parse_review_findings(example) == [("p3-r1", "in", "<one-line summary>")]


def test_an_id_repeated_within_one_block_is_malformed() -> None:
    """Review p2-r1: one reviewer listing an id twice is a malformed block, not
    two reviewers returning the same id."""
    text = "```review-findings\np2-r1 | in | a\np2-r1 | out | b\n```"
    with pytest.raises(ReviewFindingsBlockError, match="p2-r1.*more than once"):
        parse_review_findings(text)
