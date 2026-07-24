"""HostWorktreeTarget — the fr linked worktree without the devcontainer half.

Mode host-worktree (spec §B): fr owns workspace isolation (a real linked git
worktree + `.fr-isolation` marker), the host process env IS the env — no
`resolve_profile`, no `devcontainer up`, no docker at all. Every assertion that
"no container was touched" rides the RECORDING runner: it delegates git to the
real binary (cheap throwaway repos) and records every non-git argv, so a stray
`devcontainer`/`docker` call is caught structurally, not by mocking Docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import subprocess_runner
from fr.isolation.types import IsolationError, IsolationState, load_state

from tests.unit.test_isolation import make_repo


class RecordingRunner:
    """Wraps `subprocess_runner` but appends every argv to `calls` — so tests
    assert the exact command sequence (and the ABSENCE of devcontainer/docker).
    git hits the real binary (deterministic throwaway repos)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.captures: list[bool] = []

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.captures.append(capture)
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture)

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c and c[0] == binary]


def _no_container_calls(runner: RecordingRunner) -> None:
    assert not runner.argv_for("devcontainer"), "host-worktree must never call devcontainer"
    assert not runner.argv_for("docker"), "host-worktree must never call docker"


# ---------- Task 1: up ----------


def test_up_creates_worktree_marker_state_no_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)  # NO .devcontainer/ at all — fine in this mode
    runner = RecordingRunner()
    target = HostWorktreeTarget(repo, runner=runner)

    st = target.up(profile=None, branch="feat/x")

    assert st.profile == "host"
    assert st.branch == "feat/x"
    assert st.worktree.is_dir() and (st.worktree / "README.md").is_file()
    # marker written, mode "worktree" (a host-worktree IS a genuine linked wt)
    import json

    marker = json.loads((st.worktree / ".fr-isolation").read_text())
    assert marker["mode"] == "worktree"
    assert marker["toplevel"] == str(st.worktree.resolve())
    # state round-trips
    assert load_state(repo, "feat/x") == st
    _no_container_calls(runner)


def test_up_no_devcontainer_profile_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """resolve_profile is NOT consulted — a repo with no .devcontainer/ is a
    valid host-worktree host (the profile rule is a devcontainer-mode rule)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    assert not (repo / ".devcontainer").exists()
    target = HostWorktreeTarget(repo, runner=RecordingRunner())
    target.up(profile=None, branch="feat/x")  # must not raise IsolationError


def test_up_idempotent_when_worktree_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    target = HostWorktreeTarget(repo, runner=RecordingRunner())
    first = target.up(profile=None, branch="feat/x")
    second = target.up(profile=None, branch="feat/x")  # worktree already present
    assert first.worktree == second.worktree
    assert second.worktree.is_dir()


def test_up_outside_git_repo_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(IsolationError, match="git repo"):
        HostWorktreeTarget(tmp_path / "nowhere", runner=RecordingRunner()).up(
            profile=None, branch="feat/x"
        )


# ---------- Task 2: exec / restart / stats / down ----------


def _upped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, RecordingRunner, HostWorktreeTarget, IsolationState]:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    runner = RecordingRunner()
    target = HostWorktreeTarget(repo, runner=runner)
    st = target.up(profile=None, branch="feat/x")
    runner.calls.clear()
    runner.captures.clear()
    return repo, runner, target, st


def test_exec_runs_in_worktree_no_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch)
    rc = target.exec(st, ["git", "status", "--porcelain"])
    assert rc == 0
    # the recorded argv is EXACTLY the requested command — no devcontainer wrapper
    git_calls = runner.argv_for("git")
    assert git_calls[-1] == ["git", "status", "--porcelain"]
    assert runner.captures[-1] is False, "exec must inherit stdio (stream output live)"
    _no_container_calls(runner)


def test_exec_echo_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch)
    rc = target.exec(st, ["echo", "hi"])
    assert rc == 0
    assert runner.calls[-1] == ["echo", "hi"]


def test_restart_raises_externally_managed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, target, st = _upped(tmp_path, monkeypatch)
    with pytest.raises(IsolationError, match="external"):
        target.restart(st)


def test_stats_raises_externally_managed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, target, st = _upped(tmp_path, monkeypatch)
    with pytest.raises(IsolationError, match="external"):
        target.stats(st)


def test_down_removes_worktree_marker_state_no_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(tmp_path, monkeypatch)
    target.down(st, force=False)
    assert not st.worktree.exists()
    assert load_state(repo, "feat/x") is None
    _no_container_calls(runner)


def test_down_refuses_open_pr_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(tmp_path, monkeypatch)
    monkeypatch.setattr(target, "_pr", lambda state: {"state": "OPEN", "url": "u"})
    with pytest.raises(IsolationError, match="open"):
        target.down(st, force=False)
    assert st.worktree.is_dir()  # untouched
    _no_container_calls(runner)


def test_down_force_overrides_open_pr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, st = _upped(tmp_path, monkeypatch)
    monkeypatch.setattr(target, "_pr", lambda state: {"state": "OPEN", "url": "u"})
    target.down(st, force=True)
    assert not st.worktree.exists()
    assert load_state(repo, "feat/x") is None
    _no_container_calls(runner)


def test_status_skips_docker_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 2b: status must never shell out to docker in host-worktree mode
    (the inherited local status → _container_state → `docker ps` would raise
    FileNotFoundError on a docker-less pod). container == 'n/a (host)'."""
    _, runner, target, st = _upped(tmp_path, monkeypatch)
    monkeypatch.setattr(target, "_pr", lambda state: None)  # no gh
    s = target.status(st)
    assert s["container"] == "n/a (host)"
    assert s["profile"] == "host"
    assert s["branch"] == "feat/x"
    assert s["pr"] is None
    _no_container_calls(runner)
