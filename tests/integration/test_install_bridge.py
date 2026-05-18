"""E3: `bash scripts/install.sh --install-bridge` writes a wrapper script.

The wrapper is what cron exec's; the rest of `install.sh` is irrelevant
to the bridge sub-command and must be short-circuited so this test
doesn't drag in marketplace / plugin / MCP setup.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_install_bridge_flag_writes_wrapper(tmp_path: Path) -> None:
    wrapper_path = tmp_path / "wrapper" / "run.sh"
    env = os.environ.copy()
    env["VK_BRIDGE_WRAPPER_PATH"] = str(wrapper_path)
    # PATH still needs python3 for the venv-resolve fallback.
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--install-bridge"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"install.sh --install-bridge failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    assert wrapper_path.is_file(), f"{wrapper_path} not created"
    assert os.access(wrapper_path, os.X_OK), f"{wrapper_path} not executable"
    contents = wrapper_path.read_text()
    assert "-m vk.bridge" in contents, f"wrapper must exec `python -m vk.bridge`:\n{contents}"
    # The wrapper resolves a python interpreter (preferably the venv's).
    assert "python" in contents

    # Stdout advertises a cron line referencing the wrapper.
    assert str(wrapper_path) in result.stdout
    assert "cron" in result.stdout.lower() or "*/" in result.stdout
