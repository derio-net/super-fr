"""`archive_plan_dir` keeps the live plans root in every clone (super-fr#1277).

Git tracks no empty directory, so archiving the last plan used to leave a clone with no
`docs/superpowers/plans`, and the edit gate read the repo as not fr-enabled.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from fr.archive import archive_plan_dir


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path, *slugs: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for slug in slugs:
        d = repo / "docs" / "superpowers" / "plans" / slug
        d.mkdir(parents=True)
        (d / "_meta.yaml").write_text("plan: x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _plan(repo: Path, slug: str) -> Path:
    return repo / "docs" / "superpowers" / "plans" / slug


def test_archiving_the_last_plan_leaves_a_staged_gitkeep(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "a")
    archive_plan_dir(repo, _plan(repo, "a"))
    keep = repo / "docs" / "superpowers" / "plans" / ".gitkeep"
    assert keep.is_file() and not keep.is_symlink() and keep.read_bytes() == b""
    assert "docs/superpowers/plans/.gitkeep" in _git(repo, "diff", "--cached", "--name-only")
    _git(repo, "commit", "-qm", "archive")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
    assert (clone / "docs" / "superpowers" / "plans").is_dir()


def test_archiving_one_of_two_plans_writes_no_gitkeep(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "a", "b")
    archive_plan_dir(repo, _plan(repo, "a"))
    assert not (repo / "docs" / "superpowers" / "plans" / ".gitkeep").exists()


def test_a_gitkeep_symlink_is_neither_followed_nor_replaced(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me")
    for target in (tmp_path / "dangling", outside):
        sub = tmp_path / f"r-{target.name}"
        sub.mkdir()
        repo = _repo(sub, "a")
        keep = repo / "docs" / "superpowers" / "plans" / ".gitkeep"
        os.symlink(target, keep)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "link")
        archive_plan_dir(repo, _plan(repo, "a"))
        assert keep.is_symlink() and os.readlink(keep) == str(target)
    assert outside.read_text() == "keep me"
    assert not (tmp_path / "dangling").exists()


def test_an_existing_untracked_gitkeep_is_staged(tmp_path: Path) -> None:
    # review p1-r1: a regular `.gitkeep` already on disk but not in the index (never
    # added, or `git rm --cached`) must still be staged by the archive that needs it.
    repo = _repo(tmp_path, "a")
    keep = repo / "docs" / "superpowers" / "plans" / ".gitkeep"
    keep.write_text("")
    archive_plan_dir(repo, _plan(repo, "a"))
    assert "docs/superpowers/plans/.gitkeep" in _git(repo, "diff", "--cached", "--name-only")


def test_a_gitkeep_that_cannot_be_staged_is_reported_not_swallowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # review l-errors-r1: git refuses to add an ignored path; the archive still succeeds
    # but says the live root was not staged, naming the path and git's own message.
    repo = _repo(tmp_path, "a")
    (repo / ".gitignore").write_text("docs/superpowers/plans/.gitkeep\n")
    archive_plan_dir(repo, _plan(repo, "a"))
    err = capsys.readouterr().err
    assert "docs/superpowers/plans/.gitkeep not staged" in err
    assert "git add failed" in err and "ignored" in err
