"""`settle.` lines in a spec's `## Verification` section (spec 2026-11-23-pr-readiness-wait
R6, Test Plan 6)."""

from __future__ import annotations

import pytest
from fr.verification.effective import effective_strategy
from fr.verification.spec_section import (
    SectionError,
    SettleOverride,
    parse_section,
    settle_overrides,
)


def _spec(*lines: str) -> str:
    body = "\n".join(lines)
    return f"# T\n\n## Verification\n\n{body}\n\n## Test Plan\n\n1. x\n"


def test_settle_lines_parse_into_the_section() -> None:
    s = parse_section(
        _spec(
            "strategy: candidate",
            "- row-a: none — unit tests",
            "settle.ci: report — the suite is flaky on the forge this week",
            "settle.conflicts: off — the base is frozen",
        )
    )

    assert s is not None
    assert s.settle == {
        "ci": SettleOverride("report", "the suite is flaky on the forge this week"),
        "conflicts": SettleOverride("off", "the base is frozen"),
    }
    assert s.strategy == "candidate"
    assert "row-a" in s.rows


def test_a_section_holding_only_settle_lines_is_no_verification_section() -> None:
    """Review p2-r6: settle lines change no strategy, gate or walk; only the override
    reader sees them."""
    text = _spec("Prose.", "", "settle.ci: fix — re-enable after the override")

    assert parse_section(text) is None
    assert settle_overrides(text) == {"ci": SettleOverride("fix", "re-enable after the override")}


@pytest.mark.parametrize(
    "before",
    [
        "# T\n\n## Test Plan\n\n1. x\n",
        "# T\n\n## Verification\n\nProse only.\n\n## Test Plan\n\n1. x\n",
    ],
)
def test_adding_a_settle_line_changes_no_strategy(before: str) -> None:
    if "## Verification" in before:
        after = before.replace("Prose only.\n", "Prose only.\n\nsettle.ci: report — r\n")
    else:
        after = before.replace(
            "## Test Plan", "## Verification\n\nsettle.ci: report — r\n\n## Test Plan"
        )

    for text in (before, after):
        section = parse_section(text)
        assert section is None
        assert effective_strategy(None, "row-a", section, "candidate") is None
    assert settle_overrides(after) == {"ci": SettleOverride("report", "r")}
    assert settle_overrides(before) == {}


def test_a_mixed_section_keeps_its_settle_lines() -> None:
    text = _spec("strategy: candidate", "settle.conflicts: off — frozen base")

    section = parse_section(text)
    assert section is not None and section.settle == {
        "conflicts": SettleOverride("off", "frozen base")
    }
    assert settle_overrides(text) == section.settle


@pytest.mark.parametrize(
    "line",
    [
        "settle.ci: report",
        "settle.ci: report —",
        "settle.ci: report — ",
        "settle.foo: report — a reason",
        "settle.ci: maybe — a reason",
        "settle.ci report — a reason",
        "settle.: fix — a reason",
    ],
)
def test_a_malformed_settle_line_is_an_error_naming_the_line(line: str) -> None:
    for read in (parse_section, settle_overrides):
        with pytest.raises(SectionError) as e:
            read(_spec("strategy: candidate", line))

        assert "line 6" in str(e.value)
        assert line.strip() in str(e.value)


def test_a_malformed_settle_line_alone_is_still_an_override_error() -> None:
    with pytest.raises(SectionError, match="line 5"):
        settle_overrides(_spec("settle.ci: report"))


def test_a_key_given_twice_is_an_error() -> None:
    with pytest.raises(SectionError, match="line 6"):
        settle_overrides(_spec("settle.ci: report — one", "settle.ci: off — two"))


def test_sections_without_settle_lines_parse_unchanged() -> None:
    s = parse_section(_spec("strategy: candidate", "- row-a: live — needs a pane", "gate: tester"))

    assert s is not None
    assert s.settle == {}
    assert s.gate == "tester"
    assert s.rows["row-a"].reason == "needs a pane"


def test_a_prose_only_section_is_still_none() -> None:
    assert parse_section(_spec("Some prose about settle. timing.")) is None


def test_the_grammar_modes_are_the_settings_modes() -> None:
    from fr.settings.model import SETTLE_MODES
    from fr.verification.spec_section import SETTLE_OVERRIDE_MODES

    assert SETTLE_OVERRIDE_MODES == SETTLE_MODES
