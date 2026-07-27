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

from tests.unit.test_isolation import (
    _commit_in_worktree,
    _land_on_origin_main,
    make_repo,
    make_repo_with_origin,
)


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


# ---------- gc: the same reconciler, minus every docker step (#423) ----------


class GhRecordingRunner(RecordingRunner):
    """RecordingRunner + a faked `gh pr view` — the sandbox has no PR host, and
    gc classifies on the PR state. Everything else (git especially) still hits
    the real binary, so a stray docker/devcontainer call is still caught."""

    def __init__(self, pr_by_branch: dict[str, str] | None = None) -> None:
        super().__init__()
        self.pr_by_branch = pr_by_branch or {}

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        if argv[0:3] == ["gh", "pr", "view"]:
            self.calls.append(list(argv))
            self.captures.append(capture)
            body = self.pr_by_branch.get(argv[3], "")
            return subprocess.CompletedProcess(argv, 0 if body else 1, stdout=body, stderr="")
        return super().__call__(argv, cwd=cwd, check=check, capture=capture)


def _gc_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pr_by_branch: dict[str, str] | None = None
) -> tuple[Path, GhRecordingRunner, HostWorktreeTarget]:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    runner = GhRecordingRunner(pr_by_branch)
    return repo, runner, HostWorktreeTarget(repo, runner=runner)


def test_gc_reaps_merged_workspace_without_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance signal of #423: a docker-less host reaps its own merged
    workspace. The whole sweep must not touch docker or devcontainer."""
    repo, runner, target = _gc_env(
        tmp_path, monkeypatch, {"feat/merged": '{"state": "MERGED", "url": "u"}'}
    )
    st = target.up(profile=None, branch="feat/merged")

    (action,) = [a for a in target.gc() if a.branch == "feat/merged"]
    assert action.verdict == "merged" and action.action == "reaped"
    assert not st.worktree.exists()
    assert load_state(repo, "feat/merged") is None
    _no_container_calls(runner)


def test_gc_skips_open_pr_and_no_pr_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target = _gc_env(
        tmp_path, monkeypatch, {"feat/open": '{"state": "OPEN", "url": "u"}'}
    )
    open_st = target.up(profile=None, branch="feat/open")
    nopr_st = target.up(profile=None, branch="feat/nopr")

    by_branch = {a.branch: a for a in target.gc()}
    assert by_branch["feat/open"].verdict == "open"
    assert by_branch["feat/open"].action == "skipped"
    assert by_branch["feat/nopr"].verdict == "no-pr"
    assert by_branch["feat/nopr"].action == "warned"
    assert open_st.worktree.is_dir() and nopr_st.worktree.is_dir()
    _no_container_calls(runner)


def test_gc_dry_run_mutates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target = _gc_env(
        tmp_path, monkeypatch, {"feat/merged": '{"state": "MERGED", "url": "u"}'}
    )
    st = target.up(profile=None, branch="feat/merged")

    (action,) = [a for a in target.gc(dry_run=True) if a.branch == "feat/merged"]
    assert action.action == "would-reap"
    assert st.worktree.is_dir()
    assert load_state(repo, "feat/merged") is not None


def test_gc_never_reports_dangling_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """There are no `vsc-*` images without docker — the image sweep is skipped,
    not faked, so `docker images` is never even invoked."""
    _repo, runner, target = _gc_env(tmp_path, monkeypatch)
    target.up(profile=None, branch="feat/x")
    assert not [a for a in target.gc() if a.verdict == "dangling-image"]
    _no_container_calls(runner)


def test_gc_reaps_stale_state_record_without_docker_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_stale_state_reapable` is unconditionally True here: with no containers
    by construction there is no docker view to distrust, so the record is
    retired instead of deferring forever on a host that has no daemon."""
    import shutil

    repo, runner, target = _gc_env(tmp_path, monkeypatch)
    st = target.up(profile=None, branch="feat/gone")
    shutil.rmtree(st.worktree)

    (action,) = [a for a in target.gc() if a.branch == "feat/gone"]
    assert action.verdict == "orphan" and action.action == "reaped"
    assert load_state(repo, "feat/gone") is None
    _no_container_calls(runner)


def _gc_env_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, GhRecordingRunner, HostWorktreeTarget]:
    """gc env with a real bare origin + `origin/HEAD`, so the merged-by-content
    check resolves a real remote ref without docker anywhere in sight."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        ],
        check=True,
    )
    runner = GhRecordingRunner()
    return repo, runner, HostWorktreeTarget(repo, runner=runner)


def test_gc_reaps_content_merged_workspace_without_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A squash-merged branch has no discoverable PR and is not an ancestor of
    main, but its content IS on main — the classifier that keeps a docker-less
    host from warning about the same workspace forever."""
    repo, runner, target = _gc_env_origin(tmp_path, monkeypatch)
    st = target.up(profile=None, branch="feat/work")
    _commit_in_worktree(st.worktree, "feature.txt", "the feature\n")
    _land_on_origin_main(repo, "feature.txt", "the feature\n")

    (action,) = [a for a in target.gc() if a.branch == "feat/work"]
    assert action.verdict == "merged-by-content" and action.action == "reaped"
    assert not st.worktree.exists()
    assert load_state(repo, "feat/work") is None
    _no_container_calls(runner)


def test_gc_does_not_reap_content_merged_workspace_with_a_dirty_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same workspace, plus uncommitted work: reaping would destroy it, so the
    clean-tree guard demotes the verdict to a warning."""
    repo, runner, target = _gc_env_origin(tmp_path, monkeypatch)
    st = target.up(profile=None, branch="feat/work")
    _commit_in_worktree(st.worktree, "feature.txt", "the feature\n")
    _land_on_origin_main(repo, "feature.txt", "the feature\n")
    (st.worktree / "uncommitted.txt").write_text("work in progress\n")

    (action,) = [a for a in target.gc() if a.branch == "feat/work"]
    assert action.verdict == "no-pr" and action.action == "warned"
    assert (st.worktree / "uncommitted.txt").is_file()
    _no_container_calls(runner)


def test_gc_ignores_unrelated_git_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _runner, target = _gc_env(tmp_path, monkeypatch)
    scratch = tmp_path / "scratch"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(scratch), "-b", "other/manual"],
        check=True,
    )
    assert not [a for a in target.gc() if a.worktree == str(scratch)]
    assert scratch.is_dir()


# ---------- opportunistic gc triggers (#423) ----------


def test_up_and_down_fire_the_gc_spawner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sweep is no longer docker-coupled, so this mode participates in the
    same opportunistic reconciliation as devcontainer mode — that is what bounds
    the leak on a pod whose session exits before its PR merges."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    spawns: list[Path] = []
    target = HostWorktreeTarget(
        repo, runner=GhRecordingRunner(), gc_spawner=lambda root: spawns.append(root)
    )

    st = target.up(profile=None, branch="feat/x")
    assert spawns == [target.repo_root], "up fires exactly one background sweep"
    target.down(st, force=False)
    assert len(spawns) == 2, "down fires exactly one background sweep"
