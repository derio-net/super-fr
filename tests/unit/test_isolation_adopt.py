"""`fr.isolation.adopt` — the one isolation seam `fr triage batch adopt` calls
(spec 2026-10-11-batch-adopt-safety-2 §B "The isolation seam").

Host-worktree mode only (`FR_ISOLATION_TARGET=worktree`): real throwaway repos
with a real bare origin, never a devcontainer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation import adopt
from fr.isolation.sessions import attach, read_session_index
from fr.isolation.types import IsolationError, load_state

from tests.unit.test_isolation import _commit_in_worktree, make_repo_with_origin


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setattr("fr.commands.isolation_cmd._gc_spawner", lambda *a, **k: None)
    root, _origin = make_repo_with_origin(tmp_path)
    return root


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_enter_workspace_cuts_the_branch_from_origin_and_a_second_call_resumes(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    where = adopt.enter_workspace(repo, "feat/batch-x")
    assert where.is_dir()
    assert _git(where, "rev-parse", "--abbrev-ref", "HEAD") == "feat/batch-x"
    assert _git(where, "rev-parse", "HEAD") == _git(repo, "rev-parse", "origin/main")
    assert load_state(repo, "feat/batch-x") is not None

    calls: list[str] = []
    real = adopt._select_target

    def counting(root: Path) -> object:
        calls.append(str(root))
        return real(root)

    monkeypatch.setattr(adopt, "_select_target", counting)
    assert adopt.enter_workspace(repo, "feat/batch-x") == where
    assert calls == [str(repo)]  # `up` is called again: a resume, never a skip


def test_enter_workspace_always_calls_up_with_no_profile(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[object, str]] = []

    class Target:
        def up(self, profile: object, branch: str) -> object:
            seen.append((profile, branch))
            return type("S", (), {"worktree": repo.parent / "wt"})()

    monkeypatch.setattr(adopt, "_select_target", lambda root: Target())
    assert adopt.enter_workspace(repo, "feat/batch-x") == repo.parent / "wt"
    assert seen == [(None, "feat/batch-x")]


def test_bind_session_returns_none_on_success_and_a_warning_on_failure(repo: Path) -> None:
    adopt.enter_workspace(repo, "feat/batch-x")
    assert adopt.bind_session(repo, "feat/batch-x", "sess-1", "claude") is None
    index = read_session_index("sess-1")
    assert index is not None and index["branch"] == "feat/batch-x"

    warning = adopt.bind_session(repo, "feat/none", "sess-2", "claude")
    assert warning is not None and "feat/none" in warning


def test_bind_session_never_raises(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise IsolationError("state unwritable")

    monkeypatch.setattr(adopt, "attach", boom)
    warning = adopt.bind_session(repo, "feat/batch-x", "s", "claude")
    assert warning is not None and "state unwritable" in warning


def test_reusable_workspace_accepts_one_with_no_commits_and_refuses_one_with(
    repo: Path,
) -> None:
    assert adopt.reusable_workspace(repo, "feat/batch-x", None, ahead=0) is None  # none yet
    where = adopt.enter_workspace(repo, "feat/batch-x")
    assert adopt.reusable_workspace(repo, "feat/batch-x", None, ahead=0) == where
    _commit_in_worktree(where, "work.txt")
    assert adopt.reusable_workspace(repo, "feat/batch-x", None, ahead=1) is None
    assert adopt.reusable_workspace(repo, "feat/batch-x", "other", ahead=1) is None


def test_reusable_workspace_accepts_one_this_session_is_bound_to(repo: Path) -> None:
    where = adopt.enter_workspace(repo, "feat/batch-x")
    attach(repo, "feat/batch-x", "sess-1", "claude")
    assert adopt.reusable_workspace(repo, "feat/batch-x", "sess-1", ahead=3) == where


def test_session_worktree_reads_the_session_index(repo: Path) -> None:
    assert adopt.session_worktree("nobody") is None
    assert adopt.session_worktree("bad/id") is None  # an invalid id is unknown, not an error
    where = adopt.enter_workspace(repo, "feat/batch-x")
    attach(repo, "feat/batch-x", "sess-1", "claude")
    assert adopt.session_worktree("sess-1") == where


def test_workspace_containing_finds_the_workspace_around_a_path(
    repo: Path, tmp_path: Path
) -> None:
    where = adopt.enter_workspace(repo, "feat/batch-x")
    (where / "sub").mkdir()
    assert adopt.workspace_containing(repo, where / "sub") == where
    assert adopt.workspace_containing(repo, where) == where
    assert adopt.workspace_containing(repo, repo) is None
    assert adopt.workspace_containing(tmp_path / "not-a-repo", tmp_path) is None
