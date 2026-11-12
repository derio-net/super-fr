"""Quiet's edges, from the phase-3 review (spec 2026-11-04-repo-feature-settings R23):
a workspace older than quiet is sticky `repo` (p3-r5), `run start --no-fetch` (p3-r7), a
local `fr` unrelated to origin's is never adopted (p3-r9), and `apply --to` reads only the
switch (p3-r10).

Origins are LOCAL bare repos; an unreachable origin is a path that does not exist.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.artifacts.paths import space_for
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError, carried_state, load_state, save_state
from fr.placement.quiet import ensure_worktree
from fr.settings import SettingsError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch


def _invoke(cwd: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "VK_REPO_ROOT": str(cwd), "FR_ISOLATION_TARGET": "worktree"}
    result = CliRunner().invoke(app, list(argv), env=env)
    return result.exit_code, " ".join(result.output.split())


# --- p3-r5: a marker or state with no `placement` key is `repo` -------------------------


def test_a_marker_written_before_quiet_refuses_once_the_switch_appears(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/old")
    marker = state.worktree / ".fr-isolation"
    data = json.loads(marker.read_text())
    del data["placement"]  # as an fr that predates plan 3 wrote it
    marker.write_text(json.dumps(data))
    push_fr_branch(repo, QUIET)
    with pytest.raises(SettingsError, match="placement: repo.*placement: quiet"):
        space_for(state.worktree)


def test_a_state_written_before_quiet_refuses_at_up_naming_both(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/old")
    save_state(state.model_copy(update={"placement": None}))
    assert load_state(repo, "feat/old").placement is None  # type: ignore[union-attr]
    with pytest.raises(IsolationError, match="placement: repo.*placement: quiet"):
        carried_state(repo, "feat/old", state.worktree, "host", "worktree", placement="quiet")


# --- p3-r7: `fr run start --no-fetch` -------------------------------------------------


def test_run_start_no_fetch_reads_the_last_fetched_switch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/s")
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    code, out = _invoke(state.worktree, "run", "start", "fr-goal", "--branch", "feat/s")
    assert code == 2, out
    assert "fr run start --no-fetch" in out and "fr isolation up --no-fetch" not in out
    code, out = _invoke(
        state.worktree, "run", "start", "fr-goal", "--branch", "feat/s", "--no-fetch"
    )
    assert code == 0, out
    assert "--no-fetch" in out


# --- p3-r9: a local `fr` unrelated to origin/fr is never adopted ------------------------


def _unrelated_local_fr(repo: Path) -> None:
    back = git(repo, "symbolic-ref", "--short", "HEAD").strip()
    git(repo, "checkout", "-q", "--orphan", "fr")
    git(repo, "rm", "-rfq", ".")
    (repo / "other.md").write_text("not origin's fr\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "unrelated")
    git(repo, "checkout", "-q", back)


def test_an_unrelated_local_fr_branch_is_refused_not_adopted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    _unrelated_local_fr(repo)
    with pytest.raises(SettingsError, match="neither an ancestor nor a descendant"):
        ensure_worktree(repo)


def test_a_local_fr_behind_origin_is_still_adopted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    git(repo, "branch", "-q", "fr", "refs/remotes/origin/fr")
    assert (ensure_worktree(repo) / "settings.yaml").is_file()


def test_init_quiet_refuses_a_preexisting_local_fr_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _unrelated_local_fr(repo)
    code, out = _invoke(repo, "settings", "init", "--quiet")
    assert code == 2, out
    assert "local `fr` branch" in out
    assert git(repo, "ls-remote", "origin", "refs/heads/fr").strip() == ""


# --- p3-r10: `apply --to` reads the switch only ---------------------------------------


def test_apply_to_is_refused_by_the_switch_alone_without_a_worktree(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    git(repo, "checkout", "-q", "-b", "feat/q")  # space_for would create the fr worktree
    code, out = _invoke(repo, "apply", "--all", "--to", "vk")
    assert code == 2, out
    assert "not available under placement quiet" in out
    home = Path(os.environ["HOME"])
    assert not (home / ".cache" / "fr" / "worktrees" / "work" / "fr").exists()
