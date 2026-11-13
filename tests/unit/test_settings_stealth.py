"""Settings under stealth (spec 2026-11-04-repo-feature-settings R2 "stealth", R3 `init
--stealth`, R5's stealth rule, R24 "what reaches the target"; plan
2026-11-12-placement-resolver phase 4, task 2).

Target and tracking repos are LOCAL bare repos; nothing touches the network or a forge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationState
from fr.placement import stealth
from fr.settings import forge_allows, load_settings
from fr.settings.check import check_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, land_on_main
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files

__all__ = ["stealth_home"]


def _push_target_settings(track: Path, tmp_path: Path, text: str) -> None:
    clone = tmp_path / "push-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    (clone / "local--origin").mkdir()
    (clone / "local--origin/settings.yaml").write_text(text)
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "target settings")
    git(clone, "push", "-q", "origin", "main")


def _up(target: Path, track: Path, branch: str = "feat/s") -> IsolationState:
    ref = stealth.parse_ref(f"{track}@main")
    return HostWorktreeTarget(target).up(profile=None, branch=branch, stealth=ref)


def test_policy_comes_from_the_tracking_file_and_the_target_file_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target, track = stealth_pair(tmp_path)
    land_on_main(target, "artifacts:\n  gates: off\n")
    _push_target_settings(track, tmp_path, "placement: stealth\nartifacts:\n  test_plan: off\n")
    state = _up(target, track)
    effective = load_settings(state.worktree)
    assert effective.source == "stealth"
    assert effective.settings.placement == "stealth"
    assert effective.settings.artifacts.test_plan == "off"
    assert effective.settings.artifacts.gates == "on"  # the target's file is not read
    assert "ignored" in effective.ref_note
    assert "is ignored" in capsys.readouterr().err


def test_stealth_forces_the_quiet_forge_values(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    state = _up(target, track)  # no tracking file at all: defaults, then stealth's forge
    forge = load_settings(state.worktree).settings.forge
    assert (forge.labels, forge.comments, forge.issues, forge.pr_body) == (
        "off",
        "off",
        "off",
        "minimal",
    )
    for kind in ("labels", "comments", "issues"):
        assert not forge_allows(state.worktree, kind)


def test_check_and_run_start_refuse_an_explicit_contrary_forge_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "forge:\n  labels: on\n  issues: off\n")
    state = _up(target, track)
    problems = check_settings(state.worktree)
    assert [p.id for p in problems] == ["stealth-forge-explicit"]
    assert "forge.labels" in problems[0].message and "forge.issues" not in problems[0].message

    monkeypatch.chdir(state.worktree)
    result = CliRunner().invoke(
        app,
        ["settings", "check"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2
    assert "stealth-forge-explicit" in result.output
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2, result.output
    assert "forge.labels" in " ".join(result.output.split())


def test_init_stealth_writes_and_pushes_the_target_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    result = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert result.exit_code == 0, result.output
    assert "local--origin/settings.yaml" in tracked_files(track)
    text = git(track, "show", "main:local--origin/settings.yaml")
    assert "placement: stealth" in text.splitlines()
    assert "#  labels: off" in text and "#  pr_body: minimal" in text
    assert git(target, "status", "--porcelain").strip() == ""  # nothing in the target
    again = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert again.exit_code == 2 and "never overwrites" in " ".join(again.output.split())


def test_init_stealth_refuses_a_missing_branch_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    result = CliRunner().invoke(
        app,
        ["settings", "init", "--stealth", f"{track}@nope"],
        env={**os.environ, "FR_REPO_ROOT": str(target)},
    )
    assert result.exit_code == 2
    assert "no branch 'nope'" in " ".join(result.output.split())
    assert not (Path(os.environ["HOME"]) / ".cache").exists()
