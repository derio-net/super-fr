"""Integration tests for ``vk plan rework-list``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _seed_rework(tmp_path: Path, fixture: str, filename: str, archived: bool = False) -> Path:
    dir_ = tmp_path / ("docs/superpowers/archived-plans" if archived else "docs/superpowers/plans")
    dir_.mkdir(parents=True, exist_ok=True)
    dest = dir_ / filename
    shutil.copy(FIXTURES / fixture, dest)
    return dest


def test_rework_list_empty_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    # Rich table always prints column headers, even on zero data rows.
    assert "parent-slug" in result.stdout


def test_rework_list_two_active_reworks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "foo" in result.stdout
    assert "bar" in result.stdout


def test_rework_list_include_archived(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md", archived=True)
    runner = CliRunner()
    without = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    with_archived = runner.invoke(
        app, ["plan", "rework-list", "--include-archived"], catch_exceptions=False
    )
    assert "foo" not in without.stdout
    assert "foo" in with_archived.stdout


def test_rework_list_status_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")  # In Progress
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")  # Not Started
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework-list", "--status", "in progress"], catch_exceptions=False
    )
    assert "foo" in result.stdout
    assert "bar" not in result.stdout


def test_rework_list_track_substring_matches_transition(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework-list", "--track", "decision"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert "foo" in result.stdout


def test_rework_list_plan_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--plan", "foo"], catch_exceptions=False)
    assert "foo" in result.stdout
    assert "bar" not in result.stdout


def test_rework_list_json_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["parent_slug"] == "foo"
    assert data[0]["rework_number"] == 1
    assert data[0]["origin_items"] == 3
    assert set(data[0]["by_track"].keys()) == {"development", "operations", "decision"}


def test_rework_list_skips_malformed_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md")
    (tmp_path / "docs/superpowers/plans/2026-04-08-bar-rework-1.md").write_text("not a plan at all")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "foo" in result.stdout
    assert "warn" in result.stderr or "skipping" in result.stderr
