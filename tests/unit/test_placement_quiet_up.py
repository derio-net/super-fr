"""Quiet at `fr isolation up` and `fr run start`: the fetch, the reachability refusal and
the sticky placement (spec 2026-11-04-repo-feature-settings R23 "the switch", "sticky";
plan 2026-11-12-placement-resolver phase 3, task 2).

Origins are LOCAL bare repos; an unreachable origin is a path that does not exist.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.artifacts.paths import space_for
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError, IsolationState
from fr.settings import SettingsError

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch, push_quiet_switch


def _target(repo: Path) -> HostWorktreeTarget:
    return HostWorktreeTarget(repo)


def _quiet_origin(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    push_quiet_switch(repo, QUIET)
    # Only the fetch at `up` may tell this clone about the switch.
    git(repo, "update-ref", "-d", "refs/remotes/origin/fr")
    return repo


def _old_quiet_origin(tmp_path: Path) -> Path:
    """A quiet repo whose switch is only the old `fr:settings.yaml` (no fr-config yet): the
    transition window, so the tests using it are marked `s1_open` (spec
    2026-11-28-s1-followups R10)."""
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    git(repo, "update-ref", "-d", "refs/remotes/origin/fr")
    return repo


def _unreachable(repo: Path, tmp_path: Path) -> None:
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))


def test_up_fetches_the_switch_and_records_quiet(tmp_path: Path) -> None:
    repo = _quiet_origin(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/q")
    assert state.placement == "quiet"
    marker = json.loads((state.worktree / ".fr-isolation").read_text())
    assert marker["placement"] == "quiet"
    assert git(repo, "rev-parse", "--verify", "refs/remotes/origin/fr").strip()
    assert space_for(state.worktree).placement == "quiet"


def test_up_records_repo_when_origin_has_no_fr_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/r")
    assert state.placement == "repo"
    marker = json.loads((state.worktree / ".fr-isolation").read_text())
    assert marker["placement"] == "repo"


def test_up_refuses_an_unreachable_origin_before_any_worktree(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _unreachable(repo, tmp_path)
    with pytest.raises(IsolationError) as caught:
        _target(repo).up(profile=None, branch="feat/u")
    message = str(caught.value)
    assert "origin" in message and "git remote -v" in message
    assert not (Path(os.environ["HOME"]) / ".cache/fr/worktrees/work/feat__u").exists()


def test_up_no_fetch_reads_the_last_fetched_switch_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_repo(tmp_path)
    push_quiet_switch(repo, QUIET)  # origin/fr is fetched (the push updated it)
    _unreachable(repo, tmp_path)
    state = _target(repo).up(profile=None, branch="feat/n", no_fetch=True)
    assert state.placement == "quiet"
    assert "--no-fetch" in capsys.readouterr().err


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
def test_a_deleted_fr_branch_makes_the_workspace_refuse_naming_both(tmp_path: Path) -> None:
    repo = _old_quiet_origin(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/q")
    git(repo, "push", "-q", "origin", "--delete", "fr")  # also drops origin/fr locally
    with pytest.raises(SettingsError) as caught:
        space_for(state.worktree)
    message = str(caught.value)
    assert "placement: quiet" in message and "placement: repo" in message


def test_a_switch_appearing_under_a_repo_workspace_refuses_too(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/r")
    push_quiet_switch(repo, QUIET)
    with pytest.raises(SettingsError, match="placement: repo.*placement: quiet"):
        space_for(state.worktree)


def test_a_state_file_written_before_placement_still_loads() -> None:
    old = {
        "repo_root": "/r",
        "branch": "feat/x",
        "worktree": "/w",
        "profile": "host",
        "target": "worktree",
        "created_at": "2026-11-01T00:00:00+00:00",
        "sessions": [],
        "base_sha": None,
    }
    state = IsolationState.model_validate_json(json.dumps(old))
    assert state.placement is None


def test_run_start_refuses_an_unreachable_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    repo = make_repo(tmp_path)
    monkeypatch.chdir(repo)  # never the checkout under test: it may be a workspace itself
    _unreachable(repo, tmp_path)
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s"],
        env={**os.environ, "FR_REPO_ROOT": str(repo), "FR_ISOLATION_TARGET": "worktree"},
    )
    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert "origin is unreachable" in flat and "git remote -v" in flat


def test_run_start_in_an_existing_workspace_fetches_and_refuses_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`up` already ran, so only `run start`'s own fetch can notice the origin is gone."""
    from fr.cli import app
    from typer.testing import CliRunner

    repo = make_repo(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/s")
    monkeypatch.chdir(state.worktree)
    _unreachable(repo, tmp_path)
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2, result.output
    assert "origin is unreachable" in " ".join(result.output.split())


def test_up_again_on_a_quiet_workspace_with_a_plan_needs_no_validator_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p4-r4: a quiet feature's plans are on `fr`, so the product branch owes no
    scripts/validate-plans.sh and re-entering the workspace does not demand one."""
    from fr.cli import app
    from typer.testing import CliRunner

    repo = _quiet_origin(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    made = CliRunner().invoke(
        app,
        ["plan", "create", "--slug", "2026-11-12-q", "--target-repo", "derio-net/q"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert made.exit_code == 0, made.output
    assert not (state.worktree / "scripts/validate-plans.sh").exists()
    assert _target(repo).up(profile=None, branch="feat/q").worktree == state.worktree


# --- S1 (spec 2026-11-19-event-driven-a-la-carte §B, R5): entering fetches, never pushes ---
#
# Plan-journal decision p2-create-at-init-and-migration: fr creates `fr-config` only at the
# migration and at `fr settings init`. `up` and `run start` adopt one that exists.


def _origin_heads(tmp_path: Path) -> str:
    return git(tmp_path / "origin.git", "for-each-ref", "--format=%(refname) %(objectname)")


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
def test_up_on_an_old_quiet_repo_pushes_nothing_and_names_the_remedies(tmp_path: Path) -> None:
    """A quiet repo whose switch is only the old root settings.yaml on `fr`: `up` reads it
    (R13) and pushes nothing; a configuration read refuses, naming how to create the space."""
    from fr.config.space import config_space

    repo = _old_quiet_origin(tmp_path)
    before = _origin_heads(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/q")
    assert state.placement == "quiet"
    assert _origin_heads(tmp_path) == before
    assert git(tmp_path / "origin.git", "branch", "--list", "fr-config").strip() == ""
    home = Path(os.environ["HOME"])
    assert not (home / ".cache/fr/worktrees/work/fr-config").exists()
    with pytest.raises(SettingsError) as caught:
        config_space(state.worktree).at_default("settings")
    message = str(caught.value)
    assert "fr migrate artifacts --yes" in message and "fr settings init" in message


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
def test_up_adopts_an_existing_fr_config_into_its_worktree(tmp_path: Path) -> None:
    from fr.config.space import config_space

    from tests.unit.test_placement_quiet import push_config_branch

    repo = _old_quiet_origin(tmp_path)
    push_config_branch(repo, QUIET)
    git(repo, "update-ref", "-d", "refs/remotes/origin/fr-config")
    before = _origin_heads(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/q")
    assert _origin_heads(tmp_path) == before
    wt = Path(os.environ["HOME"]) / ".cache/fr/worktrees/work/fr-config"
    assert git(wt, "symbolic-ref", "--short", "HEAD").strip() == "fr-config"
    assert (wt / ".fr" / "settings.yaml").read_text() == QUIET
    space = config_space(state.worktree)
    assert space.checkout == wt and space.at_default("settings") == QUIET


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
@pytest.mark.parametrize("with_config", [False, True], ids=["old-switch", "fr-config"])
def test_up_no_fetch_never_pushes(tmp_path: Path, with_config: bool) -> None:
    from tests.unit.test_placement_quiet import push_config_branch

    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    if with_config:
        push_config_branch(repo, QUIET)
    before = _origin_heads(tmp_path)
    state = _target(repo).up(profile=None, branch="feat/n", no_fetch=True)
    assert state.placement == "quiet"
    assert _origin_heads(tmp_path) == before


# --- review p2-r2: fr adopts only a configuration branch (orphan, tree `.fr/`) -----------


def _push_fr_config_from_main(repo: Path, keep_product: bool) -> None:
    """An `fr-config` on origin cut from `main` (shares the product's history); with
    *keep_product* its tree still holds the product's files, else only `.fr/`."""
    git(repo, "checkout", "-q", "-b", "fr-config", "main")
    if not keep_product:
        git(repo, "rm", "-rqf", ".")
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "settings.yaml").write_text(QUIET)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "not a configuration branch")
    git(repo, "push", "-q", "origin", "fr-config")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-q", "-D", "fr-config")


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
@pytest.mark.parametrize(
    ("keep_product", "why"),
    [(True, "README.md"), (False, "shares history")],
    ids=["product-tree", "product-history"],
)
def test_up_refuses_to_adopt_a_foreign_fr_config(
    tmp_path: Path, keep_product: bool, why: str
) -> None:
    repo = _old_quiet_origin(tmp_path)
    _push_fr_config_from_main(repo, keep_product)
    with pytest.raises(IsolationError) as caught:
        _target(repo).up(profile=None, branch="feat/q")
    message = str(caught.value)
    assert "fr-config" in message and why in message
    assert not (Path(os.environ["HOME"]) / ".cache/fr/worktrees/work/fr-config").exists()


@pytest.mark.s1_open  # the old switch alone: the transition window (R10)
def test_fr_never_pushes_an_unrelated_local_fr_config(tmp_path: Path) -> None:
    """A local `fr-config` cut from the product, origin having none: creating the space
    (`fr settings init --quiet` on an old quiet repo) refuses rather than push it."""
    from fr.placement.quiet import ensure_config_branch

    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    git(repo, "branch", "-q", "fr-config", "main")
    with pytest.raises(SettingsError) as caught:
        ensure_config_branch(repo)
    assert "fr-config" in str(caught.value)
    assert git(tmp_path / "origin.git", "branch", "--list", "fr-config").strip() == ""
