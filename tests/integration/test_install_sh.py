"""Integration tests for scripts/install.sh.

Each test runs install.sh with a fake $HOME so nothing touches the real
user directory.  The VK MCP binary requirement is satisfied by a tiny
stub script.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """Set up a fake HOME with the minimal structure install.sh expects."""
    home = tmp_path / "home"
    home.mkdir()

    # Stub VK MCP binary — install.sh checks -x $HOME/bin/vibe-kanban-mcp
    vk_bin = home / "bin" / "vibe-kanban-mcp"
    vk_bin.parent.mkdir(parents=True)
    vk_bin.write_text("#!/bin/sh\necho stub\n")
    vk_bin.chmod(0o755)

    # Create .claude dir (install.sh expects $HOME/.claude to exist for some paths)
    (home / ".claude").mkdir()

    return home


def _run_install(
    fake_home: Path,
    *extra_args: str,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with fake HOME, skipping uv tool install."""
    env = {
        "HOME": str(fake_home),
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }
    result = subprocess.run(
        ["bash", str(INSTALL_SH), *extra_args],
        capture_output=True,
        text=True,
        env=env,
    )
    if not expect_fail:
        assert result.returncode == 0, (
            f"install.sh failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


# ── Install path ─────────────────────────────────────────────────────


class TestInstallSkillsAndRules:
    def test_installs_all_four_skills(self, fake_home: Path) -> None:
        _run_install(fake_home)

        skills_dir = fake_home / ".claude" / "skills"
        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            skill_file = skills_dir / name / "SKILL.md"
            assert skill_file.exists(), f"{name}/SKILL.md missing"
            assert skill_file.stat().st_size > 0

    def test_installs_rule_file(self, fake_home: Path) -> None:
        _run_install(fake_home)

        rule = fake_home / ".claude" / "rules" / "vk-plan-override.md"
        assert rule.exists()
        assert "vk-plan" in rule.read_text().lower()

    def test_replaces_stale_symlink_rule(self, fake_home: Path) -> None:
        """If the rule is a symlink to a removed target, install still succeeds."""
        rules_dir = fake_home / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        stale = rules_dir / "vk-plan-override.md"
        stale.symlink_to("/nonexistent/old/path")

        _run_install(fake_home)

        assert stale.exists()
        assert not stale.is_symlink()

    def test_idempotent(self, fake_home: Path) -> None:
        """Running install twice doesn't fail or corrupt anything."""
        _run_install(fake_home)
        _run_install(fake_home)

        skills_dir = fake_home / ".claude" / "skills"
        assert (skills_dir / "vk-plan" / "SKILL.md").exists()


# ── MCP config ───────────────────────────────────────────────────────


class TestMcpConfig:
    def test_creates_mcp_config_from_scratch(self, fake_home: Path) -> None:
        _run_install(fake_home)

        mcp = fake_home / ".claude" / ".mcp.json"
        assert mcp.exists()
        data = json.loads(mcp.read_text())
        vk = data["mcpServers"]["vibe_kanban"]
        assert vk["command"] == str(fake_home / "bin" / "vibe-kanban-mcp")
        assert vk["args"] == ["--mode", "global"]
        assert vk["env"]["VIBE_BACKEND_URL"] == "http://localhost:8081"

    def test_preserves_existing_mcp_servers(self, fake_home: Path) -> None:
        """Installing should not clobber other MCP servers in .mcp.json."""
        mcp = fake_home / ".claude" / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "other-server": {"command": "other", "args": []}
            }
        }))

        _run_install(fake_home)

        data = json.loads(mcp.read_text())
        assert "other-server" in data["mcpServers"]
        assert "vibe_kanban" in data["mcpServers"]

    def test_updates_existing_vk_entry(self, fake_home: Path) -> None:
        """If vibe_kanban already exists, it gets overwritten with current config."""
        mcp = fake_home / ".claude" / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "vibe_kanban": {"command": "/old/path", "args": []}
            }
        }))

        _run_install(fake_home)

        data = json.loads(mcp.read_text())
        assert data["mcpServers"]["vibe_kanban"]["command"] == str(
            fake_home / "bin" / "vibe-kanban-mcp"
        )


# ── Fail fast ────────────────────────────────────────────────────────


class TestFailFast:
    def test_fails_without_mcp_binary(self, tmp_path: Path) -> None:
        """Install must fail if vibe-kanban-mcp binary is missing."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()
        # No bin/vibe-kanban-mcp

        result = _run_install(home, expect_fail=True)

        assert result.returncode != 0
        assert "ERROR" in result.stderr or "not found" in result.stderr

    def test_fails_if_binary_not_executable(self, tmp_path: Path) -> None:
        """A non-executable binary should also trigger the fail-fast."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()
        vk_bin = home / "bin" / "vibe-kanban-mcp"
        vk_bin.parent.mkdir(parents=True)
        vk_bin.write_text("not executable")
        vk_bin.chmod(0o644)

        result = _run_install(home, expect_fail=True)

        assert result.returncode != 0


# ── Uninstall path ───────────────────────────────────────────────────


class TestUninstall:
    def test_removes_skills_and_rules(self, fake_home: Path) -> None:
        _run_install(fake_home)
        _run_install(fake_home, "--uninstall")

        skills_dir = fake_home / ".claude" / "skills"
        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            assert not (skills_dir / name).exists()

        assert not (fake_home / ".claude" / "rules" / "vk-plan-override.md").exists()

    def test_removes_vk_from_mcp_config(self, fake_home: Path) -> None:
        _run_install(fake_home)
        _run_install(fake_home, "--uninstall")

        mcp = fake_home / ".claude" / ".mcp.json"
        assert mcp.exists()
        data = json.loads(mcp.read_text())
        assert "vibe_kanban" not in data["mcpServers"]

    def test_preserves_other_mcp_servers_on_uninstall(self, fake_home: Path) -> None:
        """Uninstall should only remove vibe_kanban, not other servers."""
        mcp = fake_home / ".claude" / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "other-server": {"command": "other", "args": []},
                "vibe_kanban": {"command": "/old", "args": []}
            }
        }))

        _run_install(fake_home, "--uninstall")

        data = json.loads(mcp.read_text())
        assert "other-server" in data["mcpServers"]
        assert "vibe_kanban" not in data["mcpServers"]

    def test_uninstall_idempotent(self, fake_home: Path) -> None:
        """Uninstalling when nothing is installed should not fail."""
        result = _run_install(fake_home, "--uninstall")
        assert result.returncode == 0


# ── Marketplace cleanup ──────────────────────────────────────────────


class TestMarketplaceCleanup:
    def test_removes_marketplace_duplicates(self, fake_home: Path) -> None:
        mp_dir = (
            fake_home / ".claude" / "plugins" / "marketplaces" / "derio-net" / "skills"
        )
        mp_dir.mkdir(parents=True)
        for name in ("vk-plan", "vk-dispatch"):
            d = mp_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text("stale")

        _run_install(fake_home)

        assert not (mp_dir / "vk-plan").exists()
        assert not (mp_dir / "vk-dispatch").exists()

    def test_preserves_unrelated_marketplace_skills(self, fake_home: Path) -> None:
        mp_dir = (
            fake_home / ".claude" / "plugins" / "marketplaces" / "derio-net" / "skills"
        )
        mp_dir.mkdir(parents=True)
        other = mp_dir / "some-other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep me")

        _run_install(fake_home)

        assert other.exists()
