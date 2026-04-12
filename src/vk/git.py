"""Git subprocess wrappers.

Thin wrappers around git commands used by the vk toolchain.
All functions raise subprocess.CalledProcessError on failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def repo_root(cwd: Path | None = None) -> Path:
    """Return the root directory of the current git repository."""
    output = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(output.strip())


def add(paths: list[str], cwd: Path | None = None) -> None:
    """Stage files for commit."""
    _run_git(["add", *paths], cwd=cwd)


def commit(message: str, cwd: Path | None = None) -> None:
    """Create a commit with the given message."""
    _run_git(["commit", "-m", message], cwd=cwd)


def status(cwd: Path | None = None) -> str:
    """Return porcelain status output."""
    return _run_git(["status", "--porcelain"], cwd=cwd)
