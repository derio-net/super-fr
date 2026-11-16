"""`fr pickup --run` for a run whose effective gates include devops prints the DevOps
brief (spec 2026-10-22-fr-ops R16); every other run's brief is byte-identical to the
close-out brief it printed before."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.run.closeout import closeout_brief
from fr.run.model import RunState, StepRecord, save_run_state

from tests.unit.acceptance_helpers import write_matrix_fragments
from tests.unit.requirements_support import row, write_matrix
from tests.unit.test_pickup_cmd import _invoke

SPEC = "docs/superpowers/specs/2026-09-30-fixture-design.md"
PLAN = "docs/superpowers/plans/2026-09-30-fixture"
OPS = "schema_version: 1\nops:\n  - {id: k, summary: make the key, phase: pre-merge}\n"


def _run(repo: Path, *, ops: bool = False, gate: str = "developer") -> RunState:
    (repo / SPEC).parent.mkdir(parents=True, exist_ok=True)
    (repo / SPEC).write_text(
        f"# Fixture\n\n## Verification\n\nstrategy: none\ngate: {gate}\n\n"
        "## Test Plan\n\n- walk it\n"
    )
    write_matrix(repo, [row(SPEC, rid="r1")])
    (repo / PLAN).mkdir(parents=True, exist_ok=True)
    if ops:
        (repo / PLAN / "ops.yaml").write_text(OPS)
    state = RunState(
        run="r1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN}),
            "deliver": StepRecord(
                state="done", emitted={"pr": "https://github.com/derio-net/super-fr/pull/1"}
            ),
        },
    )
    save_run_state(repo, state)
    return state


def test_a_run_with_ops_gets_the_devops_brief(tmp_path: Path) -> None:
    _run(tmp_path, ops=True)
    result = _invoke(tmp_path, ["pickup", "--run", "r1"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "fr ops gate --run r1" in out
    assert "before or after" in out and "pull/1" in out
    assert "fr-devops-gate" in out
    for gone in ("verify-merge", "STOP", "fr archive"):
        assert gone not in out, gone


def test_a_declared_devops_gate_gets_the_devops_brief_too(tmp_path: Path) -> None:
    _run(tmp_path, gate="devops")
    result = _invoke(tmp_path, ["pickup", "--run", "r1"])
    assert result.exit_code == 0, result.output
    assert "fr ops gate --run r1" in result.output


def test_every_other_run_prints_todays_brief_byte_for_byte(tmp_path: Path) -> None:
    for gate in ("developer", "tester"):
        state = _run(tmp_path, gate=gate)
        result = _invoke(tmp_path, ["pickup", "--run", "r1"])
        assert result.exit_code == 0, result.output
        assert result.output == closeout_brief(tmp_path, state) + "\n"
        assert "fr ops gate" not in result.output


def test_a_plan_with_ops_gets_it_even_when_the_matrix_is_unreadable(tmp_path: Path) -> None:
    _run(tmp_path, ops=True)
    write_matrix_fragments(tmp_path, "rows: [\n")
    result = _invoke(tmp_path, ["pickup", "--run", "r1"])
    assert "fr ops gate --run r1" in result.output, result.output


def test_the_devops_brief_still_needs_a_done_deliver(tmp_path: Path) -> None:
    state = _run(tmp_path, ops=True)
    state.steps["deliver"] = StepRecord(state="running")
    save_run_state(tmp_path, state)
    result = _invoke(tmp_path, ["pickup", "--run", "r1"])
    assert result.exit_code == 2


def test_gh1275_a_finished_devops_stage_says_so_instead_of_the_brief(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """gh#1275: once the gate's own record holds stage 8, `fr pickup --run` reports the
    stage complete and names the workspace reap, never the `fr ops gate` command again."""
    from fr.ops.gate import HostGateState, gate_state_path

    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gate-state"))
    _run(tmp_path, ops=True)
    record = HostGateState(gate_state_path(tmp_path, "r1"))
    for n in range(1, 9):
        record.mark(n)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert result.exit_code == 0, result.output
    assert "fr ops gate --run" not in result.output
    assert "DevOps stage complete" in result.output
    assert "fr isolation down --branch feat/x" in result.output


def test_gh1275_a_partly_run_stage_still_gets_the_brief(tmp_path: Path, monkeypatch: Any) -> None:
    from fr.ops.gate import HostGateState, gate_state_path

    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gate-state"))
    _run(tmp_path, ops=True)
    HostGateState(gate_state_path(tmp_path, "r1")).mark(1)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert "fr ops gate --run r1" in result.output, result.output
