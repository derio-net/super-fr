"""Integration tests for scripts/install.sh.

Each test runs install.sh with a fake $HOME so nothing touches the real
user directory.  The VK MCP binary requirement is satisfied by a tiny
stub script.

install.sh handles Claude Code plugin registration, OpenCode skill/command
delivery, MCP config, rules, the fr CLI, stale skill cleanup, and the
PostToolUse hook hint.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _plugin_version(name: str = "super-fr") -> str:
    pj = REPO_ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
    return json.loads(pj.read_text())["version"]


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


def test_install_sh_smokes_fr_binary_not_vk():
    """The uv stub hides step 10 from CI — at least pin the script text:
    the smoke check must probe the `fr` entry point (the `vk` script was
    deleted in v3; probing it fails every real install)."""
    script = INSTALL_SH.read_text()
    assert 'fr_bin="$(uv tool dir 2>/dev/null)/fr/bin/fr"' in script
    assert '"$fr_bin" --version' in script
    assert "/fr/bin/vk" not in script


# ── fr CLI install resilience (transient uv-tool flakiness) ──────────
#
# Root cause (docs/superpowers/debugging/2026-07-05-install-uv-tool-flaky.md):
# `uv tool install --force` removes the tool env in place; on macOS that rmdir
# intermittently fails with "Directory not empty" (ENOTEMPTY), and a freshly
# built env can fail a one-shot `fr --version` before it quiesces. Both are
# transient (the operator saw fail→fail→succeed with no manual fix). Step 10
# must retry rather than turn a momentary hiccup into a hard install abort.

# A stateful `uv` stub: `tool install` fails its first $UV_STUB_INSTALL_FAILS
# invocations with the real ENOTEMPTY message, then installs an `fr` entry
# point that fails its first $UV_STUB_SMOKE_FAILS `--version` calls.
_UV_RESILIENCE_STUB = r"""#!/bin/sh
case "$1 $2" in
"tool dir")
  printf '%s\n' "$UV_STUB_TOOLDIR"
  ;;
"tool install")
  c="$UV_STUB_STATE/install_count"
  n=$(cat "$c" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$c"
  if [ "$n" -le "${UV_STUB_INSTALL_FAILS:-0}" ]; then
    echo "error: failed to remove directory \`$UV_STUB_TOOLDIR/fr/lib\`:" \
         "Directory not empty (os error 66)" >&2
    exit 2
  fi
  mkdir -p "$UV_STUB_TOOLDIR/fr/bin"
  cat > "$UV_STUB_TOOLDIR/fr/bin/fr" <<'FR'
#!/bin/sh
if [ "$1" = "--version" ]; then
  sc="$UV_STUB_STATE/smoke_count"
  m=$(cat "$sc" 2>/dev/null || echo 0); m=$((m + 1)); echo "$m" > "$sc"
  if [ "$m" -le "${UV_STUB_SMOKE_FAILS:-0}" ]; then exit 1; fi
  echo "fr 9.9.9"
fi
FR
  chmod +x "$UV_STUB_TOOLDIR/fr/bin/fr"
  echo "Installed 1 executable: fr"
  ;;
"tool uninstall")
  rm -rf "$UV_STUB_TOOLDIR/fr"
  ;;
*)
  exit 0
  ;;
