"""`fr.test_support.assert_no_repo_mutation` — the ready-made sandbox
assertion phase executors reach for (methodology restoration, phase 5).

A test that needs a git repo in a particular state must sandbox it: this
context manager snapshots `git status --porcelain` around the block and
fails loud on any drift — the #464 failure was a draft test running
`git rm --cached` + `git commit` against the real checkout while the suite
reported green throughout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    (tmp_path / "tracked.txt").write_text("v1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "seed"], check=True)
    return tmp_path


def test_clean_block_passes(tmp_path: Path) -> None:
    from fr.test_support import assert_no_repo_mutation

    repo = _repo(tmp_path)

    with assert_no_repo_mutation(repo):
        (repo / "tracked.txt").read_text()


def test_tracked_mutation_fails_naming_the_file(tmp_path: Path) -> None:
    from fr.test_support import assert_no_repo_mutation

    repo = _repo(tmp_path)

    with pytest.raises(AssertionError, match="tracked.txt"):
        with assert_no_repo_mutation(repo):
            (repo / "tracked.txt").write_text("v2\n")


def test_untracked_stray_file_fails(tmp_path: Path) -> None:
    from fr.test_support import assert_no_repo_mutation

    repo = _repo(tmp_path)

    with pytest.raises(AssertionError):
        with assert_no_repo_mutation(repo):
            (repo / "stray.txt").write_text("oops\n")


def test_scratch_elsewhere_is_fine(tmp_path: Path) -> None:
    """Scratch belongs outside the repo — activity elsewhere is not drift."""
    from fr.test_support import assert_no_repo_mutation

    repo = _repo(tmp_path / "repo")
    elsewhere = tmp_path / "scratch"
    elsewhere.mkdir()

    with assert_no_repo_mutation(repo):
        (elsewhere / "work.txt").write_text("fine\n")


def test_hung_git_fails_closed_not_hangs(monkeypatch, tmp_path: Path) -> None:
    """A git that never returns (dead mount, credential prompt) becomes a
    loud failure, not a wedged suite — mirroring `fr.artifacts.commit`."""
    import fr.test_support as ts
    from fr.test_support import assert_no_repo_mutation

    def _hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git status", timeout=30)

    monkeypatch.setattr(ts.subprocess, "run", _hang)

    with pytest.raises(AssertionError, match="did not finish"):
        with assert_no_repo_mutation(tmp_path):
            pass
