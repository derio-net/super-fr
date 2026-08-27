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


def _repo(tmp_path: Path, branch: str = "b") -> Path:
    """A repo that IS an isolation workspace.

    `fr run start` ensures isolation itself and writes the run inside the
    resulting worktree (spec §4.B, review fix r2-f5), so the marker is part of
    the precondition every one of these tests operates under — not a test
    convenience. `tests/unit/test_run_workspace.py` covers the paths where the
    marker is absent, stale, or names another branch.
    """
    (tmp_path / "docs" / "superpowers" / "workflows").mkdir(parents=True)
    (tmp_path / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": str(tmp_path.resolve()),
                "branch": branch,
                "mode": "worktree",
                "created_at": "2026-08-27T00:00:00+00:00",
            }
        )
    )
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
    repo = _repo(tmp_path, branch="feat/x")
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
    repo = _repo(tmp_path, branch="feat/ticket-polling")
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
    repo = _repo(tmp_path, branch="myb")
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


# ---------------------------------------------------------------------------
# Milestone-review fixes (r2). Each block names the finding it pins.
# ---------------------------------------------------------------------------

_GATED_AGENT_SHAPE = """
workflow: gated-agent
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    gate: operator
    emits: [spec]
  - id: after
    kind: cli
    run: "true"
"""

_THREE_AGENT_SHAPE = """
workflow: three-agents
schema: 1
unit: run
steps:
  - id: first
    kind: agent
    skill: s:one
  - id: second
    kind: agent
    skill: s:two
  - id: third
    kind: agent
    skill: s:three
"""

_NO_RUN_SHAPE = """
workflow: no-run
schema: 1
unit: run
steps:
  - id: silent
    kind: cli
  - id: after
    kind: cli
    run: "true"
"""

_HOSTILE_SHAPE = """
workflow: hostile
schema: 1
unit: run
steps:
  - id: emit
    kind: agent
    emits: [plan]
  - id: consume
    kind: cli
    run: echo {{ artifacts.plan }}
"""


def _brief_of(output: str) -> dict:
    """The JSON brief `advance` prints, wherever in the output it sits (a
    gated agent step prints the gate line first)."""
    return json.loads(output[output.index("{") :])


# --- r2-f1: a `gate: operator` step must be clearable, not a dead end -------


def test_resolve_clears_a_blocked_agent_step_and_advances_the_cursor(tmp_path: Path) -> None:
    """The shipped `fr-goal` `brainstorm` step is `kind: agent` + `gate:
    operator`; before this fix `advance` marked it `blocked` and `resolve`
    refused anything not `running`, so the run wedged on step 2 forever."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"

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
            "spec=s.md",
        ],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "done"
    assert state.steps["brainstorm"].emitted == {"spec": "s.md"}
    assert state.cursor == "after"

    # and the run keeps going — the point of the fix
    result2 = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result2.exit_code == 0, result2.output
    assert load_run_state(repo, "r1").steps["after"].state == "done"


def test_advance_onto_a_gated_agent_step_still_prints_the_dispatch_brief(tmp_path: Path) -> None:
    """A gate stops the RUN, not the harness's ability to see what the step
    is: without the brief a generic harness has no skill/agent to dispatch
    and could never produce the answer the gate is waiting for."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "blocked on operator gate" in result.output
    brief = _brief_of(result.output)
    assert brief["step"] == "brainstorm"
    assert brief["skill"] == "super-fr:fr-brainstorming"
    assert brief["gate"] == "operator"


def test_resolving_a_blocked_cli_step_clears_the_gate_but_does_not_execute_it(
    tmp_path: Path,
) -> None:
    """A `cli` step's verdict is its exit code (spec §4.A). Clearing its gate
    therefore authorizes `advance` to run it — it never declares it done, or
    an operator could report success for a command that never ran."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo, shipped, ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done"]
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "pending"
    assert state.steps["brainstorm"].gate == "cleared"
    assert state.cursor == "brainstorm"
    assert not (repo / "executed.marker").exists(), "resolve must never execute a cli step"

    # the NEXT advance executes it and records the real exit code
    result2 = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result2.exit_code == 0, result2.output
    state2 = load_run_state(repo, "r1")
    assert state2.steps["brainstorm"].state == "done"
    assert state2.steps["brainstorm"].exit == 0
    assert state2.cursor == "after"
    assert (repo / "executed.marker").exists()


def test_a_declined_operator_gate_fails_the_step_and_leaves_the_cursor_put(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo, shipped, ["run", "resolve", "r1", "--step", "brainstorm", "--state", "failed"]
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "failed"
    assert state.cursor == "brainstorm"
    assert not (repo / "executed.marker").exists()


def test_a_cleared_gate_stays_cleared_across_a_retry(tmp_path: Path) -> None:
    """`_complete_step` must carry the gate marker forward: an operator
    authorizes a step once, and a re-`advance` after a failure must not
    silently re-block on a gate that was already answered."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "gated-fail",
        "workflow: gated-fail\nschema: 1\nunit: run\n"
        'steps:\n  - id: boom\n    kind: cli\n    gate: operator\n    run: "false"\n',
    )
    _invoke(repo, shipped, ["run", "start", "gated-fail", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "boom", "--state", "done"])
    _invoke(repo, shipped, ["run", "advance", "r1"])  # executes, fails
    assert load_run_state(repo, "r1").steps["boom"].state == "failed"

    result = _invoke(repo, shipped, ["run", "advance", "r1"])  # retry

    assert result.exit_code != 0  # failed again — NOT silently re-blocked
    state = load_run_state(repo, "r1")
    assert state.steps["boom"].state == "failed"
    assert state.steps["boom"].gate == "cleared"


