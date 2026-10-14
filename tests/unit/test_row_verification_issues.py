"""`row_verification_issues` runs with or without a `## Verification` section
(spec 2026-10-14 exit-gates R24, gh#1155): a row's own `verify:` is checked even
when the spec has no section, by `fr plan self-review` and by the brainstorm
warning alike."""

from __future__ import annotations

from pathlib import Path

from fr.commands.run_cmd import _unrunnable_spec_warnings

from tests.unit.requirements_support import row, write_matrix
from tests.unit.test_plan_self_review_verification import _row, _setup

SPEC = "docs/spec.md"


def test_a_sectionless_row_with_live_and_no_reason_asks_for_a_section(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, None, [_row("a", "    verify: live\n")])

    assert "`a`" in msg and "live" in msg and "reason" in msg
    assert "## Verification" in msg
    assert "every other row" in msg and "strategy:" in msg


def test_a_sectionless_none_row_without_reason_is_flagged(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, None, [_row("a", "    verify: none\n")])

    assert "`a`" in msg and "none" in msg and "## Verification" in msg


def test_a_sectionless_unresolvable_verify_is_flagged(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, None, [_row("a", "    verify: no-such-thing\n")])

    assert "`a`" in msg and "no-such-thing" in msg


def test_a_sectionless_unrunnable_install_is_flagged(tmp_path: Path) -> None:
    (msg,) = _setup(
        tmp_path, None, [_row("a", "    verify: candidate\n    scenario: s.sh\n")], install=False
    )

    assert ".fr/candidate-install" in msg


def test_a_sectionless_agent_row_without_a_scenario_is_flagged(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, None, [_row("a", "    verify: candidate\n")])

    assert "`a`" in msg and "scenario" in msg


def test_a_sectionless_spec_with_no_row_verify_passes(tmp_path: Path) -> None:
    assert _setup(tmp_path, None, [_row("a"), _row("b")]) == []


def test_the_brainstorm_warning_prints_all_four_kinds(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / SPEC).write_text("# Spec\n\n## Requirements\n\nR1. x\n")
    write_matrix(
        tmp_path,
        [
            row(SPEC, rid="r-reason", verify="live"),
            row(SPEC, rid="r-unknown", verify="no-such-thing"),
            row(SPEC, rid="r-install", verify="candidate"),  # no install program, no scenario
        ],
    )

    text = "\n".join(_unrunnable_spec_warnings(tmp_path, SPEC))

    assert "r-reason" in text and "reason" in text  # missing reason
    assert "no-such-thing" in text  # unresolvable
    assert ".fr/candidate-install" in text  # unrunnable install
    assert "r-install" in text and "scenario" in text  # missing scenario


def test_the_brainstorm_warning_is_empty_for_a_clean_sectionless_spec(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / SPEC).write_text("# Spec\n")
    write_matrix(tmp_path, [row(SPEC, rid="r-plain")])

    assert _unrunnable_spec_warnings(tmp_path, SPEC) == []