esac
"""


class TestFrCliInstallResilience:
    def _run(
        self,
        fake_home: Path,
        tmp_path: Path,
        *,
        install_fails: int = 0,
        smoke_fails: int = 0,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        bin_dir = fake_home / "bin"
        bin_dir.mkdir(exist_ok=True)
        uv_stub = bin_dir / "uv"
        uv_stub.write_text(_UV_RESILIENCE_STUB)
        uv_stub.chmod(0o755)

        tooldir = tmp_path / "uv-tools"
        tooldir.mkdir()
        state = tmp_path / "uv-state"
        state.mkdir()

        env = {
            "HOME": str(fake_home),
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
            "VK_INSTALL_SKIP_PREFLIGHT": "1",
            "UV_STUB_TOOLDIR": str(tooldir),
            "UV_STUB_STATE": str(state),
            "UV_STUB_INSTALL_FAILS": str(install_fails),
            "UV_STUB_SMOKE_FAILS": str(smoke_fails),
            # Keep retries instant in CI.
            "FR_INSTALL_RETRY_SLEEP": "0",
        }
        result = subprocess.run(
            ["bash", str(INSTALL_SH)],
            capture_output=True,
            text=True,
            env=env,
        )
        return result, state

    def _install_count(self, state: Path) -> int:
        f = state / "install_count"
        return int(f.read_text()) if f.exists() else 0

    def test_retries_transient_enotempty_then_succeeds(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """One ENOTEMPTY from `uv tool install` must not abort the install —
        step 10 retries and recovers (the operator's fail→succeed)."""
        result, state = self._run(fake_home, tmp_path, install_fails=1)

        assert result.returncode == 0, (
            f"transient ENOTEMPTY should be retried, not fatal:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert self._install_count(state) >= 2, "install should have been retried"
        assert "Installation complete" in result.stdout

    def test_retries_flaky_smoke_check(self, fake_home: Path, tmp_path: Path) -> None:
        """A freshly built env that fails its first `fr --version` must be
        retried, not reported as 'installed but does not run'."""
        result, _ = self._run(fake_home, tmp_path, install_fails=0, smoke_fails=1)

        assert result.returncode == 0, (
            f"transient smoke-check failure should be retried:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "does not run" not in result.stderr
        assert "Installation complete" in result.stdout

    def test_gives_up_loudly_after_max_install_attempts(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """A persistent (non-transient) install failure must still fail loud —
        retry must be bounded, never an infinite loop or a silent pass."""
        result, state = self._run(fake_home, tmp_path, install_fails=99)

        assert result.returncode != 0, "persistent failure must not be masked"
        assert self._install_count(state) >= 2, "should have retried before giving up"
        assert "Directory not empty" in (result.stdout + result.stderr)


# ── Plugin cache: stable `current` symlink as installPath ────────────


class TestPluginCacheSymlink:
    """install.sh must register installPath as a stable `current` symlink and
    keep current + the most-recent previous version dir, so a running session's
    path survives a reinstall (root cause: see
    docs/superpowers/debugging/2026-06-21-plugin-cache-symlink-installpath.md)."""

    @pytest.fixture()
    def home_with_plugins(self, fake_home: Path) -> Path:
        """fake_home plus the installed_plugins.json that gates step 4."""
        plugins = fake_home / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {}, "version": 1}))
        return fake_home

    def _cache_dir(self, home: Path, plugin: str = "super-fr") -> Path:
        return home / ".claude" / "plugins" / "cache" / "derio-net" / plugin

    def _installed(self, home: Path) -> dict:
        return json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())

    def test_installpath_is_current_symlink(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        entry = self._installed(home_with_plugins)["plugins"]["super-fr@derio-net"][0]
        assert entry["installPath"].endswith("/cache/derio-net/super-fr/current"), (
            f"installPath should be the stable symlink, got {entry['installPath']}"
        )
        # The recorded version still tracks the real plugin version.
        assert entry["version"] == _plugin_version("super-fr")

    def test_current_symlink_points_to_version_relative(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        ver = _plugin_version("super-fr")
        link = self._cache_dir(home_with_plugins) / "current"
        assert link.is_symlink(), "current must be a symlink"
        # Relative target (just the version), so the link is path-independent.
        assert os.readlink(link) == ver
        assert (link.resolve() / ".claude-plugin" / "plugin.json").exists()

    def test_keeps_current_plus_one_previous(self, home_with_plugins: Path) -> None:
        # Name-sort and mtime-sort deliberately DISAGREE: the kept-previous dir
        # (1.0.0) is lexically *smaller* but has the newer mtime, while the
        # pruned dir (9.9.9) is lexically *larger* but older. A regression to
        # name-based selection would keep 9.9.9 and fail this test, pinning the
        # N-1 pick as genuine recency rather than lexical order.
        cache = self._cache_dir(home_with_plugins)
        cache.mkdir(parents=True)
        pruned = cache / "9.9.9"
        pruned.mkdir()
        kept_prev = cache / "1.0.0"
        kept_prev.mkdir()
        os.utime(pruned, (1, 1))  # older
        os.utime(kept_prev, (1_000_000_000, 1_000_000_000))  # newer -> kept

        _run_install(home_with_plugins)

        ver = _plugin_version("super-fr")
        assert (cache / ver).exists(), "current version dir must be kept"
        assert kept_prev.exists(), (
            "most-recent previous version (by mtime) must be kept (N-1 buffer)"
        )
        assert not pruned.exists(), "older versions must be pruned even when lexically larger"
        assert (cache / "current").is_symlink(), "symlink must survive pruning"

    def test_idempotent_symlink_repoint(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        _run_install(home_with_plugins)  # ln -sfn must not fail on existing link
        link = self._cache_dir(home_with_plugins) / "current"
        assert link.is_symlink()
        assert os.readlink(link) == _plugin_version("super-fr")

    def test_first_install_no_previous_leaves_only_current(self, home_with_plugins: Path) -> None:
        # From-scratch install (no pre-existing cache dir): the zero-previous
        # path must not error and must leave exactly {current symlink, <version>}.
        _run_install(home_with_plugins)
        cache = self._cache_dir(home_with_plugins)
        ver = _plugin_version("super-fr")
        entries = sorted(p.name for p in cache.iterdir())
        assert entries == sorted(["current", ver]), (
            f"first install should leave only current + {ver}, got {entries}"
        )
        assert (cache / "current").is_symlink()
        assert (cache / ver).is_dir() and not (cache / ver).is_symlink()

    def test_dispatch_plugin_also_symlinked(self, home_with_plugins: Path) -> None:
        # Symlink + installPath registration is per-plugin; super-fr-dispatch
        # must get the same treatment as super-fr, not just the first plugin.
        _run_install(home_with_plugins)
        link = self._cache_dir(home_with_plugins, "super-fr-dispatch") / "current"
        assert link.is_symlink(), "super-fr-dispatch/current must also be a symlink"
        assert os.readlink(link) == _plugin_version("super-fr-dispatch")
        entry = self._installed(home_with_plugins)["plugins"]["super-fr-dispatch@derio-net"][0]
        assert entry["installPath"].endswith("/cache/derio-net/super-fr-dispatch/current")
