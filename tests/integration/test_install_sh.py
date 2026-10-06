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
import shutil
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
    xdg_config_home: Path | None = None,
    install_sh: Path = INSTALL_SH,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh with fake HOME, stubbing uv so step 10 is a no-op.

    Args:
        fake_home: The fake home directory to use as $HOME
        extra_args: Additional arguments to pass to install.sh
        expect_fail: If True, do not assert on return code
        xdg_config_home: If provided, set $XDG_CONFIG_HOME to this path (defaults to $HOME/.config)
    """
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

    if xdg_config_home is None:
        xdg_config_home = fake_home / ".config"

    env = {
        "HOME": str(fake_home),
        "XDG_CONFIG_HOME": str(xdg_config_home),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        # Bypass the main/clean/in-sync gate: integration tests run install.sh
        # from the repo checkout (often detached HEAD on CI), which would
        # always fail the gate. The escape hatch is documented in install.sh.
        "VK_INSTALL_SKIP_PREFLIGHT": "1",
    }
    result = subprocess.run(
        ["bash", str(install_sh), *extra_args],
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
    def _extract_installed_rule_filenames(self) -> set[str]:
        """Extract rule filenames from install.sh's installation declarations."""
        script = INSTALL_SH.read_text()
        import re

        # Prefer the install-side array so this remains coupled to the same
        # authoritative list used by both install and uninstall.
        array = re.search(r"CLAUDE_RULES=\(([^)]*)\)", script)
        assert array, "CLAUDE_RULES array not found in install.sh"
        return set(re.findall(r"[\w.-]+\.md", array.group(1)))

    def test_removes_all_installed_rules_on_uninstall(self, fake_home: Path) -> None:
        """Uninstall removes every rule that install.sh installs.

        This derives the rule filenames from install.sh, installs, and asserts
        each is absent after uninstall.
        """
        # Install
        _run_install(fake_home)

        # Get expected installed rules from install.sh
        installed_rules = self._extract_installed_rule_filenames()
        assert installed_rules, "No rules found in install.sh"

        # Verify they were actually installed
        rules_dir = fake_home / ".claude" / "rules"
        for rule_file in installed_rules:
            assert (rules_dir / rule_file).exists(), (
                f"Rule {rule_file} should be installed by install.sh"
            )

        # Uninstall
        _run_install(fake_home, "--uninstall")

        # Verify all installed rules are removed
        for rule_file in installed_rules:
            assert not (rules_dir / rule_file).exists(), (
                f"Rule {rule_file} should be removed by --uninstall but still exists"
            )

    def test_removes_retired_vk_plan_override_on_uninstall(self, fake_home: Path) -> None:
        """Uninstall removes the retired vk-plan-override.md rule, even if not currently installed.

        vk-plan-override.md was the old name before the rename; --uninstall must clean it up.
        """
        # Simulate an older install that left behind vk-plan-override.md
        rules_dir = fake_home / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        retired = rules_dir / "vk-plan-override.md"
        retired.write_text("old rule content")

        # Uninstall should remove it even though we never installed it in this test
        _run_install(fake_home, "--uninstall")

        assert not retired.exists(), "Retired vk-plan-override.md should be removed by --uninstall"

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


def test_install_sh_no_longer_prints_validator_wrapper_per_repo_step(fake_home: Path) -> None:
    result = _run_install(fake_home)

    assert "Per-repo step" not in result.stdout
    assert "install-validator-wrapper.sh" not in result.stdout


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


# ── Plugin cache: `current` is one real directory, synced in place ──


