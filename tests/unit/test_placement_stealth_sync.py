"""The tracking clone never overwrites the tracking ref (review p4-r1; spec
2026-11-04-repo-feature-settings R24 "fail-fast", append-only state).

A host that committed a state write and died before its push leaves an unpushed commit
in its tracking clone. Meanwhile another host pushes. The first host's next write must
land ON TOP of the other host's commit, never instead of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.placement import stealth
from fr.settings import SettingsError

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files

__all__ = ["stealth_home"]


def _other_host_pushes(tmp_path: Path, track: Path, name: str, rel: str = "B.txt") -> None:
    other = tmp_path / name
    git(tmp_path, "clone", "-q", str(track), str(other))
    git(other, "config", "user.name", "t")
    git(other, "config", "user.email", "t@example.invalid")
    (other / rel).write_text("b\n")
    git(other, "add", "-A")
    git(other, "commit", "-qm", "host B state")
    git(other, "push", "-q", "origin", "main")


def _setup(tmp_path: Path) -> tuple[Path, stealth.StealthRef, Path, Path]:
    target, track = stealth_pair(tmp_path)
    ref = stealth.parse_ref(f"{track}@main")
    wt = stealth.ensure_worktree(target, ref)
    git(wt, "config", "user.name", "t")
    git(wt, "config", "user.email", "t@example.invalid")
    return target, ref, wt, track


def test_a_diverged_clone_never_force_overwrites_another_hosts_push(tmp_path: Path) -> None:
    target, ref, wt, track = _setup(tmp_path)
    (wt / "A1.txt").write_text("a1\n")
    assert stealth.plain_commit(wt, [wt / "A1.txt"], "A1, died before its push").committed
    _other_host_pushes(tmp_path, track, "hostB")

    stealth.ensure_worktree(target, ref)  # host A re-enters
    (wt / "A2.txt").write_text("a2\n")
    out = stealth.commit_and_push(
        ref, wt, [wt / "A2.txt"], "A2", stealth.plain_commit, target_remote=None
    )

    assert out.committed
    files = tracked_files(track)
    assert "B.txt" in files  # host B's state survived
    assert "A2.txt" in files
    subjects = git(track, "log", "--format=%s", "main").splitlines()
    assert "host B state" in subjects


def test_the_push_seam_replays_a_diverged_head_instead_of_forcing(tmp_path: Path) -> None:
    """Even with no re-entry: the remote-tracking ref already names B (a fetch happened),
    HEAD sits on A1 beside it. The lease would match B, so only an ancestry check stops
    a force push."""
    _, ref, wt, track = _setup(tmp_path)
    (wt / "A1.txt").write_text("a1\n")
    assert stealth.plain_commit(wt, [wt / "A1.txt"], "A1").committed
    _other_host_pushes(tmp_path, track, "hostB")
    git(wt, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main")
    (wt / "A2.txt").write_text("a2\n")

    stealth.commit_and_push(
        ref, wt, [wt / "A2.txt"], "A2", stealth.plain_commit, target_remote=None
    )

    assert {"B.txt", "A1.txt", "A2.txt"} <= set(tracked_files(track))


def test_reentry_fast_forwards_a_clone_that_is_behind(tmp_path: Path) -> None:
    target, ref, wt, track = _setup(tmp_path)
    _other_host_pushes(tmp_path, track, "hostB")
    stealth.ensure_worktree(target, ref)
    assert git(wt, "rev-parse", "HEAD") == git(track, "rev-parse", "main")


def test_reentry_refuses_a_fast_forward_that_fails(tmp_path: Path) -> None:
    """An untracked file in the clone where the remote adds the same path: the ff cannot
    run, and fr says so rather than reading the stale clone as the state."""
    target, ref, wt, track = _setup(tmp_path)
    _other_host_pushes(tmp_path, track, "hostB")
    (wt / "B.txt").write_text("in the way\n")
    with pytest.raises(SettingsError, match="cannot bring the tracking worktree"):
        stealth.ensure_worktree(target, ref)


def test_reentry_replays_unpushed_commits_on_the_new_tip(tmp_path: Path) -> None:
    target, ref, wt, track = _setup(tmp_path)
    (wt / "A1.txt").write_text("a1\n")
    assert stealth.plain_commit(wt, [wt / "A1.txt"], "A1").committed
    _other_host_pushes(tmp_path, track, "hostB")
    stealth.ensure_worktree(target, ref)
    tip = git(track, "rev-parse", "main").strip()
    assert git(wt, "merge-base", "--is-ancestor", tip, "HEAD") == ""
    assert (wt / "B.txt").is_file() and (wt / "A1.txt").is_file()


def test_reentry_refuses_unpushed_commits_that_conflict(tmp_path: Path) -> None:
    target, ref, wt, track = _setup(tmp_path)
    (wt / "B.txt").write_text("mine\n")
    assert stealth.plain_commit(wt, [wt / "B.txt"], "A1").committed
    head = git(wt, "rev-parse", "HEAD")
    _other_host_pushes(tmp_path, track, "hostB")
    with pytest.raises(SettingsError, match="unpushed"):
        stealth.ensure_worktree(target, ref)
    assert git(wt, "rev-parse", "HEAD") == head  # left as it was, no rebase in progress
    assert not (Path(git(wt, "rev-parse", "--absolute-git-dir")) / "rebase-merge").exists()
