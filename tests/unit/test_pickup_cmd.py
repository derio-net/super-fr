"""`fr pickup --run` — spec 2026-09-25-fr-goal-closeout-defects-design §3.D.1.

`fr pickup` gains a second mode, mutually exclusive with `<plan-dir>
--phase N`: given a run id, it prints the closeout brief for a finished
delivery run instead of a phase's scope.
"""

from __future__ import annotations

import os
from pathlib import Path

from fr.cli import app
from fr.run.model import RunState, StepRecord, save_run_state
from typer.testing import CliRunner

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

runner = CliRunner()


def _invoke(repo: Path, argv: list[str]):
    env = {**os.environ, "VK_REPO_ROOT": str(repo)}
    return runner.invoke(app, argv, env=env)


def _write_finished_run(repo: Path, run_id: str = "r1") -> None:
    spec_dir = repo / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "2026-09-30-fixture-design.md").write_text("# Fixture\n")
    state = RunState(
        run=run_id,
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(
                state="done",
                emitted={"spec": "docs/superpowers/specs/2026-09-30-fixture-design.md"},
            ),
            "deliver": StepRecord(
                state="done", emitted={"pr": "https://github.com/derio-net/super-fr/pull/1"}
            ),
        },
    )
    save_run_state(repo, state)


def _write_running_run(repo: Path, run_id: str = "r1") -> None:
    state = RunState(
        run=run_id,
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={"deliver": StepRecord(state="running")},
    )
    save_run_state(repo, state)


def test_pickup_run_prints_the_closeout_brief_for_a_finished_run(tmp_path: Path) -> None:
    _write_finished_run(tmp_path)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert result.exit_code == 0, result.output
    assert "branch: feat/x" in result.output
    assert "fr isolation verify-merge --branch feat/x" in result.output


def test_pickup_run_refuses_a_run_whose_deliver_is_not_done(tmp_path: Path) -> None:
    _write_running_run(tmp_path)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert result.exit_code == 2
    output = " ".join((result.output or "").split()) + " ".join((result.stderr or "").split())
    assert "deliver" in output
    assert "r1" in output


def test_pickup_run_refuses_an_unknown_run_id(tmp_path: Path) -> None:
    result = _invoke(tmp_path, ["pickup", "--run", "does-not-exist"])

    assert result.exit_code == 2


def test_pickup_run_refuses_combination_with_plan_dir(tmp_path: Path) -> None:
    _write_finished_run(tmp_path)

    result = _invoke(tmp_path, ["pickup", str(FIXTURE), "--run", "r1"])

    assert result.exit_code == 2


def test_pickup_run_refuses_combination_with_phase(tmp_path: Path) -> None:
    _write_finished_run(tmp_path)

    result = _invoke(tmp_path, ["pickup", "--run", "r1", "--phase", "1"])

    assert result.exit_code == 2


def test_pickup_phase_mode_is_unchanged(tmp_path: Path) -> None:
    """The pre-existing `<plan-dir> --phase N` mode still works with no
    `--run` in sight — the refactor must not touch its output shape."""
    result = _invoke(tmp_path, ["pickup", str(FIXTURE), "--phase", "1"])

    assert result.exit_code == 0, result.output
    assert "Phase 1/1" in result.output
    assert "Fixture phase" in result.output
