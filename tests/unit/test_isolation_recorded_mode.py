"""Mode from state (gh#569, spec 2026-09-23 §3.C): IsolationState.target + recorded_mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.isolation.types import (
    IsolationState,
    load_state,
    recorded_mode,
    save_state,
    state_path,
)

from tests.unit.test_isolation import make_repo


def _state(repo: Path, *, profile: str, target: str | None = None) -> IsolationState:
    return IsolationState.model_validate(
        {
            "repo_root": repo,
            "branch": "feat/x",
            "worktree": repo.parent / "wt",
            "profile": profile,
            "created_at": "2026-09-23T00:00:00Z",
            "target": target,
        }
    )


@pytest.mark.parametrize(
    ("target", "profile"),
    [
        ("devcontainer", "host"),
        ("worktree", "dev"),
        ("external", "host"),
        ("worktree", "external"),
    ],
)
def test_recorded_target_wins_over_profile(tmp_path: Path, target: str, profile: str) -> None:
    assert recorded_mode(_state(tmp_path, profile=profile, target=target)) == target


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("host", "worktree"),
        ("external", "external"),
        ("dev", "devcontainer"),
        ("admin", "devcontainer"),
    ],
)
def test_legacy_state_infers_mode_from_profile(tmp_path: Path, profile: str, expected: str) -> None:
    st = _state(tmp_path, profile=profile)
    assert st.target is None
    assert recorded_mode(st) == expected


def test_target_round_trips_through_state_file(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = _state(repo, profile="host", target="worktree")
    save_state(st)
    loaded = load_state(repo, "feat/x")
    assert loaded == st
    assert loaded is not None and loaded.target == "worktree"


def test_state_file_without_target_key_loads_as_none(tmp_path: Path) -> None:
    """A state file written by an older fr (no `target` key) still loads."""
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = _state(repo, profile="host", target="worktree")
    p = save_state(st)
    raw = json.loads(p.read_text())
    del raw["target"]
    p.write_text(json.dumps(raw))
    assert p == state_path(repo, "feat/x")
    loaded = load_state(repo, "feat/x")
    assert loaded is not None
    assert loaded.target is None
    assert recorded_mode(loaded) == "worktree"


def test_unknown_target_value_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _state(tmp_path, profile="dev", target="host")


def test_an_unknown_key_is_tolerated_so_an_older_fr_can_read_a_newer_file(tmp_path: Path) -> None:
    # §3.C: the state file is shared across fr versions on one host. Adding
    # `target` is only safe because IsolationState ignores keys it does not know;
    # `extra="forbid"` here would make every older fr refuse a newer file.
    repo = make_repo(tmp_path)
    payload = _state(repo, profile="dev", target="devcontainer").model_dump(mode="json")
    payload["future_field"] = 1
    assert IsolationState.model_validate(payload).target == "devcontainer"


def test_list_states_skips_an_unparseable_state_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # One bad file (a newer fr's unknown mode) must not blind status/gc to every
    # other workspace; the addressed workspace itself still fails closed via load_state.
    from fr.isolation.types import list_states

    repo = make_repo(tmp_path)
    good = _state(repo, profile="dev", target="devcontainer")
    save_state(good)
    bad = state_path(repo, "feat/future")
    bad.write_text(
        json.dumps({**good.model_dump(mode="json"), "branch": "feat/future", "target": "remote"})
    )
    assert [s.branch for s in list_states(repo)] == ["feat/x"]
    assert "feat__future.json" in capsys.readouterr().err
    with pytest.raises(ValueError):
        load_state(repo, "feat/future")
