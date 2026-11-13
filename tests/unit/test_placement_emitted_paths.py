"""Under quiet, a step's emitted spec/plan lives in the fr worktree's feature root, so
`fr run resolve --emitted` must resolve it there (live walk of 7.0.0rc3: brainstorm could
never resolve under quiet or stealth)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

FEATURE = "feat__q"
SPEC = "2026-11-13-q-design.md"


def _fr(cwd: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "FR_REPO_ROOT": str(cwd), "FR_ISOLATION_TARGET": "worktree"}
    result = CliRunner().invoke(app, list(argv), env=env)
    return result.exit_code, result.output


@pytest.fixture
def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    fr_root = Path(os.environ["HOME"]) / ".cache" / "fr" / "worktrees" / "work" / "fr"
    code, out = _fr(state.worktree, "run", "start", "fr-goal", "--branch", "feat/q")
    assert code == 0, out
    (cursor,) = (fr_root / "features" / FEATURE / KIND_DIRS["run"]).glob("*.yaml")
    feature = fr_root / "features" / FEATURE
    spec = feature / KIND_DIRS["spec"] / SPEC
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Q\n")
    code, out = _fr(state.worktree, "run", "advance", cursor.stem)
    assert code == 0, out
    return state.worktree, feature, cursor.stem


@pytest.mark.parametrize("spelling", ["logical", "absolute", "fr-relative"])
def test_brainstorm_resolves_an_emitted_spec_under_quiet(
    started: tuple[Path, Path, str], spelling: str
) -> None:
    worktree, feature, run_id = started
    logical = f"{KIND_DIRS['spec']}/{SPEC}"
    value = {
        "logical": logical,
        "absolute": str(feature / logical),
        "fr-relative": f"features/{FEATURE}/{logical}",
    }[spelling]
    code, out = _fr(
        worktree,
        "run",
        "resolve",
        run_id,
        "--step",
        "brainstorm",
        "--state",
        "done",
        "--answered-by",
        "agent",
        "--emitted",
        f"spec={value}",
    )
    assert code == 0, out
    cursor = (feature / KIND_DIRS["run"] / f"{run_id}.yaml").read_text()
    assert f"spec: {logical}" in cursor, cursor


def test_the_brainstorm_brief_carries_a_record_template_under_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The brief went out with `record: null` (the records dir is outside the checkout,
    and `relative_to` raised inside the swallowing `_record_brief`)."""
    import json

    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    code, out = _fr(state.worktree, "run", "start", "fr-goal", "--branch", "feat/q")
    assert code == 0, out
    fr_root = Path(os.environ["HOME"]) / ".cache" / "fr" / "worktrees" / "work" / "fr"
    (cursor,) = (fr_root / "features" / FEATURE / KIND_DIRS["run"]).glob("*.yaml")
    code, out = _fr(state.worktree, "run", "advance", cursor.stem)
    assert code == 0, out
    brief = json.loads(out[out.index("{") :])
    record = brief["record"]
    assert record is not None, brief
    path = Path(record["path"])
    assert path.is_absolute() and path.parent.is_dir(), record
    assert path.is_relative_to(fr_root / "features" / FEATURE), record
    assert f"--record {path}" in record["template"]


def test_a_spec_in_the_product_checkout_is_refused_under_quiet(
    started: tuple[Path, Path, str],
) -> None:
    worktree, _, run_id = started
    stray = worktree / KIND_DIRS["spec"] / "stray.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("# stray\n")
    code, out = _fr(
        worktree, "run", "resolve", run_id, "--step", "brainstorm", "--state", "done",
        "--answered-by", "agent", "--emitted", f"spec={stray}",
    )  # fmt: skip
    assert code == 2, out
    assert "quiet artifact root" in out and "fr settings paths" in out


@pytest.mark.parametrize("escape", ["dotdot", "other-feature", "symlink"])
def test_an_emitted_path_cannot_leave_the_feature_root(
    started: tuple[Path, Path, str], escape: str
) -> None:
    worktree, feature, run_id = started
    other = feature.parent / "feat__other" / KIND_DIRS["spec"] / "x.md"
    other.parent.mkdir(parents=True)
    other.write_text("# other\n")
    if escape == "dotdot":
        value = f"../feat__other/{KIND_DIRS['spec']}/x.md"
    elif escape == "other-feature":
        value = f"features/feat__other/{KIND_DIRS['spec']}/x.md"
    else:
        link = feature / KIND_DIRS["spec"] / "link.md"
        link.symlink_to(other)
        value = f"{KIND_DIRS['spec']}/link.md"
    code, out = _fr(
        worktree, "run", "resolve", run_id, "--step", "brainstorm", "--state", "done",
        "--answered-by", "agent", "--emitted", f"spec={value}",
    )  # fmt: skip
    assert code == 2, out
    assert "outside this feature's quiet artifact root" in out


def test_readers_of_the_emitted_paths_follow_the_artifact_root(
    started: tuple[Path, Path, str],
) -> None:
    """The cli steps' `{{ artifacts.* }}` (they run in the product checkout), a quiet
    plan's own spec, and `fr pickup`'s plan -> run match all read the feature root."""
    from fr.commands.pickup_cmd import _run_unit_record
    from fr.commands.run_cmd import _save_run_state, _template_context
    from fr.parser import parse
    from fr.run.model import load_run_state

    worktree, feature, run_id = started
    code, out = _fr(
        worktree, "run", "resolve", run_id, "--step", "brainstorm", "--state", "done",
        "--answered-by", "agent", "--emitted", f"spec={KIND_DIRS['spec']}/{SPEC}",
    )  # fmt: skip
    assert code == 0, out
    code, out = _fr(
        worktree, "plan", "create", "--slug", "2026-11-13-q", "--target-repo", "derio-net/q",
        "--spec", f"{KIND_DIRS['spec']}/{SPEC}",
    )  # fmt: skip
    assert code == 0, out
    plan_rel = f"{KIND_DIRS['plan']}/2026-11-13-q"
    state = load_run_state(worktree, run_id)
    record = state.steps["brainstorm"]
    state = state.model_copy(
        update={
            "steps": {
                **state.steps,
                "brainstorm": record.model_copy(
                    update={"emitted": {**(record.emitted or {}), "plan": plan_rel}}
                ),
            }
        }
    )
    _save_run_state(worktree, state)

    ctx = _template_context(state, worktree)
    assert ctx["artifacts.spec"] == str(feature / KIND_DIRS["spec"] / SPEC)
    assert ctx["artifacts.plan"] == str(feature / plan_rel)
    assert _template_context(state)["artifacts.plan"] == plan_rel  # no root: as recorded

    plan = parse(feature / plan_rel)
    assert plan.artifact_root == feature
    assert plan.spec_path is not None and (plan.repo_root / plan.spec_path).is_file()
    code, out = _fr(worktree, "plan", "self-review", str(feature / plan_rel))
    assert code == 0 and "does not resolve" not in out, out

    brief = _run_unit_record(plan, 1)
    assert brief is not None
