"""End-to-end test: `vk v2 apply --dry-run` against a fixture v2 plan."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

FIXTURE = Path(__file__).parent.parent / "unit" / "fixtures" / "v2_plan_minimal"


@pytest.fixture()
def fake_gh_factory(monkeypatch):
    """Patch `_make_gh_client` to return a FakeGhClient."""
    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(
        "vk.v2.commands.apply_cmd._make_gh_client",
        lambda: fake,
    )
    return fake


def test_vk_v2_apply_dry_run_shows_create_intent(fake_gh_factory):
    """vk v2 apply --dry-run on the fixture plan emits a creation summary."""
    from vk.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["v2", "apply", str(FIXTURE), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "create Issue" in result.output
    assert "phase 1" in result.output
    # Dry-run must NOT have called gh
    assert fake_gh_factory.calls == []


def test_vk_v2_apply_without_dry_run_calls_gh(fake_gh_factory):
    """vk v2 apply <plan> (no --dry-run) actually mutates via the fake gh."""
    from vk.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["v2", "apply", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    # Should have created at least the Issue + ensured labels
    methods = [c[0] for c in fake_gh_factory.calls]
    assert "ensure_labels" in methods
    assert "create_issue" in methods


def test_vk_v2_apply_all_walks_plans_dir(tmp_path, monkeypatch):
    """--all globs plans/ folders and applies each (dry-run)."""
    import shutil

    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    # Build a tmp repo-shaped tree with two plan folders
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    shutil.copytree(FIXTURE, plans / "first")
    shutil.copytree(FIXTURE, plans / "second")
    monkeypatch.chdir(tmp_path)

    fake = FakeGhClient()
    monkeypatch.setattr("vk.v2.commands.apply_cmd._make_gh_client", lambda: fake)

    runner = CliRunner()
    result = runner.invoke(app, ["v2", "apply", "--all", "--dry-run"])
    assert result.exit_code == 0, result.output
    # Both plans should have been processed (each has plan: 2026-05-09-fixture-minimal)
    assert result.output.count("plan: 2026-05-09-fixture-minimal") == 2


def test_vk_v2_apply_rejects_both_arg_and_all(monkeypatch):
    """plan_dir + --all is a usage error."""
    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    monkeypatch.setattr("vk.v2.commands.apply_cmd._make_gh_client", lambda: FakeGhClient())
    runner = CliRunner()
    result = runner.invoke(app, ["v2", "apply", str(FIXTURE), "--all", "--dry-run"])
    assert result.exit_code == 2


def test_vk_v2_apply_missing_args_exits_2(monkeypatch):
    """No plan_dir and no --all is a usage error."""
    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    monkeypatch.setattr("vk.v2.commands.apply_cmd._make_gh_client", lambda: FakeGhClient())
    runner = CliRunner()
    result = runner.invoke(app, ["v2", "apply", "--dry-run"])
    assert result.exit_code == 2
