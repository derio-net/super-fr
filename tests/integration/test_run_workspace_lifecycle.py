"""`fr run start` is born in a REAL isolation worktree — spec §4.B, r2-f5.

Unit tests fake the isolation backend; this walks the actual thing on a
docker-less host (`FR_ISOLATION_TARGET=worktree`, the same mode
`test_hostworktree_lifecycle.py` exercises) and asserts the two properties
the review found broken:

1. the run file lands **inside the linked worktree** and nowhere in the base
   clone — a run file in the base clone is not on the feature branch and
   never reaches the PR;
2. `advance` works when invoked **from the worktree**, which is where every
   later step runs, and a `cli` step's `cwd` is the workspace root — the
   thing `plan-review`'s `fr plan self-review {{ artifacts.plan }}` depends
   on, since the plan exists only there.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.local import subprocess_runner
from fr.isolation.types import load_state
from fr.run.model import load_run_state, run_path
from typer.testing import CliRunner

runner_cli = CliRunner()

_SHAPE = """
workflow: where
schema: 1
unit: run
steps:
  - id: locate
    kind: cli
    run: git rev-parse --show-toplevel
"""


class RecordingRunner:
    """Real git, no docker — and it records enough to prove that."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if argv[:1] == ["gh"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture)


def _base_repo_with_origin(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)
    return repo


def _fr(root: Path, shipped: Path, argv: list[str]):
    return runner_cli.invoke(
        app,
        argv,
        env={**os.environ, "VK_REPO_ROOT": str(root), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)},
    )


def test_a_run_started_from_the_base_clone_is_born_in_the_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    repo = _base_repo_with_origin(tmp_path)
    runner = RecordingRunner()
    monkeypatch.setattr(isolation_cmd, "_runner", runner)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "where.yaml").write_text(_SHAPE)

    started = _fr(
        repo, shipped, ["run", "start", "where", "--branch", "feat/slug", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output

    state = load_state(repo, "feat/slug")
    assert state is not None, "start must have entered isolation itself"
    worktree = Path(state.worktree)
    assert run_path(worktree, "r1").is_file()
    assert not run_path(repo, "r1").exists(), "the base clone must come away with no run file"
    assert str(worktree) in started.output

    # advance from the WORKTREE — where every later step of the run executes.
    advanced = _fr(worktree, shipped, ["run", "advance", "r1"])
    assert advanced.exit_code == 0, advanced.output
    run_state = load_run_state(worktree, "r1")
    assert run_state.steps["locate"].state == "done"
    stdout = run_state.steps["locate"].stdout or ""
    assert Path(stdout.strip()).resolve() == worktree.resolve(), (
        "a cli step's cwd must be the workspace root, not the base clone"
    )

    assert "docker" not in {c[0] for c in runner.calls if c}


def test_starting_a_second_run_reuses_the_same_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ensure` must not mean `restart`: the recorded workspace for the branch
    is reused, and `git worktree add` runs exactly once."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    repo = _base_repo_with_origin(tmp_path)
    runner = RecordingRunner()
    monkeypatch.setattr(isolation_cmd, "_runner", runner)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "where.yaml").write_text(_SHAPE)

    _fr(repo, shipped, ["run", "start", "where", "--branch", "feat/slug", "--run-id", "r1"])
    adds = [c for c in runner.calls if c[:3] == ["git", "worktree", "add"]]
    second = _fr(
        repo, shipped, ["run", "start", "where", "--branch", "feat/slug", "--run-id", "r2"]
    )

    assert second.exit_code == 0, second.output
    worktree = Path(load_state(repo, "feat/slug").worktree)  # type: ignore[union-attr]
    assert run_path(worktree, "r2").is_file()
    assert [c for c in runner.calls if c[:3] == ["git", "worktree", "add"]] == adds
