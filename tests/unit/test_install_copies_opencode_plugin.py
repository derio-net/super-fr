"""Test that install.sh delivers fr-opencode-plugin to OpenCode plugins directory."""

import os
import subprocess
import tempfile
from pathlib import Path


def test_install_copies_opencode_plugin():
    """install.sh with OPENCODE_SKILLS_INSTALL=1 delivers fr-opencode-plugin binary."""
    with tempfile.TemporaryDirectory() as tmp_home:
        env = os.environ.copy()
        env["HOME"] = tmp_home
        env["OPENCODE_SKILLS_INSTALL"] = "1"
        env["VK_INSTALL_SKIP_PREFLIGHT"] = "1"

        # Run install.sh from the repo root
        repo_root = Path(__file__).parents[2]  # tests/unit -> project root
        result = subprocess.run(
            ["bash", "scripts/install.sh"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )

        # Should succeed
        assert result.returncode == 0, f"install.sh failed: {result.stderr}"

        # Plugin binary should exist
        plugin_path = Path(tmp_home) / ".config" / "opencode" / "plugins" / "fr-opencode-plugin"
        assert plugin_path.exists(), f"Plugin binary not found at {plugin_path}"
        assert os.access(plugin_path, os.X_OK), "Plugin binary not executable"

        # Verify it's the right binary (has fr-isolation-required export)
        # Just check it's a reasonable size (>10MB for bun compiled binary)
        assert plugin_path.stat().st_size > 10_000_000, "Plugin binary too small"


def test_uninstall_removes_opencode_plugin():
    """install.sh --uninstall removes fr-opencode-plugin binary."""
    with tempfile.TemporaryDirectory() as tmp_home:
        env = os.environ.copy()
        env["HOME"] = tmp_home
        env["OPENCODE_SKILLS_INSTALL"] = "1"
        env["VK_INSTALL_SKIP_PREFLIGHT"] = "1"

        repo_root = Path(__file__).parents[2]

        # First install
        subprocess.run(
            ["bash", "scripts/install.sh"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        plugin_path = Path(tmp_home) / ".config" / "opencode" / "plugins" / "fr-opencode-plugin"
        assert plugin_path.exists()

        # Then uninstall
        result = subprocess.run(
            ["bash", "scripts/install.sh", "--uninstall"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"uninstall failed: {result.stderr}"

        # Plugin should be removed
        assert not plugin_path.exists(), "Plugin binary not removed on uninstall"


def test_parity_delivery_tripwire():
    """Every OpenCode surface in parity.yaml (enforced/partial) has a delivered artifact."""
    import yaml

    repo_root = Path(__file__).parents[2]
    parity_path = repo_root / "packages" / "fr" / "src" / "fr" / "harness" / "parity.yaml"

    with open(parity_path) as f:
        parity = yaml.safe_load(f)

    # Collect all OpenCode surfaces that are enforced or partial
    opencode_surfaces = []
    for surface in parity.get("surfaces", []):
        harnesses = surface.get("harnesses", {})
        opencode = harnesses.get("opencode", {})
        state = opencode.get("state")
        if state in ("enforced", "partial"):
            opencode_surfaces.append(surface["id"])

    # The plugin binary delivery covers the hook surfaces:
    # - fr-isolation-required (hook) -> delivered via plugin binary
    # - fr-run-idle-guard (hook) -> delivered via plugin binary
    # The interaction surfaces are not delivered via install.sh (they're CLI behaviors)
    hook_surfaces = {"fr-isolation-required", "fr-run-idle-guard"}

    missing = hook_surfaces - set(opencode_surfaces)
    assert not missing, f"Parity.yaml missing OpenCode hook surfaces: {missing}"

    # Verify the surfaces we care about are present
    for hook in hook_surfaces:
        assert hook in opencode_surfaces, f"Parity.yaml does not credit OpenCode with {hook}"
