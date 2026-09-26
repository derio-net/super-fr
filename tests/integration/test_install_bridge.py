"""E3: `bash scripts/install.sh --install-bridge` writes a wrapper script.

The wrapper is what cron exec's; the rest of `install.sh` is irrelevant
to the bridge sub-command and must be short-circuited so this test
doesn't drag in marketplace / plugin / MCP setup.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.conftest import link_state, uv_tool_bin_dir

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def test_install_bridge_flag_writes_wrapper(tmp_path: Path) -> None:
    wrapper_path = tmp_path / "wrapper" / "run.sh"
    # Do not let this integration test depend on whichever `fr` uv tool happens
    # to be installed in the host/container. Install a disposable one with the
    # workspace's bridge adapter, matching the install.sh error's recovery path.
    tool_dir = tmp_path / "uv-tools"
    env = os.environ.copy()
    env["VK_BRIDGE_WRAPPER_PATH"] = str(wrapper_path)
    env["UV_TOOL_DIR"] = str(tool_dir)
    # gh#683: the BIN dir too. Without it uv links the disposable `fr` into the
    # real `~/.local/bin` and `--force` replaces the operator's link, which
    # dangles once pytest reaps tmp_path. `--install-bridge` reads only
    # `uv tool dir`, so nothing here needs the link on PATH.
    env["UV_TOOL_BIN_DIR"] = str(tmp_path / "uv-bin")
    real_fr = uv_tool_bin_dir(os.environ) / "fr"
    before = link_state(real_fr)
    subprocess.run(
        [
            "uv",
            "tool",
            "install",
            "--force",
            "--with",
            str(REPO_ROOT / "packages" / "fr-vk"),
            str(REPO_ROOT / "packages" / "fr"),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    # gh#683: the operator's real `fr` link is untouched by the disposable install.
    assert link_state(real_fr) == before, f"{real_fr} was relinked into {tool_dir}"
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
    assert "-m fr_vk.bridge" in contents, f"wrapper must exec `python -m fr_vk.bridge`:\n{contents}"
    # The wrapper resolves a python interpreter (preferably the venv's).
    assert "python" in contents

    # Stdout advertises a cron line referencing the wrapper.
    assert str(wrapper_path) in result.stdout
    assert "cron" in result.stdout.lower() or "*/" in result.stdout
