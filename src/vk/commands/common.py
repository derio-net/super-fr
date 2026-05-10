"""Shared CLI helpers — only `resolve_repo_root` survives the v1→v2 retirement."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_repo_root(cwd: Path | None = None) -> Path:
    """Resolve the repo root for a vk command.

    Honors `$VK_REPO_ROOT` first (so integration tests can point a
    command at `tmp_path` without spawning a fake git repo), then
    falls back to `git rev-parse --show-toplevel` (run from `cwd` if
    given), then to `Path.cwd()`.

    The returned path is always `.resolve()`-d so callers can safely
    use `Path.is_relative_to` / `Path.relative_to` against other
    resolved paths, even when the source value (env var, git output,
    or cwd) traversed a symlink.

    The empty string is treated like an unset env var (we fall through
    to git) — keeping `VK_REPO_ROOT=""` as a way to disable the
    override without unsetting it.
    """
    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return (cwd or Path.cwd()).resolve()
