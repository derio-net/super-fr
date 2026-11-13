"""Choosing stealth and the local record (spec 2026-11-04-repo-feature-settings R24 "chosen
per run", "the local record"; plan 2026-11-12-placement-resolver phase 4, task 1).

Target and tracking repos are LOCAL bare repos; nothing touches the network or a forge.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.artifacts.paths import artifact_root, space_for
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError, load_state
from fr.placement import stealth
from fr.settings import SettingsError, load_settings
from fr.settings.load import SERVABLE_PLACEMENTS

from tests.unit.settings_repo import git, land_on_main
from tests.unit.stealth_repo import stealth_home, stealth_pair

__all__ = ["stealth_home"]


def _home() -> Path:
    return Path(os.environ["HOME"])


def test_stealth_is_servable() -> None:
    assert "stealth" in SERVABLE_PLACEMENTS


def test_parse_ref_splits_at_the_last_at_sign() -> None:
    ref = stealth.parse_ref("git@example.com:me/track.git@feat/x")
    assert (ref.repo, ref.branch) == ("git@example.com:me/track.git", "feat/x")
    with pytest.raises(SettingsError, match="<repo>@<branch>"):
        stealth.parse_ref("git@example.com:me/track.git")
    with pytest.raises(SettingsError, match="<repo>@<branch>"):
        stealth.parse_ref("/tmp/track.git")


def test_target_dir_names() -> None:
    assert stealth.dir_name("https://example.com/acme/widget.git", Path("/x")) == (
        "example.com--acme--widget"
    )
    assert stealth.dir_name("git@example.com:acme/widget.git", Path("/x")) == (
        "example.com--acme--widget"
    )
    assert stealth.dir_name("/srv/git/widget.git", Path("/x")) == "local--widget"
    assert stealth.dir_name(None, Path("/home/me/widget")) == "local--widget"


def test_up_with_stealth_records_it_in_the_state_and_the_marker(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    ref = stealth.parse_ref(f"{track}@main")
    state = HostWorktreeTarget(target).up(profile=None, branch="feat/s", stealth=ref)
    assert state.placement == "stealth"
    assert state.tracking == ref.text
    assert load_state(target, "feat/s").tracking == ref.text  # type: ignore[union-attr]
    marker = json.loads((state.worktree / ".fr-isolation").read_text())
    assert marker["placement"] == "stealth"
    assert marker["tracking"] == {"ref": ref.text, "target": "local--origin"}

    wt = _home() / ".cache/fr/worktrees/work" / "stealth--local--track--main"
    assert (wt / ".git").exists()
    space = space_for(state.worktree)
    assert space.placement == "stealth"
    assert space.root == wt / "local--origin"
    assert space.feature == "feat__s"
    assert artifact_root(state.worktree) == wt / "local--origin/features/feat__s"


def test_old_markers_without_tracking_still_validate(tmp_path: Path) -> None:
    target, _ = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(profile=None, branch="feat/r")
    marker = json.loads((state.worktree / ".fr-isolation").read_text())
    assert "tracking" not in marker
    assert space_for(state.worktree).placement == "repo"


def test_run_start_with_stealth_records_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s", "--stealth", f"{track}@main"],
        env={**os.environ, "FR_REPO_ROOT": str(target), "FR_ISOLATION_TARGET": "worktree"},
    )
    assert result.exit_code == 0, result.output
    state = load_state(target, "feat/s")
    assert state is not None and state.placement == "stealth"
    assert state.tracking == f"{track}@main"
    marker = json.loads((state.worktree / ".fr-isolation").read_text())
    assert marker["tracking"]["ref"] == f"{track}@main"
    runs = artifact_root(state.worktree) / "docs/superpowers/runs"
    assert list(runs.glob("*.yaml")), "the cursor is in the tracking worktree"
    assert not (state.worktree / "docs/superpowers/runs").exists()


def test_up_from_the_tracking_repo_with_target_records_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    target, track = stealth_pair(tmp_path)
    clone = tmp_path / "track-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    monkeypatch.chdir(clone)
    result = CliRunner().invoke(
        app,
        ["isolation", "up", "--branch", "feat/t", "--target", str(target)],
        env={**os.environ, "FR_ISOLATION_TARGET": "worktree"},
    )
    assert result.exit_code == 0, result.output
    state = load_state(target, "feat/t")
    assert state is not None and state.placement == "stealth"
    assert state.tracking == f"{track}@main"
    assert space_for(state.worktree).root.name == "local--origin"


def test_stealth_in_repo_settings_refuses_naming_r24(tmp_path: Path) -> None:
    target, _ = stealth_pair(tmp_path)
    land_on_main(target, "placement: stealth\n")
    with pytest.raises(SettingsError) as caught:
        load_settings(target)
    message = str(caught.value)
    assert "R24" in message and "chosen per run" in message


def test_a_workspace_never_moves_between_tracking_refs(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    other = tmp_path / "other.git"
    git(tmp_path, "clone", "-q", "--bare", str(track), str(other))
    with pytest.raises(IsolationError, match="between tracking repos"):
        HostWorktreeTarget(target).up(
            profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{other}@main")
        )
