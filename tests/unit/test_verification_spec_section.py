"""`fr.verification.spec_section` / `effective` — the spec's `## Verification`
section and the effective strategy of a row (spec 2026-10-06 §B, R6/R7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.verification.effective import effective_strategy, is_post_merge
from fr.verification.model import StrategyError
from fr.verification.spec_section import Section, SectionError, parse_section

SPEC = """\
# Title

## Verification

Prose that is not part of the grammar is ignored.

strategy: candidate
- row-a: live — needs a real herdr pane
- row-b: none — covered by unit tests
- row-c: client-live

## Next
- row-z: live — not in the section
"""


def test_parse_section_reads_strategy_and_row_lines() -> None:
    s = parse_section(SPEC)

    assert s is not None
    assert s.strategy == "candidate"
    assert s.rows["row-a"].strategy == "live"
    assert s.rows["row-a"].reason == "needs a real herdr pane"
    assert s.rows["row-b"].strategy == "none"
    assert s.rows["row-c"].reason is None
    assert "row-z" not in s.rows


def test_the_strategy_line_is_optional() -> None:
    s = parse_section("## Verification\n- r: none — why\n")

    assert s is not None
    assert s.strategy is None
    assert set(s.rows) == {"r"}


def test_a_missing_section_is_none() -> None:
    assert parse_section("# T\n\n## Other\n- r: live — x\n") is None


def test_a_heading_inside_a_code_fence_is_not_the_section() -> None:
    text = "```\n## Verification\nstrategy: live\n```\n\n## Verification\nstrategy: candidate\n"

    s = parse_section(text)

    assert s is not None
    assert s.strategy == "candidate"


@pytest.mark.parametrize(
    "line",
    [
        "- no colon here",
        "- row: ",
        "- row: Not A Name — x",
        "strategy:",
        "strategy: two words",
    ],
)
def test_a_malformed_line_is_a_section_error_naming_it(line: str) -> None:
    with pytest.raises(SectionError, match="line"):
        parse_section(f"## Verification\n{line}\n")


def test_a_repeated_row_or_strategy_line_is_refused() -> None:
    with pytest.raises(SectionError, match="row-a"):
        parse_section("## Verification\n- row-a: live — x\n- row-a: none — y\n")
    with pytest.raises(SectionError, match="strategy"):
        parse_section("## Verification\nstrategy: live\nstrategy: candidate\n")


# ── effective strategy: R7's precedence ───────────────────────────────


def _section(text: str) -> Section:
    s = parse_section(text)
    assert s is not None
    return s


def test_the_row_own_verify_wins() -> None:
    s = _section("## Verification\nstrategy: candidate\n- r: live — x\n")

    assert effective_strategy("prerelease", "r", s, "client-live") == "prerelease"


def test_then_the_spec_override_line_for_that_row() -> None:
    s = _section("## Verification\nstrategy: candidate\n- r: live — x\n")

    assert effective_strategy(None, "r", s, "client-live") == "live"


def test_then_the_spec_strategy_line() -> None:
    s = _section("## Verification\nstrategy: candidate\n")

    assert effective_strategy(None, "r", s, "client-live") == "candidate"


def test_then_the_shape_default() -> None:
    s = _section("## Verification\n- other: live — x\n")

    assert effective_strategy(None, "r", s, "client-live") == "client-live"
    assert effective_strategy(None, "r", s, None) is None


def test_a_run_with_no_section_and_a_row_with_no_verify_has_no_strategy() -> None:
    assert effective_strategy(None, "r", None, "candidate") is None


def test_a_run_with_no_section_still_honours_the_rows_own_verify() -> None:
    assert effective_strategy("live", "r", None, "candidate") == "live"


def test_none_is_returned_as_the_reserved_word() -> None:
    s = _section("## Verification\n- r: none — x\n")

    assert effective_strategy(None, "r", s, "candidate") == "none"


# ── is_post_merge ─────────────────────────────────────────────────────


def test_is_post_merge_follows_the_resolved_manifest(tmp_path: Path) -> None:
    assert is_post_merge("live", tmp_path) is True
    assert is_post_merge("candidate", tmp_path) is False


def test_none_and_no_strategy_are_neither_post_merge_nor_pre_merge(tmp_path: Path) -> None:
    assert is_post_merge("none", tmp_path) is False
    assert is_post_merge(None, tmp_path) is False


def test_a_repo_authored_post_merge_strategy_counts(tmp_path: Path) -> None:
    d = tmp_path / "docs/superpowers/verifications"
    d.mkdir(parents=True)
    (d / "staging.yaml").write_text(
        "verification: staging\nschema: 1\nwhen: post-merge\ndriver: operator\n"
    )

    assert is_post_merge("staging", tmp_path) is True


def test_an_unresolvable_name_raises(tmp_path: Path) -> None:
    with pytest.raises(StrategyError, match="ghost"):
        is_post_merge("ghost", tmp_path)
