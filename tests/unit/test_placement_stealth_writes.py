"""Fail-fast and the fatal state push (spec 2026-11-04-repo-feature-settings R24
"fail-fast"; plan 2026-11-12-placement-resolver phase 4, task 3).

Target and tracking repos are LOCAL bare repos; a tracking repo that is gone is a path
that no longer exists, and a push the remote refuses is a pre-receive hook that declines.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError, IsolationState
from fr.placement import stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files

__all__ = ["stealth_home"]

SHAPE = """
workflow: tiny
schema: 1
unit: run
steps:
  - id: work
    kind: agent
  - id: after
    kind: agent
"""
FEATURE = "local--origin/features/feat__s"


def _snapshot(*roots: Path) -> dict[str, bytes]:
    """Every file below *roots* (git dirs excluded), path -> bytes."""
    out: dict[str, bytes] = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_file() and ".git" not in p.relative_to(root).parts:
                out[str(p)] = p.read_bytes()
    return out


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[IsolationState, Path, Path]:
    """(stealth workspace state, tracking bare repo, shipped shapes dir), cwd in the
    workspace."""
    target, track = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "tiny.yaml").write_text(SHAPE)
    monkeypatch.chdir(state.worktree)
    return state, track, shipped


def _fr(ws: tuple[IsolationState, Path, Path], *argv: str):
    state, _, shipped = ws
    env = {
        **os.environ,
        "VK_REPO_ROOT": str(state.worktree),
        "FR_SHIPPED_WORKFLOWS_DIR": str(shipped),
    }
    result = CliRunner().invoke(app, list(argv), env=env)
    if result.exception and not isinstance(result.exception, SystemExit):
        import traceback

        traceback.print_exception(result.exception)
    return result


def _tracking_wt(state: IsolationState) -> Path:
    return stealth.worktree_path(state.worktree, stealth.parse_ref(state.tracking or ""))


def test_up_refuses_a_missing_tracking_repo_before_writing(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    shutil.rmtree(track)
    before = _snapshot(target)
    with pytest.raises(IsolationError, match="unreachable"):
        HostWorktreeTarget(target).up(
            profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
        )
    assert _snapshot(target) == before
    assert not (Path(os.environ["HOME"]) / ".cache").exists()


def test_up_refuses_a_missing_branch(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    with pytest.raises(IsolationError, match="no branch 'gone'"):
        HostWorktreeTarget(target).up(
            profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@gone")
        )


def test_run_start_commits_and_pushes_the_cursor_to_the_tracking_repo(
    ws: tuple[IsolationState, Path, Path],
) -> None:
    state, track, _ = ws
    head = git(state.worktree, "rev-parse", "HEAD")
    result = _fr(ws, "run", "start", "tiny", "--branch", "feat/s", "--run-id", "r1")
    assert result.exit_code == 0, result.output
    files = tracked_files(track)
    assert f"{FEATURE}/docs/superpowers/runs/r1.yaml" in files
    assert f"{FEATURE}/OWNER" in files
    assert git(state.worktree, "rev-parse", "HEAD") == head  # nothing on the product branch
    assert git(state.worktree, "status", "--porcelain").strip() == ""


def test_run_start_refuses_a_tracking_repo_gone_mid_run(
    ws: tuple[IsolationState, Path, Path],
) -> None:
    state, track, _ = ws
    shutil.rmtree(track)
    stealth.reset_caches()
    result = _fr(ws, "run", "start", "tiny", "--branch", "feat/s", "--run-id", "r1")
    assert result.exit_code == 2, result.output
    assert "unreachable" in " ".join(result.output.split())
    assert not (_tracking_wt(state) / FEATURE).exists()


def test_every_write_refuses_before_writing_when_the_tracking_repo_is_gone(
    ws: tuple[IsolationState, Path, Path],
) -> None:
    state, track, _ = ws
    shutil.rmtree(track)
    stealth.reset_caches()
    before = _snapshot(state.worktree, _tracking_wt(state))
    result = _fr(ws, "plan", "create", "--slug", "2026-11-12-s", "--target-repo", "derio-net/s")
    assert result.exit_code == 2, result.output
    assert "unreachable" in " ".join(result.output.split())
    assert _snapshot(state.worktree, _tracking_wt(state)) == before


def _decline_pushes(track: Path) -> None:
    hook = track / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'declined by policy' >&2\nexit 1\n")
    hook.chmod(0o755)


def test_a_refused_push_fails_the_resolve_and_moves_nothing(
    ws: tuple[IsolationState, Path, Path],
) -> None:
    state, track, _ = ws
    assert _fr(ws, "run", "start", "tiny", "--branch", "feat/s", "--run-id", "r1").exit_code == 0
    assert _fr(ws, "run", "advance", "r1").exit_code == 0
    wt = _tracking_wt(state)
    remote_before = git(track, "rev-parse", "main")
    local_before = git(wt, "rev-parse", "HEAD")
    from fr.artifacts.paths import artifact_root

    record = artifact_root(state.worktree) / "docs/superpowers/runs/r1.records/work.yaml"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("schema_version: 11\nrun: r1\nstep: work\noutcome: done\n")
    bytes_before = _snapshot(wt)
    _decline_pushes(track)

    result = _fr(ws, "run", "resolve", "r1", "--step", "work", "--record", str(record))

    assert result.exit_code == 2, result.output
    assert "refused the state push" in " ".join(result.output.split())
    assert git(track, "rev-parse", "main") == remote_before  # the tracking ref did not move
    assert git(wt, "rev-parse", "HEAD") == local_before  # nor did the local tracking branch
    assert _snapshot(wt) == bytes_before  # the cursor is back to its pre-resolve bytes
    assert git(wt, "status", "--porcelain", "--untracked-files=no").strip() == ""
    assert record.is_file()  # the record survives a refusal, to be resolved again


def test_a_refused_push_on_a_plain_write_is_exit_2_not_a_warning(
    ws: tuple[IsolationState, Path, Path],
) -> None:
    state, track, _ = ws
    _decline_pushes(track)
    result = _fr(ws, "plan", "create", "--slug", "2026-11-12-s", "--target-repo", "derio-net/s")
    assert result.exit_code == 2, result.output
    assert "refused the state push" in " ".join(result.output.split())
    assert git(_tracking_wt(state), "status", "--porcelain", "--untracked-files=no") == ""


def test_a_lost_race_is_replayed_on_the_new_tip(
    ws: tuple[IsolationState, Path, Path], tmp_path: Path
) -> None:
    """Another target (or host) pushed the tracking branch meanwhile: fr fetches,
    replays its own commit there (features' paths are disjoint) and pushes again."""
    state, track, _ = ws
    other = tmp_path / "other-writer"
    git(tmp_path, "clone", "-q", str(track), str(other))
    git(other, "config", "user.name", "t")
    git(other, "config", "user.email", "t@example.invalid")
    (other / "local--elsewhere").mkdir()
    (other / "local--elsewhere/x.txt").write_text("x\n")
    git(other, "add", "-A")
    git(other, "commit", "-qm", "another target")
    git(other, "push", "-q", "origin", "main")

    result = _fr(ws, "run", "start", "tiny", "--branch", "feat/s", "--run-id", "r1")

    assert result.exit_code == 0, result.output
    files = tracked_files(track)
    assert "local--elsewhere/x.txt" in files
    assert f"{FEATURE}/docs/superpowers/runs/r1.yaml" in files
