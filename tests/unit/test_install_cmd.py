"""Tests for vk install-skills command."""

from __future__ import annotations

from pathlib import Path

import pytest

from vk.commands.install_cmd import _clean_marketplace_skills, _install_rules, install_skills


@pytest.fixture
def skills_src(tmp_path: Path) -> Path:
    """Create a fake skills source directory with two skills."""
    src = tmp_path / "skills"
    src.mkdir()
    for name in ("vk-plan", "vk-dispatch"):
        d = src / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {name}")
    # A non-skill directory (no SKILL.md) — should be ignored
    (src / "not-a-skill").mkdir()
    return src


@pytest.fixture
def marketplace_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake marketplace skills directory and patch Path.home()."""
    fake_home = tmp_path / "home"
    mp = fake_home / ".claude" / "plugins" / "marketplaces" / "derio-net" / "skills"
    mp.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    return mp


class TestCleanMarketplaceSkills:
    def test_removes_matching_marketplace_copies(self, skills_src: Path, marketplace_dir: Path):
        # Plant marketplace duplicates
        for name in ("vk-plan", "vk-dispatch"):
            d = marketplace_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text("old content")

        _clean_marketplace_skills(skills_src)

        assert not (marketplace_dir / "vk-plan").exists()
        assert not (marketplace_dir / "vk-dispatch").exists()

    def test_ignores_non_matching_marketplace_skills(self, skills_src: Path, marketplace_dir: Path):
        # A marketplace skill that doesn't match any source skill
        other = marketplace_dir / "some-other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep me")

        _clean_marketplace_skills(skills_src)

        assert other.exists()

    def test_noop_when_marketplace_dir_missing(
        self, skills_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "empty_home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        # Should not raise
        _clean_marketplace_skills(skills_src)

    def test_skips_non_skill_source_dirs(self, skills_src: Path, marketplace_dir: Path):
        # Plant a marketplace dir matching the non-skill source dir
        other = marketplace_dir / "not-a-skill"
        other.mkdir()
        (other / "readme.txt").write_text("hi")

        _clean_marketplace_skills(skills_src)

        # Should still exist — source has no SKILL.md so it's not considered
        assert other.exists()


class TestInstallSkills:
    def test_creates_symlinks(
        self, skills_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_skills_dir", lambda: skills_src)

        install_skills(copy=False)

        claude_skills = fake_home / ".claude" / "skills"
        for name in ("vk-plan", "vk-dispatch"):
            target = claude_skills / name
            assert target.is_symlink()
            assert target.resolve() == (skills_src / name).resolve()

    def test_creates_copies(
        self, skills_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_skills_dir", lambda: skills_src)

        install_skills(copy=True)

        claude_skills = fake_home / ".claude" / "skills"
        for name in ("vk-plan", "vk-dispatch"):
            target = claude_skills / name
            assert target.is_dir()
            assert not target.is_symlink()
            assert (target / "SKILL.md").read_text() == f"# {name}"

    def test_replaces_existing_symlink(
        self, skills_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        claude_skills = fake_home / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        # Plant a stale symlink
        stale_target = tmp_path / "old"
        stale_target.mkdir()
        (claude_skills / "vk-plan").symlink_to(stale_target)

        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_skills_dir", lambda: skills_src)

        install_skills(copy=False)

        target = claude_skills / "vk-plan"
        assert target.is_symlink()
        assert target.resolve() == (skills_src / "vk-plan").resolve()

    def test_replaces_existing_directory(
        self, skills_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        claude_skills = fake_home / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        # Plant an old directory copy
        old = claude_skills / "vk-plan"
        old.mkdir()
        (old / "SKILL.md").write_text("old")

        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_skills_dir", lambda: skills_src)

        install_skills(copy=False)

        target = claude_skills / "vk-plan"
        assert target.is_symlink()

    def test_cleans_marketplace_during_install(
        self, skills_src: Path, marketplace_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Plant marketplace duplicate
        dup = marketplace_dir / "vk-plan"
        dup.mkdir()
        (dup / "SKILL.md").write_text("stale")

        monkeypatch.setattr("vk.commands.install_cmd._find_skills_dir", lambda: skills_src)

        install_skills(copy=False)

        assert not dup.exists()


class TestInstallRules:
    @pytest.fixture
    def rules_src(self, tmp_path: Path) -> Path:
        """Create a fake rules source directory."""
        src = tmp_path / "rules"
        src.mkdir()
        (src / "vk-plan-override.md").write_text("## Plan Override\nUse vk-plan.")
        (src / "another-rule.md").write_text("## Another Rule")
        return src

    def test_creates_symlinks(
        self, rules_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_rules_dir", lambda: rules_src)

        count = _install_rules(copy=False)

        claude_rules = fake_home / ".claude" / "rules"
        assert count == 2
        for name in ("vk-plan-override.md", "another-rule.md"):
            target = claude_rules / name
            assert target.is_symlink()
            assert target.resolve() == (rules_src / name).resolve()

    def test_creates_copies(self, rules_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_rules_dir", lambda: rules_src)

        count = _install_rules(copy=True)

        claude_rules = fake_home / ".claude" / "rules"
        assert count == 2
        target = claude_rules / "vk-plan-override.md"
        assert not target.is_symlink()
        assert "Plan Override" in target.read_text()

    def test_replaces_existing_rule(
        self, rules_src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        claude_rules = fake_home / ".claude" / "rules"
        claude_rules.mkdir(parents=True)
        (claude_rules / "vk-plan-override.md").write_text("old content")

        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr("vk.commands.install_cmd._find_rules_dir", lambda: rules_src)

        _install_rules(copy=False)

        target = claude_rules / "vk-plan-override.md"
        assert target.is_symlink()

    def test_noop_when_no_rules_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("vk.commands.install_cmd._find_rules_dir", lambda: None)

        count = _install_rules(copy=False)
        assert count == 0
