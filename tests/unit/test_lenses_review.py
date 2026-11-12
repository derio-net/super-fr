"""`fr.lenses.review` — the `review-lens` block a lens reviewer ends its return
with, and the lens finding-id grammar (spec 2026-11-12-review-lenses R9, §3.C)."""

from __future__ import annotations

import pytest
from fr.lenses.review import (
    LENS_FINDING_ID_RE,
    ReviewLensBlockError,
    lens_finding_ids,
    lens_review_rule,
    parse_review_lens,
)
from fr.run.review_return import parse_review_findings


def test_the_block_gives_the_lens_and_the_examined_files() -> None:
    text = "Read it.\n\n```review-lens\nlens: security\nexamined: a.py, b/c.py\n```\n"
    assert parse_review_lens(text) == ("security", ("a.py", "b/c.py"))


def test_no_block_is_none() -> None:
    assert parse_review_lens("I looked at everything.") is None
    assert parse_review_lens("```review-findings\nnone\n```") is None


def test_the_last_block_is_the_one_read() -> None:
    text = (
        "```review-lens\nlens: tests\nexamined: a.py\n```\n"
        "```review-lens\nlens: security\nexamined: b.py\n```"
    )
    assert parse_review_lens(text) == ("security", ("b.py",))


@pytest.mark.parametrize(
    "body",
    [
        "",
        "lens: security",
        "examined: a.py",
        "lens: security\nlens: tests\nexamined: a.py",
        "lens: security\nexamined: ",
        "lens: security\nexamined: , ,",
        "lens: Security!\nexamined: a.py",
        "lens: security\nexamined: a.py\nnote: x",
    ],
)
def test_a_malformed_block_raises(body: str) -> None:
    with pytest.raises(ReviewLensBlockError):
        parse_review_lens(f"```review-lens\n{body}\n```")


def test_the_per_lens_grammar_carries_the_lens() -> None:
    rx = lens_finding_ids("security")
    assert rx.pattern == "^l-security-r[1-9][0-9]*$"
    assert rx.match("l-security-r1")
    assert not rx.match("l-tests-r1")
    assert not rx.match("l-security-r0")
    assert LENS_FINDING_ID_RE.match("l-security-r12")
    assert LENS_FINDING_ID_RE.match("l-my-lens2-r1")
    assert not LENS_FINDING_ID_RE.match("p2-r1")


def test_the_rule_names_both_fences_and_the_id_prefix() -> None:
    rule = lens_review_rule("security")
    assert "```review-lens" in rule
    assert "```review-findings" in rule
    assert "l-security-r" in rule
    assert "lens: security" in rule
    # the example in the rule parses with the lens's own grammar
    assert parse_review_lens(rule) is not None
    assert parse_review_findings(rule, id_re=lens_finding_ids("security")) is not None
