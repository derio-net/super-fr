"""Integration tests for scripts/install.sh.

Each test runs install.sh with a fake $HOME so nothing touches the real
user directory.  The VK MCP binary requirement is satisfied by a tiny
stub script.

Skills are delivered by the plugin system (enabledPlugins), not by
install.sh.  install.sh handles: MCP config, rules, vk CLI, stale
skill cleanup, and PostToolUse hook hint.
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

    # Create .claude dir
    (home / ".claude").mkdir()

    return home


def _run_install(
    fake_home: Path,
    *extra_args: str,
    expect_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with fake HOME, stubbing uv so step 10 is a no-op."""
    # install.sh preflights `uv` on PATH. setup-uv@v4 on CI installs it to
    # $HOME/.local/bin, which isn't in the hermetic PATH below. Drop an
    # executable stub in $HOME/bin so the preflight passes and step 10's
    # `uv tool install` no-ops instead of polluting the runner's real uv.
    bin_dir = fake_home / "bin"
    bin_dir.mkdir(exist_ok=True)
    uv_stub = bin_dir / "uv"
    if not uv_stub.exists():
        uv_stub.write_text("#!/bin/sh\nexit 0\n")
        uv_stub.chmod(0o755)

    env = {
        "HOME": str(fake_home),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        # Bypass the main/clean/in-sync gate: integration tests run install.sh
        # from the repo checkout (often detached HEAD on CI), which would
        # always fail the gate. The escape hatch is documented in install.sh.
        "VK_INSTALL_SKIP_PREFLIGHT": "1",
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


# ── Rules ────────────────────────────────────────────────────────────


class TestInstallRules:
    def test_installs_rule_file(self, fake_home: Path) -> None:
        _run_install(fake_home)

        rule = fake_home / ".claude" / "rules" / "fr-plan-override.md"
        assert rule.exists()
        assert "fr-plan" in rule.read_text().lower()

    def test_replaces_stale_symlink_rule(self, fake_home: Path) -> None:
        """If the rule is a symlink to a removed target, install still succeeds."""
        rules_dir = fake_home / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        stale = rules_dir / "fr-plan-override.md"
        stale.symlink_to("/nonexistent/old/path")

        _run_install(fake_home)

        assert stale.exists()
        assert not stale.is_symlink()

    def test_idempotent(self, fake_home: Path) -> None:
        """Running install twice doesn't fail or corrupt anything."""
        _run_install(fake_home)
        _run_install(fake_home)

        assert (fake_home / ".claude" / "rules" / "fr-plan-override.md").exists()


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
        mcp.write_text(
            json.dumps({"mcpServers": {"other-server": {"command": "other", "args": []}}})
        )

        _run_install(fake_home)

        data = json.loads(mcp.read_text())
        assert "other-server" in data["mcpServers"]
        assert "vibe_kanban" in data["mcpServers"]

    def test_updates_existing_vk_entry(self, fake_home: Path) -> None:
        """If vibe_kanban already exists, it gets overwritten with current config."""
        mcp = fake_home / ".claude" / ".mcp.json"
        mcp.write_text(
            json.dumps({"mcpServers": {"vibe_kanban": {"command": "/old/path", "args": []}}})
        )

        _run_install(fake_home)

        data = json.loads(mcp.read_text())
        assert data["mcpServers"]["vibe_kanban"]["command"] == str(
            fake_home / "bin" / "vibe-kanban-mcp"
        )


# ── Stale skill cleanup ─────────────────────────────────────────────


class TestStaleSkillCleanup:
    def test_removes_user_level_skill_copies(self, fake_home: Path) -> None:
        """install.sh should clean up skills from older install.sh versions."""
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            d = skills_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text("stale")

        _run_install(fake_home)

        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            assert not (skills_dir / name).exists()

    def test_preserves_non_vk_skills(self, fake_home: Path) -> None:
        """Other user-level skills should not be touched."""
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        other = skills_dir / "my-custom-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep me")

        _run_install(fake_home)

        assert other.exists()

    def test_removes_dangling_symlinks(self, fake_home: Path) -> None:
        """install.sh should clean up dangling symlinks from VK worktree installs."""
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            (skills_dir / name).symlink_to("/nonexistent/vk-worktree/skills/" + name)

        _run_install(fake_home)

        for name in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
            assert not (skills_dir / name).exists(), f"Dangling symlink {name} was not removed"

    def test_no_error_when_no_stale_skills(self, fake_home: Path) -> None:
        """Should not fail when there are no stale skills to clean."""
        _run_install(fake_home)  # no skills dir pre-existing


# ── Missing binary graceful degradation ──────────────────────────────


class TestMissingBinary:
    def test_warns_without_mcp_binary(self, tmp_path: Path) -> None:
        """Missing binary emits a WARNING (not ERROR) and doesn't abort early."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()

        result = _run_install(home, expect_fail=True)

        assert "WARNING" in result.stderr, (
            f"Expected WARNING in stderr:\n  stderr={result.stderr!r}"
        )
        assert "vibe-kanban-mcp" in result.stderr
        # Script should continue past the binary check (installing rules, etc.)
        assert "Installing super-fr" in result.stdout

    def test_warns_if_binary_not_executable(self, tmp_path: Path) -> None:
        """A non-executable binary triggers a WARNING, not a fatal error."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()
        vk_bin = home / "bin" / "vibe-kanban-mcp"
        vk_bin.parent.mkdir(parents=True)
        vk_bin.write_text("not executable")
        vk_bin.chmod(0o644)

        result = _run_install(home, expect_fail=True)

        assert "WARNING" in result.stderr, (
            f"Expected WARNING in stderr:\n  stderr={result.stderr!r}"
        )
        # Script should continue past the binary check
        assert "Installing super-fr" in result.stdout


# ── Uninstall path ───────────────────────────────────────────────────


class TestUninstall:
    def test_removes_rules(self, fake_home: Path) -> None:
        _run_install(fake_home)
        _run_install(fake_home, "--uninstall")

        assert not (fake_home / ".claude" / "rules" / "fr-plan-override.md").exists()

    def test_removes_vk_from_mcp_config(self, fake_home: Path) -> None:
        _run_install(fake_home)
        _run_install(fake_home, "--uninstall")

        mcp = fake_home / ".claude" / ".mcp.json"
        assert mcp.exists()
        data = json.loads(mcp.read_text())
        assert "vibe_kanban" not in data["mcpServers"]

    def test_preserves_other_mcp_servers_on_uninstall(self, fake_home: Path) -> None:
        mcp = fake_home / ".claude" / ".mcp.json"
        mcp.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "other-server": {"command": "other", "args": []},
                        "vibe_kanban": {"command": "/old", "args": []},
                    }
                }
            )
        )

        _run_install(fake_home, "--uninstall")

        data = json.loads(mcp.read_text())
        assert "other-server" in data["mcpServers"]
        assert "vibe_kanban" not in data["mcpServers"]

    def test_cleans_stale_skills_on_uninstall(self, fake_home: Path) -> None:
        """Uninstall should also remove stale user-level skill copies."""
        skills_dir = fake_home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        for name in ("vk-plan", "vk-dispatch"):
            d = skills_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text("stale")

        _run_install(fake_home, "--uninstall")

        assert not (skills_dir / "vk-plan").exists()
        assert not (skills_dir / "vk-dispatch").exists()

    def test_uninstall_idempotent(self, fake_home: Path) -> None:
        """Uninstalling when nothing is installed should not fail."""
        result = _run_install(fake_home, "--uninstall")
        assert result.returncode == 0
