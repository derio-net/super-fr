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

    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gate-state"))
    _finished(tmp_path, discharged=True)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert result.exit_code == 0, result.output
    assert "fr ops gate --run" not in result.output
    assert "DevOps stage complete" in result.output and "Nothing is left" in result.output
    assert "fr isolation down --branch feat/x" in result.output
    assert result.output.rstrip().endswith("owed\n  (none)")  # the DoD closes it (R19)


def _finished(repo: Path, *, discharged: bool) -> None:
    """A run whose DevOps stage record holds all eight stages, its plan a real folder and
    its Test Plan step ran; *discharged*: its one op is closed too, so its Definition of
    Done is discharged."""
    import shutil

    from fr.ops.evidence import record_op
    from fr.ops.gate import HostGateState, gate_state_path

    from tests.unit.test_run_dod import FIXTURE

    _run(repo, ops=True)
    for name in ("_meta.yaml", "01.yaml"):
        shutil.copy(FIXTURE / name, repo / PLAN / name)
    phase = repo / PLAN / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    _ran_step_1(repo)  # its one Test Plan step (devops, by the promotion) ran
    if discharged:  # and its op is closed
        record_op(repo, Path(PLAN).name, op="k", result="attested", phase="pre-merge",
                  attested_by="operator")  # fmt: skip
    record = HostGateState(gate_state_path(repo, "r1"))
    for n in range(1, 9):
        record.mark(n)


def _ran_step_1(repo: Path) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    slug = "2026-09-30-fixture"
    entry = JournalEntry(kind="discovery", scope="spec", id="test-plan-step-1",
                         created="2026-09-30T10:00:00+00:00", title="Test Plan step 1: ran",
                         body="ran it")  # fmt: skip
    append_journal_entry(journal_path(repo, "spec", slug), slug, entry)


def test_r19_a_finished_stage_with_owed_items_names_them_and_never_says_complete(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gate-state"))
    _finished(tmp_path, discharged=False)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert result.exit_code == 0, result.output
    out = result.output
    assert "DevOps stage complete" not in out and "Nothing is left" not in out
    assert "every stage (1-8) ran" in out
    assert "  - gate:devops: op k [pre-merge]: " in out
    assert "## Definition of Done — 1 item owed" in out
    assert "fr ops gate --run" not in out


def test_r19_the_in_progress_devops_brief_ends_with_the_definition_of_done(
    tmp_path: Path,
) -> None:
    _run(tmp_path, ops=True)
    result = _invoke(tmp_path, ["pickup", "--run", "r1"])
    assert result.exit_code == 0, result.output
    headings = [ln for ln in result.output.splitlines() if ln.startswith("#")]
    assert headings[-1].startswith("## Definition of Done"), headings


def test_gh1275_a_partly_run_stage_still_gets_the_brief(tmp_path: Path, monkeypatch: Any) -> None:
    from fr.ops.gate import HostGateState, gate_state_path

    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gate-state"))
    _run(tmp_path, ops=True)
    HostGateState(gate_state_path(tmp_path, "r1")).mark(1)

    result = _invoke(tmp_path, ["pickup", "--run", "r1"])

    assert "fr ops gate --run r1" in result.output, result.output


# --- gh#1614: `deliver`'s own hand-off line names the DevOps stage ----------------------


def test_deliver_handoff_names_the_devops_stage_for_a_devops_gated_run(tmp_path: Path) -> None:
    """For a run whose gates include devops the stage owns the merge, so the line
    `deliver` ends with is `fr ops gate --run <id>`, never the post-merge pickup."""
    from fr.commands.run_cmd import _closeout_handoff_lines

    state = _run(tmp_path, ops=True)
    lines = _closeout_handoff_lines(tmp_path, state, committed=False)
    assert lines[-1].strip() == "fr ops gate --run r1"
    assert lines[-2].startswith("closeout: ") and "DevOps stage" in lines[-2]
    assert not any("fr pickup --run" in line for line in lines)


def test_deliver_handoff_stays_the_pickup_for_a_run_without_devops(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _closeout_handoff_lines

    state = _run(tmp_path)
    lines = _closeout_handoff_lines(tmp_path, state, committed=False)
    assert lines[-1].strip() == "fr pickup --run r1"
    assert lines[-2].startswith("closeout: after the PR merges, start a NEW session in")
