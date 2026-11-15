"""A devcontainer profile that still installs fr-vk is refused (spec
2026-11-14-retire-vibekanban R4).

The refusal lives in the one shared `devcontainer up` path, so `up`, `rebuild`
and exec's resume all reach it. Every devcontainer call rides test_isolation's
FakeRunner; git hits real throwaway repos. Nothing here needs Docker.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationError, load_state

from tests.unit.test_isolation import FakeRunner, _upped, make_repo_with_origin

_SEGMENT = "--with 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr-vk'"
_STALE = (
    "uv tool install --force 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr' "
    f"{_SEGMENT}"
)


def _dc_up(runner: FakeRunner) -> list[list[str]]:
    return [c for c in runner.argv_for("devcontainer") if c[1:2] == ["up"]]


def _write_profile(config: Path, post_create: str) -> None:
    config.write_text(json.dumps({"image": "x", "postCreateCommand": post_create}) + "\n")


def _commit_all(repo: Path, msg: str) -> None:
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", msg], check=True)
    subprocess.run([*git, "push", "-q", "origin", "main"], check=True)


def _assert_refusal(text: str, config: Path) -> None:
    assert str(config) in text
    assert "subdirectory=packages/fr-vk" in text
    assert "VK support was removed" in text
    assert "default branch" in text


def test_up_refuses_a_profile_that_installs_fr_vk_after_recording_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    _write_profile(repo / ".devcontainer" / "dev" / "devcontainer.json", _STALE)
    _commit_all(repo, "stale profile")
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    with pytest.raises(IsolationError) as exc:
        target.up(None, "feat/x")

    state = load_state(repo, "feat/x")
    assert state is not None
    _assert_refusal(str(exc.value), state.worktree / ".devcontainer" / "dev" / "devcontainer.json")
    assert "fr isolation up --branch feat/x" in str(exc.value)
    assert _dc_up(runner) == []


def test_rebuild_refuses_the_same_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo, runner, target, st = _upped(tmp_path, monkeypatch)
    config = st.worktree / ".devcontainer" / "dev" / "devcontainer.json"
    _write_profile(config, _STALE)

    with pytest.raises(IsolationError) as exc:
        target.rebuild(st)

    _assert_refusal(str(exc.value), config)
    assert "may already have been removed" not in str(exc.value)
    assert _dc_up(runner) == []


def test_exec_resume_refuses_the_same_profile_without_the_rebuild_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _runner, _target, st = _upped(tmp_path, monkeypatch)
    config = st.worktree / ".devcontainer" / "dev" / "devcontainer.json"
    _write_profile(config, _STALE)
    runner = FakeRunner(stdout={"docker": "cid1 exited"})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    with pytest.raises(IsolationError) as exc:
        target.exec(st, ["echo", "hi"])

    _assert_refusal(str(exc.value), config)
    assert "recreates it" not in str(exc.value)
    assert "could not resume" not in str(exc.value)
    assert _dc_up(runner) == []
    assert not [c for c in runner.argv_for("devcontainer") if c[1:2] == ["exec"]]


def test_a_customised_post_create_still_naming_the_segment_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, runner, target, st = _upped(tmp_path, monkeypatch)
    config = st.worktree / ".devcontainer" / "dev" / "devcontainer.json"
    _write_profile(
        config,
        "set -e; pip install foo && uv tool install fr "
        "--with git+https://example.invalid/fork.git#subdirectory=packages/fr-vk; echo ok",
    )

    with pytest.raises(IsolationError) as exc:
        target.rebuild(st)

    _assert_refusal(str(exc.value), config)
    assert _dc_up(runner) == []


def test_a_clean_profile_proceeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo, runner, target, st = _upped(tmp_path, monkeypatch)
    _write_profile(
        st.worktree / ".devcontainer" / "dev" / "devcontainer.json",
        "uv tool install 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr'",
    )

    target.rebuild(st)

    assert len(_dc_up(runner)) == 1


def test_an_absent_config_falls_through_to_devcontainer_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, runner, target, st = _upped(tmp_path, monkeypatch)
    (st.worktree / ".devcontainer" / "dev" / "devcontainer.json").unlink()

    target.rebuild(st)

    assert len(_dc_up(runner)) == 1


def test_an_undecodable_config_falls_through_to_devcontainer_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, runner, target, st = _upped(tmp_path, monkeypatch)
    (st.worktree / ".devcontainer" / "dev" / "devcontainer.json").write_bytes(b"\xff\xfe{\x80}")

    target.rebuild(st)

    assert len(_dc_up(runner)) == 1
