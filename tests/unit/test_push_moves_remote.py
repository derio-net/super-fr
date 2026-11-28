"""`push_moves_remote`: would `git push <remote> HEAD:<branch>` change the remote at all
(spec 2026-11-28-alacarte-settings R9; lens findings l-security-r1, l-errors-r5).

Every case runs against a real clone of a real local bare origin. The answer is read
from the remote itself, so a remote-tracking ref this clone holds never decides it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.git_policy.push import PushRefusedError, push_moves_remote

from tests.unit.settings_repo import git, make_repo

BRANCH = "feat/x"


def _commit(repo: Path, name: str, subject: str) -> str:
    (repo / name).write_text(f"{name}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", subject)
    return git(repo, "rev-parse", "HEAD").strip()


def _remote_tip(repo: Path, branch: str) -> str:
    return git(repo.parent / "origin.git", "rev-parse", branch).strip()


def test_an_absent_branch_at_the_remote_default_tip_moves_nothing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    assert git(repo, "rev-parse", "HEAD").strip() == _remote_tip(repo, "main")

    assert push_moves_remote(repo, "origin", BRANCH) is False


def test_a_new_commit_moves_the_remote(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    _commit(repo, "a", "feat(x): a")

    assert push_moves_remote(repo, "origin", BRANCH) is True


def test_a_remote_branch_already_at_head_moves_nothing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    _commit(repo, "a", "feat(x): a")
    git(repo, "push", "-q", "origin", BRANCH)

    assert push_moves_remote(repo, "origin", BRANCH) is False


def test_moving_an_older_remote_branch_to_a_commit_main_holds_moves_the_remote(
    tmp_path: Path,
) -> None:
    """The push adds no commit (origin's HEAD holds them all), but it moves the branch."""
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    git(repo, "push", "-q", "origin", BRANCH)  # the remote branch at the seed
    old = _remote_tip(repo, BRANCH)
    git(repo, "switch", "-q", "main")
    newer = _commit(repo, "m", "feat(m): on main")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "-q", BRANCH)
    git(repo, "merge", "-q", "--ff-only", "main")
    assert git(repo, "rev-parse", "HEAD").strip() == newer != old

    assert push_moves_remote(repo, "origin", BRANCH) is True


def test_a_stale_hand_made_tracking_ref_at_head_does_not_read_as_pushed(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    git(repo, "push", "-q", "origin", BRANCH)
    head = _commit(repo, "a", "feat(x): a")
    git(repo, "update-ref", f"refs/remotes/origin/{BRANCH}", head)  # claims it is pushed
    assert _remote_tip(repo, BRANCH) != head

    assert push_moves_remote(repo, "origin", BRANCH) is True


def test_an_unreadable_remote_refuses(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", BRANCH)
    git(repo, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))

    with pytest.raises(PushRefusedError):
        push_moves_remote(repo, "origin", BRANCH)
