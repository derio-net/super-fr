"""`fr run start / status / advance / resolve / check` — spec §4.B, Phase 7.

The single most important constraint: `advance` NEVER invokes a model. A
`kind: cli` step is executed by fr directly; a `kind: agent` step produces a
brief for the harness to dispatch and marks itself `running` — it is never
shelled out to. This is the structural half of the `no-claude-p-batch` rule.

`resolve` is the other half: the only way an `agent` step's cursor can move
past `running` (the harness calls it when a dispatched agent returns), and
it is equally non-executing — see `test_resolve_never_invokes_a_model_either`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fr.cli import app
from fr.run.model import load_run_state
from fr_dispatch.work_item import run_item_id
from typer.testing import CliRunner

runner_cli = CliRunner()


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "workflows").mkdir(parents=True)
    return tmp_path


def _write_shape(shipped: Path, name: str, text: str) -> None:
    shipped.mkdir(parents=True, exist_ok=True)
    (shipped / f"{name}.yaml").write_text(text)


def _invoke(repo: Path, shipped: Path, argv: list[str]):
    env = {**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)}
    return runner_cli.invoke(app, argv, env=env)


_CLI_ONLY_SHAPE = """
workflow: cli-only
schema: 1
unit: run
steps:
  - id: hello
    kind: cli
    run: echo hello-{{ run.branch }}
  - id: bye
    kind: cli
    run: "true"
"""

_FAILING_SHAPE = """
workflow: fails
schema: 1
unit: run
steps:
  - id: boom
    kind: cli
    run: "false"
  - id: never
    kind: cli
    run: "true"
"""

_GATE_SHAPE = """
workflow: gated
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: cli
    gate: operator
    run: touch executed.marker
  - id: after
    kind: cli
    run: "true"
"""

_AGENT_SHAPE = """
workflow: agentic
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    skill: super-fr:fr-plan
    needs: [spec]
    emits: [plan, journal:plan]
    tier: from_phase
"""

_AGENT_TWO_STEP_SHAPE = """
workflow: agentic-two-step
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    emits: [spec]
  - id: after
    kind: cli
    run: "true"
"""


# --- Task 1: fr run start ---


def test_start_writes_run_file_with_cursor_at_first_step(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"],
    )
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.run == "r1"
    assert state.workflow == "cli-only@1"
    assert state.branch == "feat/x"
    assert state.cursor == "hello"
    assert state.steps["hello"].state == "pending"
    assert state.steps["bye"].state == "pending"


def test_start_run_id_derivation_yields_a_single_path_segment(tmp_path: Path) -> None:
    """Whatever `fr run start` derives when `--run-id` is omitted must satisfy
    `run_item_id`'s "single path segment" constraint (Phase 2 review fix —
    `fr_dispatch.work_item.run_item_id` raises on a `/` or empty `run_id`)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/ticket-polling"],
    )
    assert result.exit_code == 0, result.output
    # find the one run file written
    runs = list((repo / "docs" / "superpowers" / "runs").glob("*.yaml"))
    assert len(runs) == 1
    run_id = runs[0].stem
    assert "/" not in run_id
    # and it composes cleanly into a run-level item id (Phase 2/8 seam)
    assert run_item_id("derio-net/super-fr", run_id) == f"derio-net/super-fr/run/{run_id}"


def test_start_refuses_to_clobber_an_existing_run(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    assert result.exit_code != 0


# --- Task 2: fr run advance — cli steps ---


def test_advance_executes_cli_step_captures_exit_and_stdout_and_moves_cursor(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "myb", "--run-id", "r1"],
    )
    result = runner_cli.invoke(
        app,
        ["run", "advance", "r1"],
        env={**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)},
    )
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["hello"].state == "done"
    assert state.steps["hello"].exit == 0
    assert state.steps["hello"].stdout is not None
    assert "hello-myb" in state.steps["hello"].stdout
    assert state.cursor == "bye"


