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


def test_pickup_still_enforces_fr_version(monkeypatch, tmp_path):
    """Phase 8 (spec §3.E.1): `fr pickup` is an execution path — it must
    keep enforcing the `fr_version` gate. `enforce_fr_version=False` is
    reserved for the read-only spec-status path (`fr.spec.compute_status`)
    only. Uses a fixture whose ceiling genuinely excludes the installed
    version (monkeypatched `INSTALLED_FR_VERSION`), not one that happens to
    admit it."""
    import shutil

    from fr.cli import app

    plan_dir = tmp_path / "plan"
    shutil.copytree(FIXTURE, plan_dir)
    meta = (plan_dir / "_meta.yaml").read_text()
    (plan_dir / "_meta.yaml").write_text(meta + 'fr_version: ">=9.0.0,<10.0.0"\n')

    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "3.0.0")

    runner = CliRunner()
    result = runner.invoke(app, ["pickup", str(plan_dir), "--phase", "1"])
    assert result.exit_code == 2, result.output
    output = " ".join(result.output.split())  # rich soft-wraps; normalize before matching
    assert "requires fr_version" in output


def test_pickup_includes_dependency_reminder():
    from fr.cli import app

    multi = FIXTURE.parent / "v2_plan_multi_phase"
    runner = CliRunner()
    result = runner.invoke(app, ["pickup", str(multi), "--phase", "10"])
    assert result.exit_code == 0, result.output
    # Phase 10 in multi_phase fixture depends_on=[2]
    assert "Depends on" in result.output
    assert "2" in result.output
