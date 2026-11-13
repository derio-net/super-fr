"""`ensure_worktree` never prunes another worktree (review pr1431-n1).

In devcontainer mode the container sees the common git dir (bind-mounted at its host
path) and its own workspace, never the host's other worktrees. A global `git worktree
prune` run there deregisters every one of them, because their paths do not exist from
the container's view. A directory renamed away stands in for "not mounted" here: git only
stats the path. Origins are LOCAL bare repos.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.placement.quiet import ensure_worktree, worktree_path

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _registered(repo: Path) -> set[str]:
    out = git(repo, "worktree", "list", "--porcelain")
    return {
        str(Path(line.removeprefix("worktree ")).resolve())
        for line in out.splitlines()
        if line.startswith("worktree ")
    }


def test_an_unmounted_worktree_survives_the_fr_worktree_being_created(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    other = tmp_path / "other-workspace"
    git(repo, "worktree", "add", "-q", str(other), "-b", "feat/other")
    hidden = tmp_path / "other-workspace.unmounted"
    other.rename(hidden)  # the container's view: the path is not there
    try:
        ensure_worktree(repo)
    finally:
        hidden.rename(other)
    assert str(other.resolve()) in _registered(repo)
    assert git(other, "status", "--porcelain") == ""  # still a working git checkout


def test_a_deleted_fr_worktree_is_recreated(tmp_path: Path) -> None:
    """The case the prune existed for: the fr worktree's directory was removed, so git
    still registers it and `worktree add` would refuse. Only that entry is cleared."""
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    path = ensure_worktree(repo)
    shutil.rmtree(path)
    other = tmp_path / "other-workspace"
    git(repo, "worktree", "add", "-q", str(other), "-b", "feat/other")
    hidden = tmp_path / "other-workspace.unmounted"
    other.rename(hidden)
    try:
        again = ensure_worktree(repo)
    finally:
        hidden.rename(other)
    assert again == worktree_path(repo)
    assert (again / "settings.yaml").is_file()
    assert {str(again.resolve()), str(other.resolve())} <= _registered(repo)


def test_a_locked_stale_fr_entry_is_left_alone(tmp_path: Path) -> None:
    """`git worktree prune` never removes a locked entry; neither does fr."""
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    path = ensure_worktree(repo)
    git(repo, "worktree", "lock", str(path))
    shutil.rmtree(path)
    with pytest.raises(Exception, match="cannot create"):
        ensure_worktree(repo)
    assert str(path.resolve()) in _registered(repo)