def test_advance_cli_step_failure_sets_failed_and_leaves_cursor_put(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "fails", _FAILING_SHAPE)
    _invoke(repo, shipped, ["run", "start", "fails", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code != 0
    state = load_run_state(repo, "r1")
    assert state.steps["boom"].state == "failed"
    assert state.steps["boom"].exit != 0
    assert state.cursor == "boom"
    assert state.steps["never"].state == "pending"


# --- Task 2: fr run advance — operator gate ---


def test_advance_onto_operator_gate_marks_blocked_and_does_not_execute(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "blocked"
    assert state.cursor == "brainstorm"
    assert not (repo / "executed.marker").exists()


def test_advance_is_idempotent_while_still_blocked(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "blocked"
    assert not (repo / "executed.marker").exists()


# --- Task 2: fr run advance — agent steps NEVER execute anything ---


def test_advance_agent_step_never_invokes_a_model(tmp_path: Path, monkeypatch) -> None:
    """The structural half of no-claude-p-batch: assert nothing is executed."""
    import fr.commands.run_cmd as run_cmd

    def _boom(*args, **kwargs):
        raise AssertionError("fr run advance must never execute anything for an agent step")

    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    result = runner_cli.invoke(
        app,
        ["run", "advance", "r1"],
        env={**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)},
    )
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "running"
    # cursor does NOT advance past an agent step by itself — only a later
    # (out-of-scope-for-this-phase) completion signal would move it.
    assert state.cursor == "plan"

    brief = json.loads(result.output.split("\n", 1)[1])
    assert brief["run"] == "r1"
    assert brief["workflow"] == "agentic@1"
    assert brief["step"] == "plan"
    assert brief["skill"] == "super-fr:fr-plan"
    assert brief["agent"] is None
    assert brief["needs"] == ["spec"]
    assert brief["emits"] == ["plan", "journal:plan"]
    assert brief["tier"] == "from_phase"


def test_advance_agent_step_brief_is_re_emitted_idempotently_while_running(
    tmp_path: Path, monkeypatch
) -> None:
    import fr.commands.run_cmd as run_cmd

    def _boom(*args, **kwargs):
        raise AssertionError("must never execute anything for an agent step")

    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "running"


# --- fr run resolve — the only way an agent step's cursor can move (spec §4.B,
# added in Phase 7 review: the original 4-command CLI was a functional dead end,
# since `advance` deliberately never executes an `agent` step) ---


def test_resolve_done_completes_the_step_and_advances_the_cursor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])  # marks brainstorm running, emits brief
    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "brainstorm",
            "--state",
            "done",
            "--emitted",
            "spec=docs/superpowers/specs/2026-08-14-x-design.md",
        ],
    )
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "done"
    assert state.steps["brainstorm"].emitted == {
        "spec": "docs/superpowers/specs/2026-08-14-x-design.md"
    }
    assert state.cursor == "after"

    # the run is not wedged: advance now executes the next (cli) step normally.
    result2 = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result2.exit_code == 0, result2.output
    state2 = load_run_state(repo, "r1")
    assert state2.steps["after"].state == "done"


def test_resolve_failed_leaves_the_cursor_put_same_as_advance(tmp_path: Path) -> None:
    """Same asymmetry `advance` already has for `cli` steps: `failed` records
    the outcome but does not move the cursor — reused, not forked."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "failed"])
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "failed"
    assert state.cursor == "plan"


def test_resolve_refuses_a_step_that_is_not_running(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    # never advanced -> "plan" is still pending, not running
    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"])
    assert result.exit_code != 0
    assert "running" in result.output.lower()
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "pending"


def test_resolve_refuses_a_cli_step_pointing_at_advance_instead(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "hello", "--state", "done"])
    assert result.exit_code != 0
    assert "advance" in result.output.lower()
    state = load_run_state(repo, "r1")
    assert state.steps["hello"].state == "pending"


def test_resolve_never_invokes_a_model_either(tmp_path: Path, monkeypatch) -> None:
    import fr.commands.run_cmd as run_cmd

    def _boom(*args, **kwargs):
        raise AssertionError("fr run resolve must never execute anything")

    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"])
    assert result.exit_code == 0, result.output


# --- Task 2: fr run status / check ---


def test_status_prints_cursor_and_per_step_states(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "status", "r1"])
    assert result.exit_code == 0, result.output
    assert "cursor: hello" in result.output
    assert "hello: pending" in result.output
    assert "bye: pending" in result.output


def test_check_exits_zero_when_cursor_is_not_failed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "check", "r1"])
    assert result.exit_code == 0, result.output


def test_check_exits_nonzero_when_cursor_sits_on_a_failed_step(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "fails", _FAILING_SHAPE)
    _invoke(repo, shipped, ["run", "start", "fails", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(repo, shipped, ["run", "check", "r1"])
    assert result.exit_code != 0
