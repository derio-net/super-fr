"""Integration tests for scripts/bootstrap.sh — the remote one-liner installer.

bootstrap.sh manages a hidden source checkout (clone if absent, else
fetch + reset --hard origin/main) and execs scripts/install.sh from it with
forwarded args. These tests point it at a local file:// origin (via
FR_SRC_REMOTE) whose install.sh is a stub that records its argv — so we assert
delegation + arg forwarding + self-healing update, without a network clone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
BOOTSTRAP_SH = REPO_ROOT / "scripts" / "bootstrap.sh"

_STUB_INSTALL = """\
#!/usr/bin/env bash
# Stub install.sh: record argv so the test can assert delegation + forwarding.
printf '%s\\n' "$@" > "$BOOTSTRAP_TEST_MARKER"
echo "stub install ran"
"""


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _origin_repo(tmp_path: Path) -> Path:
    """A git repo on `main` containing the real bootstrap.sh + a stub install.sh."""
    origin = tmp_path / "origin"
    (origin / "scripts").mkdir(parents=True)
    (origin / "scripts" / "bootstrap.sh").write_text(BOOTSTRAP_SH.read_text())
    (origin / "scripts" / "install.sh").write_text(_STUB_INSTALL)
    (origin / "scripts" / "install.sh").chmod(0o755)
    _run(["git", "-c", "init.defaultBranch=main", "init"], origin)
    _run(["git", "config", "user.email", "t@t"], origin)
    _run(["git", "config", "user.name", "t"], origin)
    _run(["git", "add", "-A"], origin)
    _run(["git", "commit", "-q", "-m", "init"], origin)
    return origin


def _bin_stubs(tmp_path: Path) -> Path:
    """A bin dir with uv + jq stubs (bootstrap only preflights their presence)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("uv", "jq"):
        stub = bin_dir / name
        if not stub.exists():
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
    return bin_dir


def _run_bootstrap(
    tmp_path: Path, origin: Path, src: Path, marker: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    bin_dir = _bin_stubs(tmp_path)
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        "FR_SRC_DIR": str(src),
        "FR_SRC_REMOTE": f"file://{origin}",
        "BOOTSTRAP_TEST_MARKER": str(marker),
    }
    (tmp_path / "home").mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(BOOTSTRAP_SH), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_clones_and_delegates_with_forwarded_args(tmp_path: Path) -> None:
    origin = _origin_repo(tmp_path)
    src = tmp_path / "src"
    marker = tmp_path / "marker.txt"

    res = _run_bootstrap(tmp_path, origin, src, marker, "--uninstall")

    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    # Source was cloned into FR_SRC_DIR.
    assert (src / ".git").exists()
    assert (src / "scripts" / "install.sh").exists()
    # Stub install.sh ran with the forwarded arg.
    assert marker.read_text().strip() == "--uninstall"


def test_rerun_is_idempotent_and_updates_source(tmp_path: Path) -> None:
    origin = _origin_repo(tmp_path)
    src = tmp_path / "src"
    marker = tmp_path / "marker.txt"

    first = _run_bootstrap(tmp_path, origin, src, marker)
    assert first.returncode == 0, f"stdout={first.stdout}\nstderr={first.stderr}"

    # New commit upstream; a re-run must fetch + reset --hard to pick it up.
    (origin / "NEWFILE").write_text("v2\n")
    _run(["git", "add", "-A"], origin)
    _run(["git", "commit", "-q", "-m", "v2"], origin)

    second = _run_bootstrap(tmp_path, origin, src, marker)
    assert second.returncode == 0, f"stdout={second.stdout}\nstderr={second.stderr}"
    assert (src / "NEWFILE").exists(), "re-run did not update the managed source checkout"


def test_bootstrap_delegates_to_install_sh_text() -> None:
    """Pin the contract: bootstrap execs install.sh (single source of truth)."""
    script = BOOTSTRAP_SH.read_text()
    assert 'exec "$SRC/scripts/install.sh"' in script