class TestPluginCacheDirectory:
    """installPath is `<cache>/<plugin>/current`, a real directory updated in
    place. It used to be a symlink to a version dir with current + one
    previous kept, which assumed a session keeps installPath literal
    (docs/superpowers/debugging/2026-06-21-plugin-cache-symlink-installpath.md).
    It does not: Claude Code runs a session's hooks from the RESOLVED path, so
    the prune deleted it two releases later (gh#938; the release-by-release
    regression is tests/integration/test_install_atomic.py)."""

    @pytest.fixture()
    def home_with_plugins(self, fake_home: Path) -> Path:
        """fake_home plus the installed_plugins.json that gates step 4."""
        plugins = fake_home / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {}, "version": 1}))
        return fake_home

    def _cache_dir(self, home: Path, plugin: str = "super-fr") -> Path:
        return home / ".claude" / "plugins" / "cache" / "derio-net--super-fr" / plugin

    def _installed(self, home: Path) -> dict:
        return json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())

    def test_installpath_is_the_current_directory(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        entry = self._installed(home_with_plugins)["plugins"]["super-fr@derio-net--super-fr"][0]
        assert entry["installPath"].endswith("/cache/derio-net--super-fr/super-fr/current")
        current = Path(entry["installPath"])
        assert current.is_dir() and not current.is_symlink(), "current must be a real directory"
        # The recorded version still tracks the real plugin version, and so does the content.
        assert entry["version"] == _plugin_version("super-fr")
        pj = json.loads((current / ".claude-plugin" / "plugin.json").read_text())
        assert pj["version"] == _plugin_version("super-fr")

    def test_first_install_leaves_only_current(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        cache = self._cache_dir(home_with_plugins)
        assert sorted(p.name for p in cache.iterdir()) == ["current"]

    def test_reinstall_updates_in_place(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        current = self._cache_dir(home_with_plugins) / "current"
        inode = current.stat().st_ino
        stray = current / "hooks" / "removed-upstream.sh"
        stray.write_text("exit 0\n")
        _run_install(home_with_plugins)
        assert current.stat().st_ino == inode, "the directory a session holds must not be replaced"
        assert not stray.exists(), "a file gone from the source is gone from current"

    def test_legacy_version_dirs_go_by_age_not_by_count(self, home_with_plugins: Path) -> None:
        cache = self._cache_dir(home_with_plugins)
        for name in ("1.0.0", "1.0.1", "1.0.2", "9.9.9"):
            (cache / name).mkdir(parents=True)
        os.utime(cache / "9.9.9", (1, 1))  # over a week old
        _run_install(home_with_plugins)
        assert not (cache / "9.9.9").exists()
        for name in ("1.0.0", "1.0.1", "1.0.2"):
            assert (cache / name).is_dir(), f"{name} is recent: a session may still hold it"

    def test_dispatch_plugin_gets_the_same_layout(self, home_with_plugins: Path) -> None:
        _run_install(home_with_plugins)
        current = self._cache_dir(home_with_plugins, "super-fr-dispatch") / "current"
        assert current.is_dir() and not current.is_symlink()
        entry = self._installed(home_with_plugins)["plugins"][
            "super-fr-dispatch@derio-net--super-fr"
        ][0]
        assert entry["installPath"].endswith("/cache/derio-net--super-fr/super-fr-dispatch/current")


# ── Workflow manifests ──────────────────────────────────────────────


class TestMarketplaceRsyncSkipsLocalState:
    """gh#630: the marketplace rsync copies the repo root wholesale. Local
    state there (coverage data, which xdist workers create and delete while
    the rsync walks it, and the container venv) must not ship, and must not
    be able to fail the copy. Runs from a copy of the tracked tree, so the
    stray files never touch the real checkout."""

    STRAYS = (".coverage", ".coverage.host.1234.XyZ", ".venv-container/bin/python")

    def test_local_state_never_reaches_the_marketplace(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        tracked = (
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .split("\0")
        )
        checkout = tmp_path / "checkout"
        for rel in filter(None, tracked):
            src = REPO_ROOT / rel
            if src.is_file():
                (checkout / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, checkout / rel)
        for rel in self.STRAYS:
            (checkout / rel).parent.mkdir(parents=True, exist_ok=True)
            (checkout / rel).write_text("local state\n")

        _run_install(fake_home, install_sh=checkout / "scripts" / "install.sh")

        marketplace = fake_home / ".claude" / "plugins" / "marketplaces" / "derio-net--super-fr"
        assert (marketplace / "scripts" / "install.sh").is_file()
        shipped = [rel for rel in self.STRAYS if (marketplace / rel).exists()]
        assert not shipped, f"local state copied into the marketplace: {shipped}"


class TestInstallWorkflows:
    """Drift guard for shipped workflow manifests (spec §4.A, Phase 11).

    Unlike rules (test_install_copies_rules.py) or the OpenCode skill mirror
    (test_install_copies_opencode_skills.py), a shipped workflow manifest
    needs NO per-file `cp` line: `plugins/super-fr/workflows/` lives inside
    `plugins/super-fr/`, so it rides the same wholesale, un-excluded rsync
    (`$PLUGIN_ROOT/` -> `$MARKETPLACE_DIR/`) every other file under
    `plugins/super-fr/` already takes. These tests prove that delivery for
    real rather than trusting the absence of an `--exclude` — an install.sh
    edit that added one (or moved the rsync source) would fail this loudly,
    which is the whole point of a drift guard.

    `fr.workflow.resolve.default_shipped_workflows_dir()`'s fallback is
    literally `$HOME/.claude/plugins/marketplaces/derio-net--super-fr/
    plugins/super-fr/workflows` — i.e. `$MARKETPLACE_DIR/plugins/super-fr/
    workflows` — so the marketplace directory (not the version-pinned cache)
    is the one this module's own runtime lookup actually reads.
    """

    def test_shipped_manifest_lands_in_the_marketplace_directory(self, fake_home: Path) -> None:
        _run_install(fake_home)

        manifest = (
            fake_home
            / ".claude"
            / "plugins"
            / "marketplaces"
            / "derio-net--super-fr"
            / "plugins"
            / "super-fr"
            / "workflows"
            / "fr-goal.yaml"
        )
        assert manifest.exists(), (
            "plugins/super-fr/workflows/fr-goal.yaml must be delivered by install.sh's "
            "marketplace-directory rsync"
        )
        assert "workflow: fr-goal" in manifest.read_text()

    def test_shipped_manifest_matches_the_repo_source_byte_for_byte(self, fake_home: Path) -> None:
        _run_install(fake_home)

        installed = (
            fake_home
            / ".claude"
            / "plugins"
            / "marketplaces"
            / "derio-net--super-fr"
            / "plugins"
            / "super-fr"
            / "workflows"
            / "fr-goal.yaml"
        )
        source = REPO_ROOT / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml"
        assert installed.read_text() == source.read_text()

    def test_every_shipped_workflow_manifest_is_delivered(self, fake_home: Path) -> None:
        _run_install(fake_home)

        source_dir = REPO_ROOT / "plugins" / "super-fr" / "workflows"
        installed_dir = (
            fake_home
            / ".claude"
            / "plugins"
            / "marketplaces"
            / "derio-net--super-fr"
            / "plugins"
            / "super-fr"
            / "workflows"
        )
        source_names = sorted(p.name for p in source_dir.glob("*.yaml"))
        assert source_names, "expected at least the shipped fr-goal.yaml"
        installed_names = sorted(p.name for p in installed_dir.glob("*.yaml"))
        assert installed_names == source_names


# ── fr-herdr rides beside fr: `--with-executables-from` and a second PATH link ──

_UV_PATH_LINK_STUB = r"""#!/bin/sh
# Records each `uv tool install` and builds the tool env the way uv does: the entry
# points live under <tool dir>/fr/bin, and `fr-herdr` only when asked for it.
case "$1 $2 $3" in
"tool dir --bin") printf '%s\n' "$UV_STUB_BINDIR" ;;
"tool dir "*) printf '%s\n' "${UV_TOOL_DIR:-$UV_STUB_TOOLDIR}" ;;
"tool install "*)
  td="${UV_TOOL_DIR:-$UV_STUB_TOOLDIR}"
  echo "INSTALL tooldir=$td" >> "$UV_STUB_LOG"
  for a in "$@"; do printf '  %s\n' "$a" >> "$UV_STUB_LOG"; done
  # what the PATH link names while this install is running (staged, or uv's own env)
  echo "link-fr-herdr=$(readlink "$UV_STUB_BINDIR/fr-herdr" 2>/dev/null)" >> "$UV_STUB_LOG"
  mkdir -p "$td/fr/bin"
  printf '#!/bin/sh\necho "fr 9.9.9"\n' > "$td/fr/bin/fr"
  chmod +x "$td/fr/bin/fr"
  case " $* " in
  *" --with-executables-from "*)
    if [ -z "${UV_STUB_NO_HERDR:-}" ]; then
      printf '#!/bin/sh\nexit 0\n' > "$td/fr/bin/fr-herdr"
      chmod +x "$td/fr/bin/fr-herdr"
    fi
    ;;
  esac
  ;;
*) exit 0 ;;
esac
"""


class TestFrHerdrOnPath:
    @staticmethod
    def _run(
        fake_home: Path, tmp_path: Path, *, preexisting_fr: bool, no_herdr: bool = False
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
        bin_dir = fake_home / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "uv").write_text(_UV_PATH_LINK_STUB)
        (bin_dir / "uv").chmod(0o755)
        path_bin = tmp_path / "path-bin"
        path_bin.mkdir()
        tooldir = tmp_path / "uv-tools"
        tooldir.mkdir()
        log = tmp_path / "uv.log"
        if preexisting_fr:  # a live fr link makes install.sh stage a copy aside first
            old = tmp_path / "old-fr"
            old.write_text("#!/bin/sh\n")
            (path_bin / "fr").symlink_to(old)
        env = {
            "HOME": str(fake_home),
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
            "VK_INSTALL_SKIP_PREFLIGHT": "1",
            "FR_INSTALL_RETRY_SLEEP": "0",
            "FR_INSTALL_DRAIN_SECONDS": "0",
            "UV_STUB_BINDIR": str(path_bin),
            "UV_STUB_TOOLDIR": str(tooldir),
            "UV_STUB_LOG": str(log),
        }
        if no_herdr:
            env["UV_STUB_NO_HERDR"] = "1"
        result = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True, env=env)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        return result, path_bin, tooldir, log

    @staticmethod
    def _installs(log: Path) -> list[list[str]]:
        blocks: list[list[str]] = []
        for line in log.read_text().splitlines():
            if line.startswith("INSTALL"):
                blocks.append([])
            elif blocks:
                blocks[-1].append(line.strip())
        return blocks

    def test_both_installs_ask_for_fr_herdrs_executables(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        _, _, _, log = self._run(fake_home, tmp_path, preexisting_fr=True)
        installs = self._installs(log)
        assert len(installs) == 2, "a staged install, then the final one"
        for block in installs:
            i = block.index("--with-executables-from")
            assert block[i + 1] == "fr-herdr"

    def test_the_fr_herdr_link_is_staged_then_repointed_like_frs(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        _, path_bin, tooldir, log = self._run(fake_home, tmp_path, preexisting_fr=True)
        link = path_bin / "fr-herdr"
        assert link.is_symlink()
        assert os.readlink(link) == str(tooldir / "fr" / "bin" / "fr-herdr")
        assert os.readlink(path_bin / "fr") == str(tooldir / "fr" / "bin" / "fr")
        # while the final install ran, the link already named the staged copy
        final = [ln for ln in log.read_text().splitlines() if ln.startswith("link-fr-herdr=")][-1]
        assert "/install-stage/" in final

    def test_a_first_install_creates_the_link(self, fake_home: Path, tmp_path: Path) -> None:
        _, path_bin, tooldir, _ = self._run(fake_home, tmp_path, preexisting_fr=False)
        assert os.readlink(path_bin / "fr-herdr") == str(tooldir / "fr" / "bin" / "fr-herdr")

    def test_no_link_when_fr_herdr_was_not_installed(self, fake_home: Path, tmp_path: Path) -> None:
        _, path_bin, _, _ = self._run(fake_home, tmp_path, preexisting_fr=True, no_herdr=True)
        assert not (path_bin / "fr-herdr").exists() and not (path_bin / "fr-herdr").is_symlink()


def test_candidate_install_asks_for_fr_herdrs_executables(tmp_path: Path) -> None:
    """`.fr/candidate-install` installs into `<prefix>/bin`, which is on the walk's PATH:
    the flag alone puts `fr-herdr` there."""
    bin_dir = tmp_path / "stub"
    bin_dir.mkdir()
    log = tmp_path / "argv"
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do printf "%s\\n" "$a" >> "$UV_STUB_LOG"; done\n'
        'mkdir -p "$UV_TOOL_BIN_DIR"\n'
        'printf "#!/bin/sh\\necho fr 9\\n" > "$UV_TOOL_BIN_DIR/fr"\n'
        'chmod +x "$UV_TOOL_BIN_DIR/fr"\n'
    )
    uv.chmod(0o755)
    result = subprocess.run(
        [str(REPO_ROOT / ".fr" / "candidate-install"), str(tmp_path / "prefix"), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "UV_STUB_LOG": str(log),
        },
    )
    assert result.returncode == 0, result.stderr
    argv = log.read_text().splitlines()
    assert argv[argv.index("--with-executables-from") + 1] == "fr-herdr"
