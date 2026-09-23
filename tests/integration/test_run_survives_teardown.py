"""A run survives `down --force` and comes back with `up` — #575 acceptance 4,
spec §5 Test Plan 9, driven through the REAL CLI end to end.

Real git in a temp repo, docker-less host-worktree mode, `gh` faked to report
no PR, HOME and every git config source under tmp_path. The walk:

    fr run start → commit the cursor → fr run advance (the cursor is now dirty)
    → fr isolation down refuses, naming the run
    → fr isolation down --force prints the ended-run line
    → fr run advance <id> from the base clone: exit 2, the torn-down message
    → fr isolation up --branch <b> restores the record
    → fr run status <id> from the worktree shows the ADVANCED cursor.

Before #575 the fourth step said `no run state at …` and the advanced cursor
was simply gone.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.local import subprocess_runner
from fr.isolation.types import load_state
from fr.run.model import load_run_state, run_path
from typer.testing import CliRunner

cli = CliRunner()
BRANCH = "feat/y"
RUN = "r1"

# Two cli steps then an agent step: `advance` executes `one`, moves the cursor
# to `two`, and the run stays active (an agent step is never executed here).
_SHAPE = """
workflow: walk
schema: 1
unit: run
steps:
  - id: one
    kind: cli
    run: "true"
  - id: two
    kind: cli
    run: "true"
  - id: three
    kind: agent
    skill: fr-execute
"""


def _no_pr_runner(argv: list[str], cwd: Path | None = None, **kw: Any) -> Any:
    """Real git; `gh` reports no PR (exit 1, nothing on stdout)."""
    if argv[:1] == ["gh"]:
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no pull requests found")
    return subprocess_runner(argv, cwd=cwd, **kw)


@pytest.fixture(autouse=True)
def _hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "gitcfg"
    cfg.mkdir()
    (cfg / "global").write_text("[user]\n\temail = t@t\n\tname = t\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg / "global"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg / "xdg"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    for var in ("GIT_SSH_COMMAND", "GIT_SSH", "VK_REPO_ROOT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(isolation_cmd, "_runner", _no_pr_runner)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")
    return repo.resolve()


def _fr(root: Path, shipped: Path, argv: list[str]) -> Any:
    env = {**os.environ, "VK_REPO_ROOT": str(root), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)}
    return cli.invoke(app, argv, env=env)


def test_a_dirty_run_survives_a_forced_down_and_comes_back_with_up(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "walk.yaml").write_text(_SHAPE)

    # 1. start — born in the worktree; commit the cursor on the branch.
    started = _fr(repo, shipped, ["run", "start", "walk", "--branch", BRANCH, "--run-id", RUN])
    assert started.exit_code == 0, started.output
    state = load_state(repo, BRANCH)
    assert state is not None
    wt = Path(state.worktree)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "run cursor")

    # 2. advance from the worktree: `one` runs, the cursor moves to `two`, and
    #    the committed cursor is now dirty.
    advanced = _fr(wt, shipped, ["run", "advance", RUN])
    assert advanced.exit_code == 0, advanced.output
    assert load_run_state(wt, RUN).cursor == "two"
    assert _git(wt, "status", "--porcelain")

    # 3. down refuses, naming the run it would end.
    refused = _fr(repo, shipped, ["isolation", "down", "--repo", str(repo), "--branch", BRANCH])
    assert refused.exit_code == 2, refused.output
    assert f"holds run {RUN} at step two" in refused.output
    assert wt.is_dir()

    # 4. down --force ends it and says where the record went.
    forced = _fr(
        repo, shipped, ["isolation", "down", "--repo", str(repo), "--branch", BRANCH, "--force"]
    )
    assert forced.exit_code == 0, forced.output
    preserved = repo / ".git" / "fr" / "preserved" / "feat__y"
    assert (
        f"down: ended run {RUN} at step two here — its record is preserved at {preserved}; "
        f"`fr isolation up --branch {BRANCH}` restores it"
    ) in forced.stderr
    assert not wt.exists()

    # 5. from the base clone: not a bare `no run state at`, the teardown.
    torn = json.loads((preserved / "teardown.json").read_text())["torn_down_at"]
    missing = _fr(repo, shipped, ["run", "advance", RUN])
    assert missing.exit_code == 2, missing.output
    assert (
        f"run {RUN} is not in this checkout: its workspace for {BRANCH} ({wt}) was torn "
        f"down at {torn}; its record is preserved — `fr isolation up --branch {BRANCH}` "
        "restores it, then run fr from there."
    ) in missing.stderr
    assert "no run state at" not in missing.output
    assert not run_path(repo, RUN).exists(), "the explanation must not write a run file"

    # 6. up restores the record into the new worktree.
    upped = _fr(repo, shipped, ["isolation", "up", "--repo", str(repo), "--branch", BRANCH])
    assert upped.exit_code == 0, upped.output
    assert f"isolation: restored 1 preserved file(s) (run {RUN} at two)" in upped.stderr
    wt2 = Path(load_state(repo, BRANCH).worktree)  # type: ignore[union-attr]

    # 7. status from the worktree reads the ADVANCED cursor, not the committed one.
    status = _fr(wt2, shipped, ["run", "status", RUN])
    assert status.exit_code == 0, status.output
    restored = load_run_state(wt2, RUN)
    assert restored.cursor == "two"
    assert restored.steps["one"].state == "done"
    assert "two" in status.output

    # and a second start on the branch points at the way on.
    again = _fr(repo, shipped, ["run", "start", "walk", "--branch", BRANCH, "--run-id", RUN])
    assert again.exit_code == 2, again.output
    assert f"fr run advance {RUN}" in again.output
