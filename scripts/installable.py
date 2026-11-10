"""What counts as installable: the one definition (spec 2026-11-08-sweep-fixes R17).

`release.py` asks it whether a release candidate would carry anything a consumer
installs. It is a denylist on purpose: a path nobody thought about counts as
installable, which costs at worst a spare RC and never a stranded change.
`requires_bump` (`check-change-fragment.py`) is narrower, and
`tests/unit/test_installable.py` pins that it stays inside this one.

Stdlib only, so it runs under `uv run --no-project`, like the other scripts.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

NOT_INSTALLED_DIRS = ("docs/", "tests/", ".github/", ".changes/")
NOT_INSTALLED_FILES = (".test_durations",)


def is_installable(path: str) -> bool:
    """Every repo-relative path is installable except `docs/`, `tests/`, `.github/`,
    `.changes/`, root-level `*.md` and `.test_durations`."""
    if path.startswith(NOT_INSTALLED_DIRS) or path in NOT_INSTALLED_FILES:
        return False
    return "/" in path or not path.endswith(".md")


def installable_changed(repo: Path, tag: str, *, env: Mapping[str, str] | None = None) -> bool:
    """Whether any installable path differs between *tag* and HEAD.

    A two-dot diff compares the trees, so a revert to the tag's tree is no change.
    `--no-renames` lists both sides of a move, so a file moved out of `plugins/` into
    `docs/` is a change. `-z` reads a non-ASCII path unquoted, and the bytes are decoded
    so that no locale can make the read fail.

    Raises `subprocess.CalledProcessError` when git fails: that must never read as
    "nothing changed", because a wrong no-op stops releases and nothing goes red.
    """
    diff = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", "-z", f"refs/tags/{tag}", "HEAD", "--"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    return any(is_installable(os.fsdecode(p)) for p in diff.stdout.split(b"\0") if p)
