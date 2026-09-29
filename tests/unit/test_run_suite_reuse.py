"""`deliver` reuses a verified phase suite log on an unchanged code tree —
spec 2026-09-29-fr-goal-light-path §D (R6).

Task 1 pins the pure helpers in `fr.run.code_tree`: the code tree is
`git ls-tree -r HEAD` without fr's artifact trees (`docs/superpowers/`,
`docs/acceptance/`), so the bookkeeping `resolve` writes between the suite run
and `deliver` never reads as a code change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fr.run.code_tree import (
    FR_ARTIFACT_PREFIXES,
    code_tree,
    dirty_code_paths,
    newest_code_mtime,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _plain_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("x = 1\n")
    (repo / "docs" / "superpowers" / "runs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\n")
    _commit_all(repo, "seed")
    return repo


def _set_mtime(path: Path, at: float) -> None:
    os.utime(path, (at, at))


def test_the_excluded_prefixes_are_fr_artifact_trees() -> None:
    assert FR_ARTIFACT_PREFIXES == ("docs/superpowers/", "docs/acceptance/")


def test_code_tree_is_stable_across_a_bookkeeping_only_commit(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\nstep: x\n")
    (repo / "docs" / "acceptance").mkdir()
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text("rows: []\n")
    _commit_all(repo, "bookkeeping")

    assert code_tree(repo) == before
    assert len(before) == 64


def test_code_tree_changes_with_a_code_commit(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit_all(repo, "code")

    assert code_tree(repo) != before


def test_code_tree_takes_a_revision(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    seed = _git(repo, "rev-parse", "HEAD").strip()
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit_all(repo, "code")

    assert code_tree(repo, seed) == before


def test_code_tree_ignores_uncommitted_changes(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 3\n")

    assert code_tree(repo) == before


def test_dirty_code_paths_lists_only_uncommitted_code(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    assert dirty_code_paths(repo) == []
    (repo / "src" / "x.py").write_text("x = 3\n")
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("changed\n")
    (repo / "docs" / "superpowers" / "runs" / "r2.yaml").write_text("new\n")

    assert dirty_code_paths(repo) == ["src/new.py", "src/x.py"]


def test_newest_code_mtime_spans_committed_and_uncommitted_changes(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "y.py").write_text("y = 1\n")
    _commit_all(repo, "code")
    (repo / "src" / "z.py").write_text("z = 1\n")
    _set_mtime(repo / "src" / "x.py", 5_000)  # unchanged since base: not counted
    _set_mtime(repo / "src" / "y.py", 1_000)
    _set_mtime(repo / "src" / "z.py", 2_000)
    _set_mtime(repo / "docs" / "superpowers" / "runs" / "r1.yaml", 9_000)

    assert newest_code_mtime(repo, base) == (2_000.0, "src/z.py")

    _set_mtime(repo / "src" / "y.py", 3_000)
    assert newest_code_mtime(repo, base) == (3_000.0, "src/y.py")


def test_newest_code_mtime_is_none_when_no_code_changed(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("changed\n")

    assert newest_code_mtime(repo, base) is None


def test_newest_code_mtime_without_a_base_counts_every_code_path(tmp_path: Path) -> None:
    """No merge-base (no remote default branch): fail toward stricter — every
    tracked code path counts, so a log must be newer than all of them."""
    repo = _plain_repo(tmp_path)
    _set_mtime(repo / "src" / "x.py", 4_000)

    assert newest_code_mtime(repo, None) == (4_000.0, "src/x.py")


def test_newest_code_mtime_skips_ignored_paths(tmp_path: Path) -> None:
    """The log itself may sit in the worktree; it is not code it tested."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "suite.log").write_text("ok\n")

    assert newest_code_mtime(repo, base, ignore=[repo / "suite.log"]) is None
