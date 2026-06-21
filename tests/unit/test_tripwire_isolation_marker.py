"""CI tripwire: the `.fr-isolation` marker must never be tracked (#328 Task 3).

`up` adds it to info/exclude and the repo `.gitignore`, but a hand-`git add` or
a copied worktree could still stage it — a staged marker leaks into a PR and (in
the base clone) could false-allow the enforcement hook. This guard fails loud.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def tracked_matching(names: Iterable[str], needle: str) -> list[str]:
    """Tracked paths whose basename == needle (catches nested copies too)."""
    return [n for n in names if Path(n).name == needle]


def test_tracked_matching_detects_violation() -> None:
    assert tracked_matching([".fr-isolation", "a.py"], ".fr-isolation") == [".fr-isolation"]
    assert tracked_matching(["src/.fr-isolation"], ".fr-isolation") == ["src/.fr-isolation"]


def test_tracked_matching_clean() -> None:
    assert tracked_matching(["a.py", "b.md"], ".fr-isolation") == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_marker_never_tracked() -> None:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
    )
    offenders = tracked_matching(out.stdout.splitlines(), ".fr-isolation")
    assert offenders == [], f".fr-isolation is tracked: {offenders}"
