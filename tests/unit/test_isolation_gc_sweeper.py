"""`GcSweeper` runs gc for a target and calls that target's own overrides
(spec 2026-11-27-isolation-gc-sweeper R5, R7).

gc moved off `LocalWorktreeDevcontainerTarget` into a collaborator. The mode
differences gc depends on stay on the target classes: a host-worktree target
has no containers, so its sweep must never run docker, while a devcontainer
target's sweep asks docker for its labelled containers. A sweeper that called
its own copy of a target step, or the base class's, would lose that.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fr.isolation.gc import GcSweeper
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationState, load_state, save_state

from tests.unit.test_isolation import FakeRunner, make_repo_with_origin

_BRANCH = "feat/gone"


def _host_record_with_no_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    save_state(
        IsolationState(
            repo_root=repo.resolve(),
            branch=_BRANCH,
            worktree=tmp_path / "vanished-worktree",
            profile="host",
            target="worktree",
            created_at="2026-11-27T00:00:00+00:00",
        )
    )
    return repo


def _action_for(actions, worktree: Path):
    found = [a for a in actions if a.worktree == str(worktree)]
    assert len(found) == 1, actions
    return found[0]


def test_a_host_worktree_sweep_runs_no_docker_and_retires_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _host_record_with_no_worktree(tmp_path, monkeypatch)
    runner = FakeRunner()
    target = HostWorktreeTarget(repo, runner=runner, gc_spawner=lambda _r, _m: None)

    actions = GcSweeper(target).gc()

    assert not [c for c in runner.calls if c and c[0] == "docker"], runner.calls
    action = _action_for(actions, tmp_path / "vanished-worktree")
    assert (action.verdict, action.action) == ("orphan", "reaped"), action
    assert load_state(repo, _BRANCH) is None


def test_a_devcontainer_sweep_asks_docker_for_labelled_containers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _host_record_with_no_worktree(tmp_path, monkeypatch)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    GcSweeper(target).gc()

    labelled = [
        c
        for c in runner.calls
        if c[:3] == ["docker", "ps", "-a"] and "label=devcontainer.local_folder" in c
    ]
    assert labelled, runner.calls


def test_the_gc_module_imports_on_its_own() -> None:
    result = subprocess.run(
        [sys.executable, "-P", "-c", "import fr.isolation.gc"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
