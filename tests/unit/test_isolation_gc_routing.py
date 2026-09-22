"""gc follows each workspace's recorded mode, and the background gc keeps its
spawner's mode (gh#569, spec 2026-09-23 §3.C).

gc is host-wide: the sweeping target's class is whatever mode the triggering
command ran in, not the mode of each workspace it reaps. Building the reap
sibling as ``type(self)`` meant a host-worktree sweep tore a devcontainer
workspace down through the docker-less ``_teardown_container`` no-op — the
#354 container leak by another route.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation import local as local_mod
from fr.isolation import routing
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import LocalWorktreeDevcontainerTarget, _detached_gc_spawn
from fr.isolation.types import IsolationState, load_state, save_state

from tests.unit.test_isolation import FakeRunner, make_repo_with_origin

_MERGED = '{"state": "MERGED", "url": "u"}'


def _devcontainer_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(pr_by_branch={branch: _MERGED}, stdout={"docker": "cid running"})
    st = LocalWorktreeDevcontainerTarget(repo, runner=runner).up(None, branch)
    assert st.target == "devcontainer"
    return repo, runner, st


def test_host_worktree_sweep_reaps_a_devcontainer_workspace_through_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, st = _devcontainer_workspace(tmp_path, monkeypatch, "feat/m")
    sweeper = HostWorktreeTarget(repo, runner=runner)

    by_branch = {a.branch: a for a in sweeper.gc()}

    assert by_branch["feat/m"].action == "reaped", by_branch["feat/m"]
    docker = runner.argv_for("docker")
    assert ["docker", "stop", "cid"] in docker, docker
    assert ["docker", "rm", "cid"] in docker, docker
    assert load_state(repo, "feat/m") is None


def test_dry_run_probe_is_built_from_the_recorded_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, st = _devcontainer_workspace(tmp_path, monkeypatch, "feat/p")
    built: list[tuple[str, type]] = []
    real = routing.target_for_state

    def _spy(state, runner, gc_spawner):
        t = real(state, runner, gc_spawner)
        built.append((state.branch, type(t)))
        return t

    monkeypatch.setattr(routing, "target_for_state", _spy)
    actions = {a.branch: a for a in HostWorktreeTarget(repo, runner=runner).gc(dry_run=True)}

    assert actions["feat/p"].action == "would-reap", actions["feat/p"]
    assert ("feat/p", LocalWorktreeDevcontainerTarget) in built


def test_worktree_sweep_never_reaps_an_external_recorded_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    state = IsolationState(
        repo_root=repo.resolve(),
        branch="feat/ext",
        worktree=repo.resolve(),
        profile="external",
        created_at="2026-09-23T00:00:00+00:00",
        target="external",
    )
    save_state(state)
    runner = FakeRunner(pr_by_branch={"feat/ext": _MERGED})
    sweeper = HostWorktreeTarget(repo, runner=runner)

    for dry_run in (True, False):
        action = sweeper._reap_or_classify(str(repo), state, "merged", dry_run)
        assert (action.verdict, action.action) == ("external", "skipped"), action
        assert "preparer" in (action.detail or "")
    assert load_state(repo, "feat/ext") is not None
    assert repo.is_dir()


# ---------- the background gc keeps its spawner's mode ----------


@pytest.mark.parametrize(
    ("cls", "mode", "ambient"),
    [
        (HostWorktreeTarget, "worktree", None),
        (HostWorktreeTarget, "worktree", "devcontainer"),
        (LocalWorktreeDevcontainerTarget, "devcontainer", None),
        (LocalWorktreeDevcontainerTarget, "devcontainer", "worktree"),
    ],
)
def test_spawned_gc_carries_the_spawning_targets_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cls: type,
    mode: str,
    ambient: str | None,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    if ambient is None:
        monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    else:
        monkeypatch.setenv("FR_ISOLATION_TARGET", ambient)
    repo, _origin = make_repo_with_origin(tmp_path)
    captured: list[dict] = []

    def _popen(argv, **kwargs):
        captured.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 0)

    target = cls(repo, gc_spawner=_detached_gc_spawn)  # construction runs git
    # Patched only now: `subprocess` is the shared module, so run() would see it.
    monkeypatch.setattr(local_mod.subprocess, "Popen", _popen)
    target._spawn_gc()

    (call,) = captured
    assert call["argv"][-3:-1] == ["gc", "--repo"]
    assert call["env"]["FR_ISOLATION_TARGET"] == mode
    assert call["env"].get("HOME") == str(tmp_path / "home"), "rest of env inherited"


def test_detached_gc_spawn_always_pins_the_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p2-f2: the mode is a required argument, so no caller (a wrapper,
    a partial) can drop it and hand the child the caller's env by accident."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "devcontainer")
    captured: list[dict] = []
    monkeypatch.setattr(local_mod.subprocess, "Popen", lambda argv, **kw: captured.append(kw))
    _detached_gc_spawn(tmp_path, "worktree")
    (kw,) = captured
    assert kw["env"]["FR_ISOLATION_TARGET"] == "worktree"


# ---------- review p2-f1: the stale-state reap asks the WORKSPACE's mode ----------


def test_host_worktree_sweep_defers_a_devcontainer_stale_state_when_docker_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A devcontainer workspace whose worktree is gone may still own a running
    container. A host-worktree sweeper must ask the devcontainer mode's
    `_stale_state_reapable` (a healthy `docker ps`), not its own hard-coded True —
    dropping the state on a failed docker query is the #354 leak."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / "repo" / "feat__gone"
    state = IsolationState(
        repo_root=repo.resolve(),
        branch="feat/gone",
        worktree=gone,
        profile="dev",
        created_at="2026-09-23T00:00:00+00:00",
        target="devcontainer",
    )
    save_state(state)
    runner = FakeRunner(fail_on="ps")  # every `docker ps` fails
    sweeper = HostWorktreeTarget(repo, runner=runner)

    by_branch = {a.branch: a for a in sweeper.gc()}

    action = by_branch["feat/gone"]
    assert (action.verdict, action.action) == ("orphan", "skipped"), action
    assert "docker unavailable" in (action.detail or "")
    assert load_state(repo, "feat/gone") is not None


def test_host_worktree_sweep_still_retires_its_own_stale_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    state = IsolationState(
        repo_root=repo.resolve(),
        branch="feat/hgone",
        worktree=tmp_path / "nowhere" / "feat__hgone",
        profile="host",
        created_at="2026-09-23T00:00:00+00:00",
        target="worktree",
    )
    save_state(state)
    sweeper = HostWorktreeTarget(repo, runner=FakeRunner(fail_on="ps"))
    by_branch = {a.branch: a for a in sweeper.gc()}
    assert by_branch["feat/hgone"].action == "reaped", by_branch["feat/hgone"]
    assert load_state(repo, "feat/hgone") is None


# ---------- review p2-f2: the mode is part of the spawner contract ----------


@pytest.mark.parametrize(
    ("profile", "target", "mode"),
    [("host", "worktree", "worktree"), ("dev", "devcontainer", "devcontainer")],
)
def test_routed_target_hands_its_mode_to_any_spawner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, target: str, mode: str
) -> None:
    from fr.commands import isolation_cmd

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    spawned: list[tuple[Path, str]] = []
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda root, m: spawned.append((root, m)))
    state = IsolationState(
        repo_root=repo.resolve(),
        branch="feat/sp",
        worktree=repo.resolve(),
        profile=profile,
        created_at="2026-09-23T00:00:00+00:00",
        target=target,  # type: ignore[arg-type]
    )
    t = isolation_cmd._target_for(repo, state)
    t._spawn_gc()  # type: ignore[attr-defined]
    assert spawned == [(repo.resolve(), mode)]
