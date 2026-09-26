"""The batch verbs' git seam, `fr.triage.gitseam` (spec 2026-09-25-triage-batches
§3.F, §3.I), against real throwaway repos.

Each test pins one thing merge's scratch worktree must never do with git:
commit an untracked artifact (review r3-f7), destroy a kept worktree holding
local changes (r3-f6), or let the operator's rerere resolve a conflict for it
(r3-f12).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.triage import gitseam
from fr.triage.gitseam import Checkout, GitError


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path) -> Checkout:
    """A clone of a bare origin with one commit on main."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(clone, "config", k, v)
    _git(clone, "checkout", "--quiet", "-b", "main")
    (clone / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (clone / "a.txt").write_text("a\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "seed")
    _git(clone, "push", "--quiet", "origin", "main")
    return Checkout(clone)


def test_commit_all_stages_tracked_changes_and_version_files_only(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    wt = checkout.add_worktree(tmp_path / "scratch", "HEAD")
    (wt.path / "pyproject.toml").write_text('[project]\nversion = "1.0.1"\n')
    (wt.path / "packages").mkdir()
    (wt.path / "packages" / "new.json").write_text('{"version": "1.0.1"}\n')
    (wt.path / "build").mkdir()
    (wt.path / "build" / "artifact.bin").write_text("built by set\n")

    head = wt.commit_all("chore: re-slot", ["pyproject.toml", "packages/*.json"])

    assert head is not None
    committed = _git(wt.path, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(committed) == ["packages/new.json", "pyproject.toml"]
    assert "build/artifact.bin" in _git(wt.path, "status", "--porcelain", "--untracked-files=all")


def test_a_kept_worktree_with_local_changes_is_refused_by_name(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "state" / "merge" / "feat" / "batch-x"
    wt = checkout.add_worktree(where, "HEAD")
    (wt.path / "a.txt").write_text("a manual fix\n")

    with pytest.raises(GitError) as info:
        checkout.add_worktree(where, "HEAD")

    message = str(info.value)
    assert str(where) in message
    assert f"git worktree remove --force {where}" in message
    assert (where / "a.txt").read_text() == "a manual fix\n"  # nothing destroyed


def test_a_kept_worktree_with_an_untracked_file_is_refused(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    checkout.add_worktree(where, "HEAD")
    (where / "notes.txt").write_text("what I tried\n")

    with pytest.raises(GitError, match="local changes"):
        checkout.add_worktree(where, "HEAD")
    assert (where / "notes.txt").exists()


def test_a_clean_kept_worktree_is_replaced(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    checkout.add_worktree(where, "HEAD")

    again = checkout.add_worktree(where, "HEAD")

    assert again.path == where and (where / "a.txt").read_text() == "a\n"


def test_a_directory_that_is_not_a_worktree_is_refused(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    where.mkdir()
    (where / "leftover").write_text("x\n")

    with pytest.raises(GitError, match="not a git worktree"):
        checkout.add_worktree(where, "HEAD")
    assert (where / "leftover").exists()


def test_the_scratch_merge_disables_rerere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review r3-f12: an operator's `rerere.enabled` would replay a recorded
    resolution of a non-version conflict, so merge would see no conflict."""
    seen: list[list[str]] = []

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(argv: list[str], **kw: Any) -> _Done:
        seen.append(list(argv))
        return _Done()

    monkeypatch.setattr(gitseam.subprocess, "run", _run)

    gitseam.Worktree(tmp_path).merge("origin/main")

    merge = next(a for a in seen if "merge" in a)
    assert merge[:5] == ["git", "-c", "rerere.enabled=false", "merge", "--no-ff"]
    assert merge[-1] == "origin/main"


def test_merge_base_and_show_read_the_pr_side(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    seed = _git(checkout.path, "rev-parse", "HEAD").strip()
    wt = checkout.add_worktree(tmp_path / "scratch", "HEAD")
    (wt.path / "a.txt").write_text("pr\n")
    _git(wt.path, "commit", "--quiet", "-am", "pr")

    assert wt.merge_base("origin/main") == seed
    assert wt.show("HEAD", "a.txt") == "pr\n"
    assert wt.show(seed, "a.txt") == "a\n"
    assert wt.show(seed, "absent.txt") is None
