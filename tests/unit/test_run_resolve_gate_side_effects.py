"""`fr run resolve` decides everything before its operator gate writes anything
(debug journal `2026-09-27-resolve-gate-side-effects`).

Three defects on one path, one cause — the gate's side effects ran at DECISION
time, not at each branch's persistence point:

- gh#587: `--state done` never required a step's declared emits, so a gated
  `brainstorm` reached `done` with no spec.
- gh#632: a cleared gate on a `kind: cli` step noted `unobserved=operator-gate`
  but the cli branch never took the note, so the cursor lost it.
- gh#690: the flag path appended the gate's spec-journal decision before a
  later refusal, and the command's closing commit kept the orphan.
"""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import journal_path
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _GATE_SHAPE,
    _GATED_AGENT_SHAPE,
    _gated_agent_blocked,
    _invoke,
    _invoke_as_harness,
    _invoke_measurable,
    _repo,
    _write_shape,
)

_SPEC = "docs/superpowers/specs/2026-09-21-x-design.md"
_DONE = ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done"]


def _agent_blocked(tmp_path: Path, shape: str) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", shape)
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"
    return repo, shipped


def test_done_without_a_declared_emit_is_refused_naming_it(tmp_path: Path) -> None:
    """gh#587, the measured run: `resolve --step brainstorm --state done` with
    no `--emitted spec=` used to record `done` and `emitted: None`."""
    repo, shipped = _agent_blocked(tmp_path, _GATED_AGENT_SHAPE)

    result = _invoke(repo, shipped, [*_DONE, "--answered-by", "agent"])

    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert "spec" in flat and "--emitted spec=" in flat
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_failed_needs_no_declared_emit(tmp_path: Path) -> None:
    """A failed step produced nothing; demanding its outputs would make the
    failure unreportable."""
    repo, shipped = _agent_blocked(tmp_path, _GATED_AGENT_SHAPE)

    result = _invoke(repo, shipped, [*_DONE[:-1], "failed"])

    assert result.exit_code == 0, result.output


def test_a_cleared_cli_gate_persists_unobserved_on_the_cursor(tmp_path: Path) -> None:
    """gh#632: the `kind: cli` branch saved the cursor without the note."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    env = {"FR_HARNESS": "opencode"}
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], env
    )
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], env)

    result = _invoke_as_harness(repo, shipped, [*_DONE, "--answered-by", "agent"], env)

    assert result.exit_code == 0, result.output
    assert "unobserved=operator-gate" in " ".join(result.output.split())
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "pending" and record.gate == "cleared"
    assert units.evidence_of(record, "step/brainstorm").get("unobserved") == "operator-gate"


_GATED_WITH_EVIDENCE = _GATED_AGENT_SHAPE.replace(
    "    emits: [spec]\n", "    emits: [spec]\n    evidence: [tests]\n", 1
)


def test_a_later_refusal_leaves_no_gate_decision_on_the_journal(tmp_path: Path) -> None:
    """gh#690: `--no-questions --reason` cleared the gate, `_verified_evidence`
    then refused (no `--evidence tests=`), and the journal kept — and the
    command's closing commit recorded — a decision the cursor never did."""
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")
    _write_shape(shipped, "gated-agent", _GATED_WITH_EVIDENCE)
    journal = journal_path(repo, "spec", "2026-09-21-x")

    result = _invoke_measurable(
        repo,
        shipped,
        [*_DONE, "--emitted", f"spec={_SPEC}", "--no-questions", "--reason", "all in the ask"],
        root,
        "s-g",
    )

    assert result.exit_code == 2, result.output
    assert "tests" in " ".join(result.output.split())
    assert not journal.exists(), journal.read_text()
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"
