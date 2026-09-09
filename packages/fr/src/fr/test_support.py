"""Test-support assertions phase executors reach for (methodology restoration).

`assert_no_repo_mutation` is the ready-made answer to the #464 failure: a
draft test needing a git repo in a particular state ran `git rm --cached`
and `git commit` against the REAL checkout instead of a sandbox, and the
suite reported green throughout. Tests that need a repo sandbox it and wrap
the block in this assertion — drift fails loud, naming the paths.

Deliberately dependency-free (stdlib only): generated tests import it
without pulling the CLI stack.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["assert_no_repo_mutation"]

GIT_TIMEOUT_SECONDS = 30.0
"""Mirrors `fr.artifacts.commit.GIT_TIMEOUT_SECONDS`: a git that never
returns (dead mount, credential prompt) must fail loud, never wedge."""


def _porcelain(repo_root: Path) -> str:
    """`git status --porcelain` for `repo_root`, or a loud failure."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise AssertionError(
            f"`git status --porcelain` in {repo_root} did not finish within "
            f"{GIT_TIMEOUT_SECONDS:g}s — refusing to assert on an unreadable repo"
        ) from e
    if done.returncode != 0:
        raise AssertionError(
            f"`git status --porcelain` in {repo_root} failed: {done.stderr.strip()}"
        )
    return done.stdout


@contextmanager
def assert_no_repo_mutation(repo_root: Path) -> Iterator[None]:
    """Fail loud if the block changes `repo_root`'s git state.

    Compares full porcelain (tracked AND untracked): scratch files belong in
    `tmp_path`, not in the repo under test — a stray file left behind is
    drift too. The diff names the paths, so the failure points at the
    mutation instead of merely reporting "green but dirty".
    """
    before = _porcelain(repo_root)
    yield
    after = _porcelain(repo_root)
    if after != before:
        raise AssertionError(
            f"test mutated the repo under test ({repo_root}):\n"
            f"--- before\n{before}--- after\n{after}"
            "Sandbox the repo (a scratch clone or worktree) instead of "
            "operating on the real checkout."
        )