def test_resolve_still_refuses_an_ungated_cli_step_pointing_at_advance(tmp_path: Path) -> None:
    """The gate-clearing path must not become a back door for declaring an
    ordinary `cli` step done by hand."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "hello", "--state", "done"])
    assert result.exit_code != 0
    assert "advance" in result.output.lower()
    assert load_run_state(repo, "r1").steps["hello"].state == "pending"


# --- r2-f2: a `kind: cli` step with no `run:` must never report success -----


def test_advance_refuses_a_cli_step_with_no_run_command(tmp_path: Path) -> None:
    """`subprocess.run("", shell=True)` exits 0, so an omitted `run:` used to
    report a green step that did nothing and move the cursor on."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "no-run", _NO_RUN_SHAPE)
    _invoke(repo, shipped, ["run", "start", "no-run", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code != 0
    assert "run:" in result.output
    state = load_run_state(repo, "r1")
    assert state.steps["silent"].state != "done"
    assert state.cursor == "silent"


# --- r2-f3: an emitted artifact is data, not shell source ------------------


def test_a_hostile_emitted_artifact_is_quoted_not_executed(tmp_path: Path) -> None:
    """`{{ artifacts.* }}` values come from `fr run resolve --emitted`, i.e.
    from whatever a dispatched agent reports — they are never operator-authored
    and must not be able to inject a command."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "hostile", _HOSTILE_SHAPE)
    marker = tmp_path / "pwned"
    _invoke(repo, shipped, ["run", "start", "hostile", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "emit",
            "--state",
            "done",
            "--emitted",
            f"plan=plan.md; touch {marker}",
        ],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert not marker.exists(), "an emitted value was interpolated into a shell unquoted"
    state = load_run_state(repo, "r1")
    assert state.steps["consume"].stdout is not None
    assert f"plan.md; touch {marker}" in state.steps["consume"].stdout


# --- r2-f4: the dispatch brief must be exhaustive of Step's agent fields ----


def test_the_dispatch_brief_carries_for_each_and_gate(tmp_path: Path) -> None:
    """`implement`'s whole purpose is fanning out one executor per phase; a
    harness driving off the brief could not know that without `for_each`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "fanout",
        "workflow: fanout\nschema: 1\nunit: run\n"
        "steps:\n  - id: implement\n    kind: agent\n"
        "    agent: super-fr:fr-phase-executor\n    for_each: phase\n    gate: operator\n",
    )
    _invoke(repo, shipped, ["run", "start", "fanout", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    brief = _brief_of(result.output)
    assert brief["for_each"] == "phase"
    assert brief["gate"] == "operator"


def test_the_dispatch_brief_is_exhaustive_of_steps_agent_relevant_fields(tmp_path: Path) -> None:
    """Derived from the model, not restated: a new `Step` field is carried by
    the brief or this fails. `id` is emitted as `step`, and `run` is the one
    cli-only field (`advance` executes it; it is never dispatched)."""
    from fr.workflow.model import Step

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])

    brief = _brief_of(_invoke(repo, shipped, ["run", "advance", "r1"]).output)

    step_fields = set(Step.model_fields) - {"id", "run"}
    # `run`/`workflow`/`step` are the run-identity keys the brief adds on top.
    assert set(brief) == step_fields | {"run", "workflow", "step"}


# --- r2-f7: a manifest that grew a step must not traceback -----------------


def test_advance_reports_a_cursor_with_no_step_record_instead_of_tracebacking(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])
    run_file = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    run_file.write_text(run_file.read_text().replace("  hello:", "  gone:"))

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2
    assert "hello" in result.output
    assert "Traceback" not in result.output


# --- r2-f8: resolving a non-cursor step must never rewind the run ----------


def test_resolving_a_non_cursor_step_does_not_rewind_the_cursor(tmp_path: Path) -> None:
    """`_complete_step` used to set the cursor to `_next_step_id(<resolved
    step>)` unconditionally, so completing anything behind the cursor rewound
    the run. The cursor moves off the cursor, or not at all."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "three-agents", _THREE_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "three-agents", "--branch", "b", "--run-id", "r1"])
    run_file = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    run_file.write_text(
        run_file.read_text()
        .replace("cursor: first", "cursor: third")
        .replace("  first:\n    state: pending", "  first:\n    state: running")
        .replace("  third:\n    state: pending", "  third:\n    state: running")
    )

    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "first", "--state", "done"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["first"].state == "done"
    assert state.cursor == "third", "resolving a step behind the cursor rewound the run"


def test_the_dispatch_brief_survives_a_narrow_terminal(tmp_path: Path) -> None:
    """The brief is machine-facing: a harness parses it off stdout. Rich folds
    a long token mid-string by default, which would emit invalid JSON exactly
    when a value is long (an emitted path, a qualified agent name)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "wide",
        "workflow: wide\nschema: 1\nunit: run\nsteps:\n  - id: implement\n    kind: agent\n"
        "    agent: super-fr:fr-phase-executor-with-a-deliberately-very-long-name\n"
        "    for_each: phase\n",
    )
    env = {
        **os.environ,
        "VK_REPO_ROOT": str(repo),
        "FR_SHIPPED_WORKFLOWS_DIR": str(shipped),
        "COLUMNS": "40",
    }
    runner_cli.invoke(app, ["run", "start", "wide", "--branch", "b", "--run-id", "r1"], env=env)

    result = runner_cli.invoke(app, ["run", "advance", "r1"], env=env)

    assert result.exit_code == 0, result.output
    brief = json.loads(result.output[result.output.index("{") :])
    assert brief["agent"] == "super-fr:fr-phase-executor-with-a-deliberately-very-long-name"
