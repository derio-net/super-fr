"""`fr placement move` refuses while fr's own clones hold pending writes (review
pr1431-n2).

The copy into quiet resets the `fr` worktree's index and tree (`read-tree -u --reset`),
and the stealth copy commits through the tracking clone. A write left pending in either
would be discarded or swept into the move's commit, so the R27 precondition lists them
beside the workspaces. Every repo is a local sandbox with bare remotes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import move, quiet, stealth
from fr.settings import SettingsError

from tests.unit.settings_repo import make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

__all__ = ["stealth_home"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    quiet._CACHE.clear()


def test_a_pending_write_in_the_fr_worktree_refuses_the_move(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    frwt = quiet.worktree_path(repo)
    (frwt / "pending.md").write_text("not yet committed\n")
    assert any(str(frwt) in d for d in move.dirty_workspaces(repo))
    with pytest.raises(SettingsError, match="uncommitted work"):
        move.move(repo, "repo", emit=lambda _l: None)


def test_a_pending_write_in_a_tracking_clone_is_listed(tmp_path: Path) -> None:
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    ref = stealth.parse_ref(f"{track}@main")
    HostWorktreeTarget(target).up(profile=None, branch="feat/s", stealth=ref)
    clone = stealth.worktree_path(target, ref)
    (clone / "pending.md").write_text("x\n")
    assert any(str(clone) in d for d in move.dirty_workspaces(target))


def test_clean_clones_are_not_listed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    assert move.dirty_workspaces(repo) == []
