"""Mode from state (gh#569, spec 2026-09-23 §3.C).

A workspace records the mode it was created in; every command that addresses
an EXISTING workspace builds its backend from that record, never from
`FR_ISOLATION_TARGET`. The env var only selects the mode where no workspace
exists yet (`up`, gc discovery, verify-merge on a reaped branch).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.isolation import external as external_mod
from fr.isolation.external import ExternalTarget
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import LocalWorktreeDevcontainerTarget, subprocess_runner
from fr.isolation.routing import target_for_state
from fr.isolation.types import IsolationError, IsolationState

from tests.unit.test_isolation import FakeRunner, make_repo, make_repo_with_origin
from tests.unit.test_isolation_external import _write_marker


def _noop(_root: Path) -> None:
    return None


def _state(repo: Path, *, profile: str, target: str | None, branch: str = "feat/s"):
    return IsolationState(
        repo_root=repo.resolve(),
        branch=branch,
        worktree=repo.resolve(),
        profile=profile,
        created_at="2026-09-23T00:00:00+00:00",
        target=target,  # type: ignore[arg-type]
    )


# ---------- (a) each target's up writes its own mode ----------


def test_devcontainer_up_records_devcontainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    st = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner()).up(None, "feat/d")
    assert st.target == "devcontainer"


def test_host_worktree_up_records_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    st = HostWorktreeTarget(repo, runner=FakeRunner()).up(None, "feat/h")
    assert st.target == "worktree"


def test_external_up_records_external(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_marker(repo)
    st = ExternalTarget(repo, runner=subprocess_runner).up(None, "feat/x")
    assert st.target == "external"


# ---------- (b) target_for_state ignores the environment ----------


@pytest.mark.parametrize("env", [None, "devcontainer", "worktree", "bogus"])
def test_worktree_state_routes_to_host_worktree_whatever_the_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env: str | None
) -> None:
    if env is None:
        monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    else:
        monkeypatch.setenv("FR_ISOLATION_TARGET", env)
    repo = make_repo(tmp_path)
    t = target_for_state(
        _state(repo, profile="host", target="worktree"), runner=FakeRunner(), gc_spawner=_noop
    )
    assert type(t) is HostWorktreeTarget
    assert t.repo_root == repo.resolve()


@pytest.mark.parametrize("env", [None, "devcontainer", "worktree", "bogus"])
def test_devcontainer_state_routes_to_devcontainer_whatever_the_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env: str | None
) -> None:
    if env is None:
        monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    else:
        monkeypatch.setenv("FR_ISOLATION_TARGET", env)
    repo = make_repo(tmp_path)
    t = target_for_state(
        _state(repo, profile="dev", target="devcontainer"), runner=FakeRunner(), gc_spawner=_noop
    )
    assert type(t) is LocalWorktreeDevcontainerTarget
    assert t.repo_root == repo.resolve()


def test_routed_target_carries_the_runner_and_spawner(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    fake = FakeRunner()
    t = target_for_state(_state(repo, profile="host", target="worktree"), fake, _noop)
    assert isinstance(t, HostWorktreeTarget)
    assert t.run is fake and t._gc_spawner is _noop


@pytest.mark.parametrize(
    ("profile", "expected"),
    [("host", HostWorktreeTarget), ("dev", LocalWorktreeDevcontainerTarget)],
)
def test_legacy_state_without_target_infers_from_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, expected: type
) -> None:
    """An older fr on PATH rewrites the state file and drops `target` — so
    inference from the profile sentinel is permanent, not transitional."""
    monkeypatch.setenv("FR_ISOLATION_TARGET", "bogus")
    repo = make_repo(tmp_path)
    t = target_for_state(_state(repo, profile=profile, target=None), FakeRunner(), _noop)
    assert type(t) is expected


# ---------- (c) external fails closed without a corroborated marker ----------


def test_external_state_without_marker_fails_closed_naming_the_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(external_mod, "_container_evidence", lambda: True)
    repo = make_repo(tmp_path)  # no marker
    with pytest.raises(IsolationError, match="feat/ext"):
        target_for_state(
            _state(repo, profile="external", target="external", branch="feat/ext"),
            FakeRunner(),
            _noop,
        )


def test_external_state_without_container_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(external_mod, "_container_evidence", lambda: False)
    repo = make_repo(tmp_path)
    _write_marker(repo, branch="feat/ext")
    with pytest.raises(IsolationError, match="feat/ext"):
        target_for_state(
            _state(repo, profile="external", target="external", branch="feat/ext"),
            subprocess_runner,
            _noop,
        )


@pytest.mark.parametrize("target", ["external", None])
def test_external_state_with_marker_and_evidence_is_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str | None
) -> None:
    monkeypatch.setattr(external_mod, "_container_evidence", lambda: True)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    repo = make_repo(tmp_path)
    _write_marker(repo, branch="feat/ext")
    t = target_for_state(
        _state(repo, profile="external", target=target, branch="feat/ext"),
        subprocess_runner,
        _noop,
    )
    assert type(t) is ExternalTarget
    assert t.repo_root == repo.resolve()
