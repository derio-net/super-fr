"""gh#1087: the installers' host-prerequisite preflight.

`install.sh` and `bootstrap.sh` used to stop at the FIRST missing command with
"Install it first" — no install command for the host, and a second missing
tool only surfaced on the next attempt. Both now name EVERY missing
prerequisite and the command that installs them on the detected OS.

The host's PATH cannot be emptied of `jq` or `rsync` (they live in /usr/bin), so
each test runs the script against a PATH "farm": a directory of symlinks to
every executable in /usr/bin and /bin except the ones the test removes, plus
stubs for `uv` and (to pick the OS) `uname` and a package manager.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
BOOTSTRAP_SH = REPO_ROOT / "scripts" / "bootstrap.sh"


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


def _farm(tmp_path: Path, *, drop: set[str], os_name: str, pkg: str | None) -> Path:
    farm = tmp_path / "farm"
    farm.mkdir()
    for src in (Path("/usr/bin"), Path("/bin")):
        for exe in src.iterdir():
            name = exe.name
            if name in drop or name in {"uname", "apt-get", "dnf", "apk", "brew", "uv"}:
                continue
            if not (farm / name).exists() and os.access(exe, os.X_OK):
                (farm / name).symlink_to(exe)
    if "uv" not in drop:
        _stub(farm / "uv", "exit 0")
    _stub(farm / "uname", f"echo {os_name}")
    if pkg:
        _stub(farm / pkg, "exit 0")
    return farm


def _run(script: Path, tmp_path: Path, farm: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "PATH": str(farm),
        "VK_INSTALL_SKIP_PREFLIGHT": "1",
        "FR_SRC_DIR": str(tmp_path / "src"),
        "FR_SRC_REMOTE": str(tmp_path / "no-such-remote"),
    }
    return subprocess.run(
        [str(farm / "bash"), str(script)], capture_output=True, text=True, env=env, timeout=120
    )


@pytest.mark.parametrize("script", [INSTALL_SH, BOOTSTRAP_SH], ids=["install", "bootstrap"])
class TestEveryMissingPrerequisiteIsNamedWithItsInstallCommand:
    def test_linux_with_apt(self, tmp_path: Path, script: Path) -> None:
        farm = _farm(tmp_path, drop={"jq", "rsync"}, os_name="Linux", pkg="apt-get")
        result = _run(script, tmp_path, farm)
        assert result.returncode != 0
        assert "'jq'" in result.stderr and "'rsync'" in result.stderr, result.stderr
        assert "apt-get install -y jq rsync" in result.stderr, result.stderr
        assert not (tmp_path / "src").exists(), "bootstrap must refuse before cloning"

    def test_macos_with_brew(self, tmp_path: Path, script: Path) -> None:
        farm = _farm(tmp_path, drop={"jq", "rsync"}, os_name="Darwin", pkg="brew")
        result = _run(script, tmp_path, farm)
        assert result.returncode != 0
        assert "brew install jq rsync" in result.stderr, result.stderr

    def test_missing_uv_names_its_own_installer(self, tmp_path: Path, script: Path) -> None:
        farm = _farm(tmp_path, drop={"uv"}, os_name="Linux", pkg="apt-get")
        result = _run(script, tmp_path, farm)
        assert result.returncode != 0
        assert "'uv'" in result.stderr
        assert "astral.sh/uv/install.sh" in result.stderr, result.stderr


def _prereq_block(script: Path) -> str:
    text = script.read_text()
    start = text.index("# >>> prereq preflight")
    return text[start : text.index("# <<< prereq preflight", start)]


def test_the_two_copies_of_the_preflight_are_identical() -> None:
    """bootstrap.sh runs from `curl | bash` before the clone exists, so it
    cannot source install.sh's copy; the two are kept byte-identical instead."""
    assert _prereq_block(INSTALL_SH) == _prereq_block(BOOTSTRAP_SH)
