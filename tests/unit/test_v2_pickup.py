"""`fr pickup` tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_pickup_emits_phase_title_and_pr_template():
    from fr.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["pickup", str(FIXTURE), "--phase", "1"])
    assert result.exit_code == 0, result.output
    assert "Phase 1/1" in result.output
    assert "Fixture phase" in result.output
    assert "[agentic]" in result.output
    # PR title template
    assert "[derio-net/superpowers-for-vk] 2026-05-09-fixture-minimal · Phase 1/1" in result.output
    # All step text rendered
    assert "P1.T1.S1" in result.output
    assert "Fixture step" in result.output
    # Pointer to prose
    assert "_prose.md" in result.output


def test_pickup_unknown_phase_exits_2():
    from fr.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["pickup", str(FIXTURE), "--phase", "99"])
    assert result.exit_code == 2
    assert "not found" in result.output.lower() or "not found" in (result.stderr or "").lower()


def test_pickup_includes_dependency_reminder():
    from fr.cli import app

    multi = FIXTURE.parent / "v2_plan_multi_phase"
    runner = CliRunner()
    result = runner.invoke(app, ["pickup", str(multi), "--phase", "10"])
    assert result.exit_code == 0, result.output
    # Phase 10 in multi_phase fixture depends_on=[2]
    assert "Depends on" in result.output
    assert "2" in result.output
