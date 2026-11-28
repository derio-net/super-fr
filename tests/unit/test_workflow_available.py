"""`workflows.disabled` withdraws a shape (spec 2026-11-28-alacarte-settings R2).

A disabled shape binds no new run: `fr run start`, a brainstorm record's `shape:` rebind
and `fr run adopt` refuse it, naming the setting and the shapes still available. A run
already started on it keeps going: `advance`, `resolve` and `reshape` never refuse, and
`adopt --supersede` onto the run's own shape is that run continuing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fr.workflow import available
from fr.workflow.available import refuse_disabled
from fr.workflow.model import WorkflowError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, land_on_main, make_repo
from tests.unit.stealth_repo import stealth_home, stealth_pair

__all__ = ["stealth_home"]

pytestmark = pytest.mark.own_artifacts

DISABLE_LIGHT = "schema: 3\nworkflows:\n  disabled: [fr-goal-light]\n"


def _squash(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    land_on_main(root, DISABLE_LIGHT)
    return root


# --- the one check -----------------------------------------------------------------


def test_a_disabled_shape_is_refused_naming_the_setting_and_what_is_left(repo: Path) -> None:
    with pytest.raises(WorkflowError) as e:
        refuse_disabled("fr-goal-light", repo)
    msg = str(e.value)
    assert "workflows.disabled" in msg
    assert "available: fr-debugging, fr-goal" in msg
    assert "fr-goal-light," not in msg.split("available:")[1]


def test_a_shape_that_is_not_disabled_passes(repo: Path) -> None:
    assert refuse_disabled("fr-goal", repo) is None


# --- fr run start --------------------------------------------------------------------


def test_run_start_refuses_a_disabled_shape_before_any_worktree(repo: Path) -> None:
    from fr.cli import app

    before = git(repo, "worktree", "list")
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal-light", "--branch", "feat/x"],
        env={**os.environ, "FR_REPO_ROOT": str(repo)},
    )
    assert result.exit_code == 2, result.output
    assert "workflows.disabled" in _squash(result.output)
    assert git(repo, "worktree", "list") == before


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


def test_under_stealth_run_start_reads_the_tracking_settings(tmp_path: Path) -> None:
    from fr.cli import app
    from fr.isolation.hostworktree import HostWorktreeTarget
    from fr.placement import stealth

    target, track = stealth_pair(tmp_path)
    land_on_main(target, "schema: 3\nworkflows:\n  disabled: []\n")
    _push_target_settings(track, tmp_path, "schema: 3\nworkflows:\n  disabled: [fr-goal]\n")
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "workflow fr-goal is disabled" in out and "workflows.disabled" in out


# --- the brainstorm rebind --------------------------------------------------------------


def _disable(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    monkeypatch.setattr(available, "disabled_shapes", lambda _root: list(names))


def test_a_rebind_onto_a_disabled_shape_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.model import RunStateError, load_run_state
    from fr.run.steps import rebind_shape, resolve_manifest_for_state

    from tests.unit.test_run_light_shape import _at_brainstorm

    root = _at_brainstorm(tmp_path)
    state = load_run_state(root, "r1")
    manifest = resolve_manifest_for_state(root, state)
    _disable(monkeypatch, "fr-goal-light")
    with pytest.raises(RunStateError, match="workflows.disabled"):
        rebind_shape(state, manifest, "brainstorm", "fr-goal-light", root)


# --- fr run adopt -------------------------------------------------------------------------


def _adopt_repo(tmp_path: Path, repo_root: Path) -> tuple[Path, Path, Path]:
    from tests.unit.test_run_adopt import _repo, _write_plan, _write_spec

    repo, shipped = _repo(tmp_path, repo_root)
    shutil.copy(
        repo_root / "plugins" / "super-fr" / "defaults" / "workflows" / "fr-goal-light.yaml",
        shipped / "fr-goal-light.yaml",
    )
    _write_spec(repo)
    return repo, shipped, _write_plan(repo, phases=1, complete=0)


def test_a_plain_adopt_onto_a_disabled_shape_is_refused(
    tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.adopt import AdoptError, adopt_run

    from tests.unit.test_run_adopt import BRANCH

    repo, shipped, plan_dir = _adopt_repo(tmp_path, repo_root)
    _disable(monkeypatch, "fr-goal-light")
    with pytest.raises(AdoptError, match="workflows.disabled"):
        adopt_run(repo, plan_dir, branch=BRANCH, workflow="fr-goal-light", shipped_root=shipped)
    with pytest.raises(AdoptError, match="workflows.disabled"):
        adopt_run(
            repo,
            plan_dir,
            branch=BRANCH,
            workflow="fr-goal-light",
            supersede=True,
            shipped_root=shipped,
        )


def test_supersede_onto_the_runs_own_shape_passes_and_onto_another_disabled_one_refuses(
    tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.adopt import AdoptError, adopt_run

    from tests.unit.test_run_adopt import BRANCH, _commit_all, _git

    repo, shipped, plan_dir = _adopt_repo(tmp_path, repo_root)
    adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        workflow="fr-goal-light",
        run_id="old-run",
        shipped_root=shipped,
    )
    _commit_all(repo)
    _git(repo, "checkout", "-q", "-b", "feat/old")
    _disable(monkeypatch, "fr-goal-light", "fr-goal")
    with pytest.raises(AdoptError, match="workflow fr-goal is disabled"):
        adopt_run(
            repo,
            plan_dir,
            branch=BRANCH,
            workflow="fr-goal",
            run_id="new-run",
            supersede=True,
            shipped_root=shipped,
        )
    state = adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        workflow="fr-goal-light",
        run_id="new-run",
        supersede=True,
        shipped_root=shipped,
    )
    assert state.workflow.startswith("fr-goal-light@")


# --- a started run keeps going ------------------------------------------------------------


def test_advance_resolve_and_reshape_never_consult_the_disabled_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.record_support import fr
    from tests.unit.test_run_light_shape import _at_brainstorm

    root = _at_brainstorm(tmp_path, shape="fr-goal-light")

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("refuse_disabled must not run here")

    monkeypatch.setattr(available, "refuse_disabled", _boom)
    for argv in (
        ["run", "advance", "r1"],
        ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done",
         "--answered-by", "agent", "--emitted", "spec=docs/spec.md"],
        ["run", "reshape", "r1"],
    ):  # fmt: skip
        out = fr(root, argv)
        assert out.exit_code == 0, (argv, out.output)
