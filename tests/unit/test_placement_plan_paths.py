"""Under quiet, a plan lives in the fr worktree's feature root, but it still belongs to
the product checkout: `Plan.repo_root` is that checkout and `Plan.spec_path` is relative
to the plan's artifact root, the run cursor's convention (live walk of 7.0.0rc4: plan
self-review refused every plan whose rows cite their spec logically, debug journal
2026-11-13-placement-plan-paths)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

FEATURE = "feat__q"
SLUG = "2026-11-13-q"
SPEC = f"{SLUG}-design.md"
SPEC_TEXT = """# Q

## Requirements

R1. The tool says hello.

## Test Plan

- unit: hello is printed.

## Verification

strategy: none
- q-hello: none — proven by its unit test
"""
PHASES = [
    {
        "number": 1,
        "title": "Hello",
        "tag": "agentic",
        "tier": "mechanical",
        "acceptance": ["q-hello"],
        "tasks": [
            {"number": 1, "title": "say hello", "steps": [{"id": "P1.T1.S1", "text": "Write it"}]}
        ],
    }
]


def _fr(cwd: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "FR_REPO_ROOT": str(cwd), "FR_ISOLATION_TARGET": "worktree"}
    result = CliRunner().invoke(app, list(argv), env=env)
    return result.exit_code, result.output


@pytest.fixture
def quiet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A quiet workspace with a spec below its feature root and one acceptance row
    citing it logically, the state brainstorm leaves."""
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    feature = Path(os.environ["HOME"]) / ".cache/fr/worktrees/work/fr/features" / FEATURE
    spec = feature / KIND_DIRS["spec"] / SPEC
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC_TEXT)
    code, out = _fr(state.worktree, "acceptance", "init")
    assert code == 0, out
    code, out = _fr(
        state.worktree, "acceptance", "add", "--id", "q-hello", "--capability", "hello",
        "--acceptance", "the tool says hello", "--origin", f"spec:{SLUG}#R1",
        "--status", "not-implemented", "--notes", "n", "--repo", "derio-net/q",
    )  # fmt: skip
    assert code == 0, out
    return state.worktree, feature


def _create(worktree: Path, tmp_path: Path, spec_arg: str) -> Path:
    phases = tmp_path / "phases.yaml"
    phases.write_text(yaml.safe_dump(PHASES))
    code, out = _fr(
        worktree, "plan", "create", "--slug", SLUG, "--target-repo", "derio-net/q",
        "--spec", spec_arg, "--phases-file", str(phases),
    )  # fmt: skip
    assert code == 0, out
    return (
        Path(os.environ["HOME"])
        / ".cache/fr/worktrees/work/fr/features"
        / FEATURE
        / (f"{KIND_DIRS['plan']}/{SLUG}")
    )


@pytest.mark.parametrize("spelling", ["absolute", "logical", "bare"])
def test_plan_create_stores_the_bare_spec_filename_under_quiet(
    quiet: tuple[Path, Path], tmp_path: Path, spelling: str
) -> None:
    worktree, feature = quiet
    value = {
        "absolute": str(feature / KIND_DIRS["spec"] / SPEC),
        "logical": f"{KIND_DIRS['spec']}/{SPEC}",
        "bare": SPEC,
    }[spelling]
    plan_dir = _create(worktree, tmp_path, value)
    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    assert meta["spec"] == SPEC, meta


