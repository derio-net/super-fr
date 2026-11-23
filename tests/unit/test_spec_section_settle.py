"""`settle.` lines in a spec's `## Verification` section (spec 2026-11-23-pr-readiness-wait
R6, Test Plan 6)."""

from __future__ import annotations

import pytest
from fr.verification.spec_section import SectionError, SettleOverride, parse_section


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


def test_a_section_holding_only_settle_lines_is_a_grammar_section() -> None:
    s = parse_section(_spec("Prose.", "", "settle.ci: fix — re-enable after the override"))

    assert s is not None
    assert s.settle == {"ci": SettleOverride("fix", "re-enable after the override")}
    assert s.strategy is None
    assert s.rows == {}


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
    with pytest.raises(SectionError) as e:
        parse_section(_spec("strategy: candidate", line))

    assert "line 6" in str(e.value)
    assert line.strip() in str(e.value)


def test_a_key_given_twice_is_an_error() -> None:
    with pytest.raises(SectionError, match="line 6"):
        parse_section(_spec("settle.ci: report — one", "settle.ci: off — two"))


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
