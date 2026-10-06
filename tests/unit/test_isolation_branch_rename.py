"""`fr.isolation.rename_branch` — move every key fr holds on a branch name (spec
2026-10-06-triage-batch-adopt §B, R4, R10).

Every test runs over a real git repo in tmp with a linked worktree, and HOME,
the session index dir and git's identity pointed at tmp: nothing here touches
the checkout under test.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation.rename import plan_rename, rename_branch
from fr.isolation.sessions import read_session_index, session_index_path
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    SessionBinding,
    load_state,
    save_state,
    state_path,
)

OLD = "feat/hand-started"
NEW = "feat/batch-x"
CURSOR = "docs/superpowers/runs/2026-10-06-feat-hand-started.yaml"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A main checkout and a linked worktree on OLD, set up as `fr isolation up`
    leaves one: a record with two bound sessions, their indexes, the marker and a
    committed run cursor naming OLD."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FR_SESSIONS_DIR", str(home / ".cache" / "fr" / "sessions"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k, v in {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }.items():
        monkeypatch.setenv(k, v)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", OLD)
    cursor = wt / CURSOR
    cursor.parent.mkdir(parents=True)
    cursor.write_text(
        "schema_version: 8\nrun: 2026-10-06-feat-hand-started\n"
        f"workflow: fr-goal@1\nbranch: {OLD}\nstarted: '2026-10-06T00:00:00+00:00'\n"
    )
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "run")
    sessions = [
        SessionBinding(session_id=s, harness="claude", attached_at="2026-10-06T00:00:00+00:00")
        for s in ("sid-a", "sid-b")
    ]
    state = IsolationState(
        repo_root=repo,
        branch=OLD,
        worktree=wt,
        profile="host",
        target="worktree",
        created_at="2026-10-06T00:00:00+00:00",
        sessions=sessions,
    )
    save_state(state)
    for b in sessions:
        p = session_index_path(b.session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"session_id": b.session_id, "branch": OLD, "worktree": str(wt)}))
    (wt / ".fr-isolation").write_text(
        json.dumps({"toplevel": str(wt.resolve()), "branch": OLD, "mode": "worktree"})
    )
    return repo, wt


def _snapshot(repo: Path, wt: Path) -> dict[str, object]:
    state = {p.name: p.read_text() for p in state_path(repo, OLD).parent.glob("*.json")}
    idx = {p.name: p.read_text() for p in session_index_path("sid-a").parent.glob("*.json")}
    return {
        "branches": _git(repo, "branch", "--list"),
        "head": _git(wt, "rev-parse", "HEAD"),
        "status": _git(wt, "status", "--porcelain"),
        "state": state,
        "idx": idx,
        "marker": (wt / ".fr-isolation").read_text(),
        "cursor": (wt / CURSOR).read_text(),
    }


def test_rename_moves_branch_record_marker_indexes_and_cursor(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    rename_branch(repo, wt, OLD, NEW)

    assert _git(wt, "rev-parse", "--abbrev-ref", "HEAD") == NEW
    assert OLD not in _git(repo, "branch", "--list")
    assert not state_path(repo, OLD).exists()
    moved = load_state(repo, NEW)
    assert moved is not None and moved.branch == NEW
    assert [b.session_id for b in moved.sessions] == ["sid-a", "sid-b"]
    assert json.loads((wt / ".fr-isolation").read_text())["branch"] == NEW
    for sid in ("sid-a", "sid-b"):
        idx = read_session_index(sid)
        assert idx is not None and idx["branch"] == NEW
    assert f"branch: {NEW}\n" in (wt / CURSOR).read_text()
    assert _git(wt, "status", "--porcelain", "--", CURSOR) == ""
    assert "branch renamed to feat/batch-x by batch adopt" in _git(wt, "log", "-1", "--format=%s")


def test_the_cursor_commit_takes_only_the_cursor_and_leaves_staged_work_staged(
    ws: tuple[Path, Path],
) -> None:
    repo, wt = ws
    (wt / "work.txt").write_text("in progress\n")
    _git(wt, "add", "work.txt")
    rename_branch(repo, wt, OLD, NEW)
    assert _git(wt, "show", "--name-only", "--format=", "HEAD") == CURSOR
    assert _git(wt, "diff", "--cached", "--name-only") == "work.txt"


def test_a_second_call_is_done_and_changes_nothing(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    assert rename_branch(repo, wt, OLD, NEW)
    before = _snapshot_new(repo, wt)
    assert rename_branch(repo, wt, OLD, NEW) == []
    assert plan_rename(repo, wt, OLD, NEW).done
    assert _snapshot_new(repo, wt) == before


def _snapshot_new(repo: Path, wt: Path) -> dict[str, object]:
    return {
        "branches": _git(repo, "branch", "--list"),
        "head": _git(wt, "rev-parse", "HEAD"),
        "state": state_path(repo, NEW).read_text(),
        "marker": (wt / ".fr-isolation").read_text(),
        "idx": read_session_index("sid-a"),
    }


def test_a_partial_rename_is_finished(ws: tuple[Path, Path]) -> None:
    """The branch moved but nothing else did (a crash after `git branch -m`)."""
    repo, wt = ws
    _git(repo, "branch", "-m", OLD, NEW)
    rename_branch(repo, wt, OLD, NEW)
    assert json.loads((wt / ".fr-isolation").read_text())["branch"] == NEW
    assert load_state(repo, NEW) is not None
    assert f"branch: {NEW}\n" in (wt / CURSOR).read_text()


def _refused(repo: Path, wt: Path, match: str, new: str = NEW, old: str = OLD) -> None:
    before = _snapshot(repo, wt)
    with pytest.raises(IsolationError, match=match):
        rename_branch(repo, wt, old, new)
    assert _snapshot(repo, wt) == before


def test_a_worktree_mid_rebase_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    Path(_git(wt, "rev-parse", "--git-path", "rebase-merge")).mkdir(parents=True)
    _refused(repo, wt, "rebase")


def test_a_worktree_mid_merge_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    Path(_git(wt, "rev-parse", "--git-path", "MERGE_HEAD")).write_text(
        _git(wt, "rev-parse", "HEAD") + "\n"
    )
    _refused(repo, wt, "merge")


def test_a_modified_cursor_file_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    with (wt / CURSOR).open("a") as f:
        f.write("cursor: implement\n")
    _refused(repo, wt, "modified")


def test_an_unrelated_existing_target_branch_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    _git(repo, "branch", NEW, "main")
    _refused(repo, wt, "already exists")


def test_an_unknown_branch_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    _refused(repo, wt, "no branch", old="feat/nope")


def test_a_worktree_on_another_branch_is_refused(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    _git(wt, "switch", "-q", "-c", "feat/elsewhere")
    _refused(repo, wt, "not on")


def test_a_dry_run_names_the_moves_and_writes_nothing(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    before = _snapshot(repo, wt)
    steps = rename_branch(repo, wt, OLD, NEW, dry_run=True)
    assert steps[0] == f"git branch -m {OLD} {NEW}"
    assert any("marker" in s for s in steps) and any("cursor" in s for s in steps)
    assert _snapshot(repo, wt) == before


def test_a_dry_run_refuses_as_the_real_call_does(ws: tuple[Path, Path]) -> None:
    repo, wt = ws
    _git(repo, "branch", NEW, "main")
    with pytest.raises(IsolationError, match="already exists"):
        rename_branch(repo, wt, OLD, NEW, dry_run=True)
