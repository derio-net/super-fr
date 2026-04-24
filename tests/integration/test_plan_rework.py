"""Integration tests for ``vk plan rework <parent>``."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _setup_repo(tmp_path: Path, parent_fixture: str, *, archived: bool = True) -> Path:
    """Build a minimal repo with a parent plan in plans/ or archived-plans/."""
    target_dir = tmp_path / (
        "docs/superpowers/archived-plans" if archived else "docs/superpowers/plans"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    parent_dest = target_dir / "2026-04-08-kid-laptops-5-parental-controls.md"
    shutil.copy(FIXTURES / parent_fixture, parent_dest)
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True, exist_ok=True)
    return parent_dest


def test_rework_archived_parent_happy_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework", str(parent)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out_path = (
        tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    )
    assert out_path.exists()
    text = out_path.read_text()
    assert "# Kid Laptops Plan 5 — Rework 1" in text
    assert "**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`" in text
    assert "(merged + archived)" in text
    assert "## Origin" in text


def test_rework_missing_parent_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework", str(tmp_path / "nope.md")],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "parent plan not found" in result.stderr


def test_rework_parent_outside_plans_dirs_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    rogue = tmp_path / "not-a-plan-dir" / "2026-04-08-foo.md"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("# Foo\n**Status:** Complete\n**Goal:** g\n")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework", str(rogue)], catch_exceptions=False)
    assert result.exit_code == 2
    assert "must live in docs/superpowers/plans/" in result.stderr


def test_rework_unarchived_parent_warns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md", archived=False)
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework", str(parent)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "not yet archived" in result.stderr
    out = tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    assert out.exists()
    text = out.read_text()
    assert "(not yet archived)" in text


def test_rework_chains_prior_rework(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md")
    # Seed an archived rework-1.
    (
        tmp_path
        / "docs/superpowers/archived-plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    ).write_text("# Stub — Rework 1\n**Status:** Complete\n**Goal:** done.\n")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework", str(parent)], catch_exceptions=False)
    assert result.exit_code == 0
    out = tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-2.md"
    assert out.exists()
    assert "# Kid Laptops Plan 5 — Rework 2" in out.read_text()
    assert (
        "**Prior rework:** `docs/superpowers/archived-plans/"
        "2026-04-08-kid-laptops-5-parental-controls-rework-1.md`"
    ) in out.read_text()


def test_rework_cross_dir_collision_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md")
    slug = "2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    (tmp_path / "docs/superpowers/plans" / slug).write_text("# x\n")
    (tmp_path / "docs/superpowers/archived-plans" / slug).write_text("# x\n")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework", str(parent)], catch_exceptions=False)
    assert result.exit_code == 2
    assert "ambiguous rework state" in result.stderr


def test_rework_no_h1_title_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    target_dir = tmp_path / "docs/superpowers/archived-plans"
    target_dir.mkdir(parents=True)
    parent = target_dir / "2026-04-08-no-title.md"
    parent.write_text("**Status:** Complete\n\n**Goal:** g\n")
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework", str(parent)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "no H1 title" in result.stderr
    out_text = (tmp_path / "docs/superpowers/plans/2026-04-08-no-title-rework-1.md").read_text()
    assert out_text.startswith("# Rework 1 for 2026-04-08-no-title\n")
