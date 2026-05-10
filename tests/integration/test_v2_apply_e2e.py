"""End-to-end test: `vk apply --dry-run` against a fixture v2 plan."""

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
        "vk.commands.apply_cmd._make_gh_client",
        lambda: fake,
    )
    return fake


def test_vk_v2_apply_default_is_dry_run(fake_gh_factory):
    """vk apply <plan> (no flags) is a dry-run; emits a creation summary."""
    from vk.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    assert "create Issue" in result.output
    assert "phase 1" in result.output
    # Dry-run shows the "pass --yes" hint
    assert "--yes" in result.output
    # Dry-run still observes (read methods may be called) but must NOT
    # have invoked any mutating method.
    write_methods = {
        "create_issue",
        "edit_issue_labels",
        "edit_issue_state",
        "edit_issue_body",
        "ensure_labels",
    }
    called = {c[0] for c in fake_gh_factory.calls}
    assert called.isdisjoint(write_methods), f"unexpected writes: {called & write_methods}"


def test_vk_v2_apply_yes_actually_calls_gh(fake_gh_factory):
    """vk apply <plan> --yes actually mutates via the fake gh."""
    from vk.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(FIXTURE), "--yes"])
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
    monkeypatch.setattr("vk.commands.apply_cmd._make_gh_client", lambda: fake)

    runner = CliRunner()
    result = runner.invoke(app, ["apply", "--all"])
    assert result.exit_code == 0, result.output
    # Both plans should have been processed (each has plan: 2026-05-09-fixture-minimal)
    assert result.output.count("plan: 2026-05-09-fixture-minimal") == 2


def test_vk_v2_apply_rejects_both_arg_and_all(monkeypatch):
    """plan_dir + --all is a usage error."""
    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    monkeypatch.setattr("vk.commands.apply_cmd._make_gh_client", lambda: FakeGhClient())
    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(FIXTURE), "--all"])
    assert result.exit_code == 2


def test_vk_v2_apply_missing_args_exits_2(monkeypatch):
    """No plan_dir and no --all is a usage error."""
    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    monkeypatch.setattr("vk.commands.apply_cmd._make_gh_client", lambda: FakeGhClient())
    runner = CliRunner()
    result = runner.invoke(app, ["apply"])
    assert result.exit_code == 2


def test_vk_v2_apply_json_format(fake_gh_factory):
    """vk apply <plan> --format json emits parseable JSON."""
    import json

    from vk.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(FIXTURE), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is False  # default dry-run
    assert len(payload["plans"]) == 1
    plan_payload = payload["plans"][0]
    assert plan_payload["plan"] == "2026-05-09-fixture-minimal"
    kinds = [m["kind"] for m in plan_payload["mutations"]]
    assert "IssueCreate" in kinds


def test_vk_v2_apply_invalid_format(monkeypatch):
    """--format must be text or json."""
    from tests.unit.fakes import FakeGhClient
    from vk.cli import app

    monkeypatch.setattr("vk.commands.apply_cmd._make_gh_client", lambda: FakeGhClient())
    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(FIXTURE), "--format", "xml"])
    assert result.exit_code == 2
