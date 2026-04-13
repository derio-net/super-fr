"""Tests for vk install-skills command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vk.commands.install_cmd import (
    _clean_stale_skills,
    _clear_stale_cache,
    _install_rules,
    _pull_marketplace,
)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a fake home with the expected directory structure."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    # Patch module-level constants that use Path.home()
    claude_dir = home / ".claude"
    monkeypatch.setattr("vk.commands.install_cmd.CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(
        "vk.commands.install_cmd.MARKETPLACE_DIR",
        claude_dir / "plugins" / "marketplaces" / "derio-net",
    )
    monkeypatch.setattr(
        "vk.commands.install_cmd.CACHE_DIR",
        claude_dir / "plugins" / "cache" / "derio-net" / "superpowers-for-vk",
    )
    return home


class TestCleanStaleSkills:
    def test_removes_skill_directories(self, fake_home: Path):
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            d = skills_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"# {name}")

        _clean_stale_skills()

        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            assert not (skills_dir / name).exists()

    def test_removes_symlinks(self, fake_home: Path, tmp_path: Path):
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        target = tmp_path / "real-skill"
        target.mkdir()
        (skills_dir / "vk-plan").symlink_to(target)

        _clean_stale_skills()

        assert not (skills_dir / "vk-plan").exists()

    def test_leaves_non_vk_skills(self, fake_home: Path):
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        other = skills_dir / "some-other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep me")

        _clean_stale_skills()

        assert other.exists()

    def test_noop_when_no_skills_dir(self, fake_home: Path):
        # Should not raise
        _clean_stale_skills()


class TestClearStaleCache:
    def test_removes_old_version_keeps_current(self, fake_home: Path):
        cache_dir = fake_home / ".claude" / "plugins" / "cache" / "derio-net" / "superpowers-for-vk"
        (cache_dir / "0.2.1").mkdir(parents=True)
        (cache_dir / "1.0.4").mkdir(parents=True)

        # Set up marketplace manifest pointing to 1.0.4
        mp_dir = fake_home / ".claude" / "plugins" / "marketplaces" / "derio-net" / ".claude-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps({"plugins": [{"name": "superpowers-for-vk", "version": "1.0.4"}]})
        )

        _clear_stale_cache()

        assert not (cache_dir / "0.2.1").exists()
        assert (cache_dir / "1.0.4").exists()

    def test_noop_when_no_cache(self, fake_home: Path):
        # Should not raise
        _clear_stale_cache()


class TestInstallRules:
    def test_copies_rules(self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        rules_src = tmp_path / "rules"
        rules_src.mkdir()
        (rules_src / "vk-plan-override.md").write_text("## Plan Override")

        monkeypatch.setattr("vk.commands.install_cmd._repo_root", lambda: tmp_path)

        count = _install_rules()

        target = fake_home / ".claude" / "rules" / "vk-plan-override.md"
        assert count == 1
        assert target.exists()
        assert not target.is_symlink()
        assert "Plan Override" in target.read_text()

    def test_replaces_existing_rule(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        claude_rules = fake_home / ".claude" / "rules"
        claude_rules.mkdir(parents=True)
        (claude_rules / "vk-plan-override.md").write_text("old")

        rules_src = tmp_path / "rules"
        rules_src.mkdir()
        (rules_src / "vk-plan-override.md").write_text("new")

        monkeypatch.setattr("vk.commands.install_cmd._repo_root", lambda: tmp_path)

        _install_rules()

        assert (claude_rules / "vk-plan-override.md").read_text() == "new"

    def test_replaces_symlink_with_copy(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        claude_rules = fake_home / ".claude" / "rules"
        claude_rules.mkdir(parents=True)
        old_target = tmp_path / "old-rule.md"
        old_target.write_text("old")
        (claude_rules / "vk-plan-override.md").symlink_to(old_target)

        rules_src = tmp_path / "rules"
        rules_src.mkdir()
        (rules_src / "vk-plan-override.md").write_text("new")

        monkeypatch.setattr("vk.commands.install_cmd._repo_root", lambda: tmp_path)

        _install_rules()

        target = claude_rules / "vk-plan-override.md"
        assert not target.is_symlink()
        assert target.read_text() == "new"

    def test_noop_when_no_rules_dir(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vk.commands.install_cmd._repo_root", lambda: tmp_path / "nowhere")

        count = _install_rules()
        assert count == 0


class TestPullMarketplace:
    def test_noop_when_no_git_dir(self, fake_home: Path):
        # Should not raise when marketplace dir doesn't exist
        _pull_marketplace()
