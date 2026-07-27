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
from fr.isolation.local import subprocess_runner
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
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)

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

    # down: worktree + state gone
    target.down(st, force=False)
    assert not st.worktree.exists()
    assert load_state(repo, "feat/slug") is None

    # the whole walk touched neither docker nor devcontainer
    binaries = {c[0] for c in runner.calls if c}
    assert "docker" not in binaries
    assert "devcontainer" not in binaries
