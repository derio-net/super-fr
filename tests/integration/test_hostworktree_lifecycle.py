"""End-to-end host-worktree lifecycle on a docker-less "host".

`FR_ISOLATION_TARGET=worktree` selects `HostWorktreeTarget` at the single
`_target()` site; the full up → exec → down walk runs with NO docker/devcontainer
call ever issued (asserted via a recording runner that delegates git to the real
binary) and the base clone is never written. This is the spec §B / Test-Plan
step-2 shape a Hermes/VK pod exercises live.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.commands import isolation_cmd
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import ReapRefused, subprocess_runner
from fr.isolation.types import load_state


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if argv[:1] == ["gh"]:
            # No PR host in this sandbox — report "no PR" so down's guard passes.
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


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


def test_hostworktree_full_lifecycle_no_docker_base_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    repo = _base_repo_with_origin(tmp_path)

    runner = RecordingRunner()
    monkeypatch.setattr(isolation_cmd, "_runner", runner)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root, _mode: None)

    # Selection: the env declaration routes to the host-worktree backend.
    target = isolation_cmd._target(repo)
    assert type(target) is HostWorktreeTarget

    # up
    st = target.up(profile=None, branch="feat/slug")
    assert st.profile == "host"
    assert st.worktree.is_dir()

    # write a file in the worktree — the base clone must stay clean
    (st.worktree / "scratch.txt").write_text("work\n")
    assert _git(repo, "status", "--porcelain") == "", "base clone must be untouched"

    # exec: a real command runs in the worktree and returns 0
    assert target.exec(st, ["git", "status", "--porcelain"]) == 0

    # gc: the sweep runs docker-less (#423) and classifies this live workspace
    # instead of refusing. It has no PR and a dirty tree, so it is left alone —
    # a reconciler that reaped the run it was launched from would be worse than
    # no reconciler at all.
    actions = target.gc()
    (mine,) = [a for a in actions if a.branch == "feat/slug"]
    assert mine.action == "warned" and st.worktree.is_dir()
    assert not [a for a in actions if a.verdict == "dangling-image"]

    # down: the #435 dirty-worktree guard now refuses a plain down() on this
    # still-dirty workspace (the scratch.txt written above) — the worktree and
    # state must survive the refusal, then --force tears it down as usual.
    with pytest.raises(ReapRefused):
        target.down(st, force=False)
    assert st.worktree.is_dir()
    assert load_state(repo, "feat/slug") is not None

    target.down(st, force=True)
    assert not st.worktree.exists()
    assert load_state(repo, "feat/slug") is None

    # the whole walk touched neither docker nor devcontainer
    binaries = {c[0] for c in runner.calls if c}
    assert "docker" not in binaries
    assert "devcontainer" not in binaries


def test_later_commands_follow_the_recorded_mode_without_the_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """gh#569: `up` under FR_ISOLATION_TARGET=worktree, then every later command
    with the variable GONE — the shape of a dispatched agent, a hook, or a new
    shell. The workspace's recorded mode routes them, never the env."""
    from fr.cli import app
    from typer.testing import CliRunner

    cli = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    repo = _base_repo_with_origin(tmp_path)
    runner = RecordingRunner()
    monkeypatch.setattr(isolation_cmd, "_runner", runner)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root, _mode: None)

    res = cli.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/env"])
    assert res.exit_code == 0, res.output
    st = load_state(repo, "feat/env")
    assert st is not None and st.target == "worktree"

    monkeypatch.delenv("FR_ISOLATION_TARGET")
    capfd.readouterr()
    res = cli.invoke(
        app, ["isolation", "exec", "--repo", str(repo), "--", "git", "rev-parse", "--show-toplevel"]
    )
    assert res.exit_code == 0, res.output
    # host-worktree exec streams (capture=False), so the child writes the real fd
    printed = capfd.readouterr().out + res.output
    assert str(st.worktree.resolve()) in printed

    res = cli.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert "container=n/a (host)" in res.output

    res = cli.invoke(app, ["isolation", "down", "--repo", str(repo), "--branch", "feat/env"])
    assert res.exit_code == 0, res.output
    assert not st.worktree.exists()
    assert load_state(repo, "feat/env") is None

    binaries = {c[0] for c in runner.calls if c}
    assert "docker" not in binaries and "devcontainer" not in binaries
