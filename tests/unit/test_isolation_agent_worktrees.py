"""gh#1270: fr reaps the `agent-*` worktrees Claude Code never removes.

A registered WorktreeCreate replaces Claude's native creation, and Claude Code
(2.1.316, measured live) then never fires WorktreeRemove for the subagent, so
nothing removed them. `fr isolation gc` now does, conservatively: a worktree is
reaped only when it is clean, every commit on it is reachable from a branch, tag
or remote ref (ancestry, never PR state), no live session holds its lock, and it
is older than the threshold. Everything kept is reported, never removed.

Real git throughout: the decision reads `git worktree list --porcelain`, status
and rev-list, and a fake would only restate the implementation.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
from fr.isolation.agent_worktrees import (
    AGENT_MIN_AGE_SECONDS,
    agent_cache_root,
    sweep_agent_worktrees,
)

LATER = time.time() + AGENT_MIN_AGE_SECONDS + 3600


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    (path / ".gitignore").write_text(".claude/worktrees/\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path.resolve()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _repo(tmp_path / "src" / "repo")


def _legacy(repo: Path, name: str, inside: Path | None = None) -> Path:
    wt = (inside or repo) / ".claude" / "worktrees" / name
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--detach", str(wt), "HEAD")
    return wt


def _cached(repo: Path, name: str, lock: str | None = None) -> Path:
    wt = agent_cache_root() / repo.name / name
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--detach", str(wt), "HEAD")
    if lock is not None:
        _git(repo, "worktree", "lock", "--reason", lock, str(wt))
    return wt


def _listed(repo: Path) -> list[str]:
    out = _git(repo, "worktree", "list", "--porcelain")
    return [ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("worktree ")]


def _by_path(actions: list) -> dict[str, object]:
    return {a.worktree: a for a in actions}


def _sweep(repo: Path, **kw: object) -> list:
    kw.setdefault("now", LATER)
    kw.setdefault("pid_alive", lambda pid: False)
    return sweep_agent_worktrees(repo, dry_run=kw.pop("dry_run", False), **kw)  # type: ignore[arg-type]


def test_an_old_clean_legacy_worktree_is_reaped_and_logged(repo: Path) -> None:
    wt = _legacy(repo, "agent-a1")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].verdict == "agent-worktree"
    assert actions[str(wt)].action == "reaped"
    assert not wt.exists()
    assert str(wt) not in _listed(repo)
    log = (agent_cache_root() / "reap.log").read_text()
    assert str(wt) in log and "reaped" in log


def test_a_young_worktree_is_left_alone(repo: Path) -> None:
    wt = _legacy(repo, "agent-young")
    actions = _by_path(_sweep(repo, now=time.time()))
    assert actions[str(wt)].action == "skipped"
    assert "younger than" in actions[str(wt)].detail
    assert wt.exists()


def test_a_dirty_worktree_is_reported_never_removed(repo: Path) -> None:
    wt = _legacy(repo, "agent-dirty")
    (wt / "scratch.txt").write_text("work\n")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "warned"
    assert "uncommitted" in actions[str(wt)].detail
    assert (wt / "scratch.txt").exists()


def test_a_commit_on_no_ref_is_reported_never_removed(repo: Path) -> None:
    wt = _legacy(repo, "agent-commit")
    (wt / "f.txt").write_text("f\n")
    _git(wt, "add", "f.txt")
    _git(wt, "commit", "-qm", "work only this detached HEAD holds")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "warned"
    assert "no branch, tag or remote" in actions[str(wt)].detail
    assert wt.exists()


def test_a_commit_a_branch_holds_is_reaped_by_ancestry(repo: Path) -> None:
    """Ancestry, not PR state (the gc classifier's known quirk must not leak in):
    a commit any ref reaches is not lost by removing the checkout."""
    wt = _legacy(repo, "agent-pushed")
    (wt / "f.txt").write_text("f\n")
    _git(wt, "add", "f.txt")
    _git(wt, "commit", "-qm", "work")
    _git(wt, "branch", "kept-work")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "reaped"


def test_a_live_session_lock_protects_even_an_old_worktree(repo: Path) -> None:
    wt = _cached(repo, "agent-live", lock=f"fr-agent pid={os.getpid()} session=s")
    actions = _by_path(_sweep(repo, pid_alive=lambda pid: pid == os.getpid()))
    assert actions[str(wt)].action == "skipped"
    assert f"pid {os.getpid()}" in actions[str(wt)].detail
    assert wt.exists()


def test_a_dead_session_lock_is_released_and_reaped(repo: Path) -> None:
    wt = _cached(repo, "agent-dead", lock="fr-agent pid=999999 session=s")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "reaped"
    assert not wt.exists()
    assert str(wt) not in _listed(repo)


def test_a_dead_session_lock_still_waits_for_the_age_threshold(repo: Path) -> None:
    """The lock's pid is the hook's parent. Were that ever a short-lived shell
    instead of Claude, a dead pid alone would reap a running subagent's tree."""
    wt = _cached(repo, "agent-freshdead", lock="fr-agent pid=999999 session=s")
    actions = _by_path(_sweep(repo, now=time.time()))
    assert actions[str(wt)].action == "skipped"
    assert wt.exists()


def test_a_lock_fr_did_not_take_is_respected(repo: Path) -> None:
    wt = _cached(repo, "agent-foreign", lock="someone else's")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "skipped"
    assert "locked" in actions[str(wt)].detail
    assert wt.exists()


def test_nested_legacy_worktrees_go_child_first(repo: Path) -> None:
    outer = _legacy(repo, "agent-outer")
    inner = _legacy(repo, "agent-inner", inside=outer)
    actions = _sweep(repo)
    order = [a.worktree for a in actions if a.action == "reaped"]
    assert order == [str(inner), str(outer)]
    assert not outer.exists()


def test_dry_run_reports_and_removes_nothing(repo: Path) -> None:
    wt = _legacy(repo, "agent-dry")
    actions = _by_path(_sweep(repo, dry_run=True))
    assert actions[str(wt)].action == "would-reap"
    assert wt.exists()
    assert not (agent_cache_root() / "reap.log").exists()


def test_the_cache_is_swept_host_wide(tmp_path: Path, repo: Path) -> None:
    """`gc` is host-wide: sweeping from repo A reaps repo B's finished subagent
    worktrees in the shared cache, as it already does B's fr workspaces."""
    other = _repo(tmp_path / "src" / "other")
    wt = _cached(other, "agent-b1")
    actions = _by_path(_sweep(repo))
    assert actions[str(wt)].action == "reaped"
    assert str(wt) not in _listed(other)


def test_worktrees_that_are_not_subagents_are_never_touched(tmp_path: Path, repo: Path) -> None:
    session = _legacy(repo, "feature-x")  # `claude --worktree` in a non-fr repo
    workspace = tmp_path / "ws"
    _git(repo, "worktree", "add", "-b", "feat/y", str(workspace))
    actions = _by_path(_sweep(repo))
    assert str(session) not in actions and str(workspace) not in actions
    assert session.exists() and workspace.exists()


def test_a_non_repo_root_yields_nothing(tmp_path: Path) -> None:
    assert _sweep(tmp_path / "nowhere") == []