def test_a_quiet_plan_belongs_to_the_product_checkout(
    quiet: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.parser import parse

    worktree, feature = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    for cwd in (worktree, plan_dir, tmp_path):  # the workspace, the fr worktree, elsewhere
        monkeypatch.chdir(cwd)
        monkeypatch.delenv("FR_REPO_ROOT", raising=False)
        plan = parse(plan_dir)
        assert plan.repo_root == worktree.resolve(), cwd
        assert plan.artifact_root == feature
        assert plan.spec_path == f"{KIND_DIRS['spec']}/{SPEC}"
        assert plan.spec_file == feature / KIND_DIRS["spec"] / SPEC
        # Review F1: the Issue body's `📋 Plan:` line names the plan by this path; it is
        # relative to the artifact root, never the operator's absolute one.
        assert plan.repo_relative_dir == Path(KIND_DIRS["plan"]) / SLUG


def test_plan_self_review_passes_a_quiet_plan_whose_rows_cite_the_spec_logically(
    quiet: tuple[Path, Path], tmp_path: Path
) -> None:
    worktree, _ = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    code, out = _fr(worktree, "plan", "self-review", str(plan_dir))
    assert "serves no ask" not in out, out
    assert "no matrix row citing the spec" not in out, out
    assert "unknown acceptance row" not in out, out
    assert "features/" not in out, out
    assert code == 0, out


def _delivered(worktree: Path) -> str:
    """A run on feat/q whose deliver is done and whose spec is the quiet feature's."""
    from fr.run.model import load_run_state, save_run_state

    code, out = _fr(worktree, "run", "start", "fr-goal", "--branch", "feat/q", "--run-id", "rq")
    assert code == 0, out
    state = load_run_state(worktree, "rq")
    steps = dict(state.steps)
    steps["brainstorm"] = steps["brainstorm"].model_copy(
        update={"state": "done", "emitted": {"spec": f"{KIND_DIRS['spec']}/{SPEC}"}}
    )
    steps["deliver"] = steps["deliver"].model_copy(
        update={"state": "done", "emitted": {"pr": "https://github.com/derio-net/q/pull/1"}}
    )
    save_run_state(worktree, state.model_copy(update={"steps": steps}))
    return "rq"


def test_pickup_run_from_the_base_clone_finds_a_quiet_features_run(
    quiet: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`deliver` tells the operator to run `fr pickup --run <id>` in the base clone; under
    quiet the base clone's own feature is its default branch, which holds no run."""
    worktree, _ = quiet
    run_id = _delivered(worktree)
    base = tmp_path / "work"
    monkeypatch.chdir(base)
    code, out = _fr(base, "pickup", "--run", run_id)
    assert code == 0, out
    assert f"spec: {KIND_DIRS['spec']}/{SPEC}" in out
    assert "run the spec's Test Plan" in out, out  # the spec was read where it lives
    assert "fr archive --branch feat/q" in out
    # Under quiet the archive records the merge on `fr` and pushes it: no housekeeping
    # workspace, no product commit, no housekeeping PR.
    assert "fr isolation up --branch chore/" not in out, out
    assert "git add -A" not in out, out
    assert "housekeeping PR" not in out, out
    assert "fr isolation down --branch feat/q" in out


def test_a_pending_rows_origin_is_corrected_in_place_and_moves_to_its_spec(
    quiet: tuple[Path, Path],
) -> None:
    """A row this feature just created with a wrong origin (the live walk's typo) had no
    supported correction: `add` creates only, `set-status` moves status and evidence, and
    no amendment op carries an origin. `amend --op reword --origin` rewrites a pending
    row in place and files it under the spec its corrected origin names."""
    worktree, feature = quiet
    frags = feature / KIND_DIRS["acceptance-fragment"]
    code, out = _fr(
        worktree, "acceptance", "add", "--id", "q-typo", "--capability", "hello",
        "--acceptance", "a typo'd origin", "--origin", "spec:2026-11-13-qq#R1",
        "--status", "not-implemented", "--notes", "n",
    )  # fmt: skip
    assert code == 0, out
    assert (frags / "2026-11-13-qq.yaml").is_file()
    code, out = _fr(
        worktree, "acceptance", "amend", "--id", "q-typo", "--op", "reword",
        "--origin", f"spec:{SLUG}#R1", "--why", "the origin was mistyped",
    )  # fmt: skip
    assert code == 0, out
    assert not (frags / "2026-11-13-qq.yaml").exists(), out
    rows = yaml.safe_load((frags / f"{SLUG}.yaml").read_text())["rows"]
    fixed = next(r for r in rows if r["id"] == "q-typo")
    assert fixed["origin"] == [f"spec:{SLUG}#R1"]
    assert fixed["acceptance"] == "a typo'd origin"
    assert "amendments" not in yaml.safe_load((frags / f"{SLUG}.yaml").read_text())
    code, out = _fr(worktree, "acceptance", "check", "--no-fetch")
    assert code == 0, out


def test_origin_correction_is_refused_for_any_op_but_reword(quiet: tuple[Path, Path]) -> None:
    worktree, _ = quiet
    code, out = _fr(
        worktree, "acceptance", "amend", "--id", "q-hello", "--op", "set-status",
        "--status", "unwired", "--notes", "n", "--origin", f"spec:{SLUG}#R1", "--why", "w",
    )  # fmt: skip
    assert code == 2, out
    assert "only with `--op reword`" in out


def test_the_staleness_guard_sees_a_quiet_features_uncited_spec(
    quiet: tuple[Path, Path],
) -> None:
    """`fr acceptance check` refuses a spec with a Test Plan that no row cites; under
    quiet it globbed the product checkout's specs dir, which holds none, so it never
    fired."""
    worktree, feature = quiet
    code, out = _fr(worktree, "acceptance", "check", "--no-fetch")
    assert code == 0, out  # the fixture's spec is cited by q-hello
    stray = feature / KIND_DIRS["spec"] / "2026-11-13-uncited-design.md"
    stray.write_text("# U\n\n## Test Plan\n\n- unit: nothing cites this.\n")
    code, out = _fr(worktree, "acceptance", "check", "--no-fetch")
    assert code != 0, out
    assert f"staleness: {KIND_DIRS['spec']}/2026-11-13-uncited-design.md" in out, out


def test_moving_a_rows_origin_keeps_the_fragments_amendments(quiet: tuple[Path, Path]) -> None:
    """Review: a fragment emptied of rows by an origin correction still holds the
    feature's amendments, so it is kept (only its row moves), never deleted."""
    worktree, feature = quiet
    frags = feature / KIND_DIRS["acceptance-fragment"]
    code, out = _fr(
        worktree, "acceptance", "add", "--id", "q-typo", "--capability", "hello",
        "--acceptance", "a typo'd origin", "--origin", "spec:2026-11-13-qq#R1",
        "--status", "not-implemented", "--notes", "n",
    )  # fmt: skip
    assert code == 0, out
    code, out = _fr(
        worktree, "acceptance", "amend", "--id", "q-hello", "--op", "reword",
        "--acceptance", "the tool says hello, loudly", "--why", "w", "--feature", "2026-11-13-qq",
    )  # fmt: skip
    assert code == 0, out
    code, out = _fr(
        worktree, "acceptance", "amend", "--id", "q-typo", "--op", "reword",
        "--origin", f"spec:{SLUG}#R1", "--why", "the origin was mistyped",
    )  # fmt: skip
    assert code == 0, out
    kept = yaml.safe_load((frags / "2026-11-13-qq.yaml").read_text())
    assert not kept.get("rows"), kept
    assert [a["row"] for a in kept["amendments"]] == ["q-hello"], kept
    rows = yaml.safe_load((frags / f"{SLUG}.yaml").read_text())["rows"]
    assert "q-typo" in {r["id"] for r in rows}


def test_a_quiet_issue_body_names_no_local_path(quiet: tuple[Path, Path], tmp_path: Path) -> None:
    """Review F1: `fr apply --yes` (tracking, allowed under quiet) renders `📋 Plan:` from
    `repo_relative_dir`, which fell back to the absolute plan dir."""
    from fr import render
    from fr.parser import parse

    worktree, _ = quiet
    plan = parse(_create(worktree, tmp_path, SPEC))
    body = render.render_body(plan.phases[0], plan)
    plan_line = next(line for line in body.splitlines() if "Plan:" in line)
    assert str(Path.home()) not in plan_line and str(tmp_path) not in plan_line, plan_line
    assert f"{KIND_DIRS['plan']}/{SLUG}" in plan_line, plan_line


def test_pickup_names_a_quiet_plans_prose_by_a_readable_path(
    quiet: tuple[Path, Path], tmp_path: Path
) -> None:
    worktree, _ = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    code, out = _fr(worktree, "pickup", str(plan_dir), "--phase", "1")
    assert code == 0, out
    flat = " ".join(out.split())
    assert f"read `{plan_dir}/_prose.md`" in flat.replace("\n", ""), out
    assert (plan_dir / "_prose.md").is_file()


def test_pickup_run_refuses_a_run_id_two_features_hold(
    quiet: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F8: the base clone took whichever feature root sorted first."""
    import shutil

    worktree, feature = quiet
    run_id = _delivered(worktree)
    cursor = feature / KIND_DIRS["run"] / f"{run_id}.yaml"
    other = feature.parent / "feat__other" / KIND_DIRS["run"]
    other.mkdir(parents=True)
    shutil.copy(cursor, other / cursor.name)
    base = tmp_path / "work"
    monkeypatch.chdir(base)
    for argv in (
        ("pickup", "--run", run_id),
        ("closeout", "outcome", "--run", run_id, "--step", "1", "--na", "--reason", "r"),
    ):
        code, out = _fr(base, *argv)
        flat = " ".join(out.split())
        assert code == 2, out
        assert "feat__q" in flat and "feat__other" in flat, out


def test_parsing_a_quiet_plan_from_a_deleted_cwd_does_not_raise(
    quiet: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F7: `parse` asks the working directory for a product-checkout candidate,
    and a deleted one raised `FileNotFoundError` from inside the lookup."""
    from fr.parser import parse

    worktree, _ = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    plan = parse(plan_dir)  # the isolation states still name the workspace
    assert plan.repo_root == worktree.resolve()
