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

import pytest
from fr.cli import app
from fr.run.model import load_run_state
from fr_dispatch.work_item import run_item_id
from typer.testing import CliRunner

runner_cli = CliRunner()


def _repo(tmp_path: Path, branch: str = "b") -> Path:
    """A repo that IS an isolation workspace — a REAL linked worktree.

    `fr run start` ensures isolation itself and writes the run inside the
    resulting worktree (spec §4.B, review fix r2-f5), so the marker is part of
    the precondition every one of these tests operates under — not a test
    convenience. `tests/unit/test_run_workspace.py` covers the paths where the
    marker is absent, stale, or names another branch.

    FIXTURE CHANGE, assertions unchanged (review r5-e3): the marker's `mode` is
    now corroborated, and `mode: worktree` means "this IS a linked worktree"
    (`git rev-parse --git-common-dir` != `--git-dir`) — the same structural
    check the `fr-isolation-required` PreToolUse hook makes. A marker written
    into a bare directory is exactly the forgery the check exists to refuse, so
    the fixture has to be the real thing.
    """
    import subprocess

    base = tmp_path / "base"
    base.mkdir(parents=True, exist_ok=True)

    def git(root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
    git(base, "config", "user.email", "t@example.com")
    git(base, "config", "user.name", "T")
    (base / "seed.md").write_text("seed\n")
    git(base, "add", "-A")
    git(base, "commit", "-qm", "seed")

    workspace = tmp_path / "workspace"
    git(base, "worktree", "add", "-q", "-b", branch, str(workspace))

    (workspace / "docs" / "superpowers" / "workflows").mkdir(parents=True, exist_ok=True)
    (workspace / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": str(workspace.resolve()),
                "branch": branch,
                "mode": "worktree",
                "created_at": "2026-08-27T00:00:00+00:00",
            }
        )
    )
    return workspace


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
unit: spec
steps:
  - id: plan
    kind: agent
    skill: super-fr:fr-plan
    needs: [spec]
    emits: [plan, journal:plan]
    tier: from_phase
"""
"""`unit: spec`, not `unit: run` — changed with `fr run start`'s new
`check_workflow` gate (review r5-b6). The step `needs: [spec]` and no step
emits it, which for a `unit: run` shape is a dangling need
(`IMPLIED_INPUTS_BY_UNIT["run"]` seeds nothing) and now refuses the start.
A `unit: spec` shape is seeded with `spec`, so the SAME step graph — the one
every assertion below is about — is valid. `unit` is not read by `fr run`
at all; it only decides dispatch granularity."""

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

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    # Installed AFTER `start`: `start` legitimately shells out to git to verify
    # the isolation marker's `mode` (review r5-e3). The claim under test is
    # about `advance`, and it is unchanged.
    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)
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

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)  # see the test above
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
    # `--emitted` records artifacts that were actually written (review r5-e2),
    # so the fixture writes the one it is about to report. Assertions unchanged.
    spec = repo / "docs" / "superpowers" / "specs" / "2026-08-14-x-design.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x\n")
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

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)  # see the advance tests
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
    (repo / "s.md").write_text("# spec\n")  # `--emitted` now requires it to exist
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


_VALID_NO_RUN_SHAPE = _NO_RUN_SHAPE.replace(
    "  - id: silent\n    kind: cli\n", '  - id: silent\n    kind: cli\n    run: "true"\n'
)
"""The same step graph, valid — see the test below for why it is needed."""


def test_advance_refuses_a_cli_step_with_no_run_command(tmp_path: Path) -> None:
    """`subprocess.run("", shell=True)` exits 0, so an omitted `run:` used to
    report a green step that did nothing and move the cursor on.

    HOW THE SHAPE GETS THERE CHANGED, the behaviour asserted did not (review
    r5-b6): `fr run start` now runs `check_workflow` on the resolved
    manifest, so it refuses a `kind: cli` step with no `run:` up front and
    the run never exists. The remaining way to reach `advance` with one is
    the realistic one — the manifest is EDITED mid-run, which is exactly the
    hand-built/edited case this guard was always for. Every assertion below
    is unchanged.
    """
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "no-run", _VALID_NO_RUN_SHAPE)
    started = _invoke(repo, shipped, ["run", "start", "no-run", "--branch", "b", "--run-id", "r1"])
    assert started.exit_code == 0, started.output
    _write_shape(shipped, "no-run", _NO_RUN_SHAPE)  # operator edits the shape mid-run

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
    and must not be able to inject a command.

    FIXTURE CHANGE, assertions unchanged (review r5-e2): `--emitted` now
    refuses a repo-tracked artifact that is not on disk, so the hostile value
    is a file that really EXISTS with that name. `; touch <marker>` is a legal
    POSIX filename, which makes this a stronger test than the old one — the
    value survives every validation the real path takes and still must not
    execute.
    """
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "hostile", _HOSTILE_SHAPE)
    # A RELATIVE marker: the filename must be one path segment (it is a real
    # file), and the `cli` step runs with cwd at the workspace root, so an
    # unquoted interpolation would create it right here.
    marker = repo / "pwned"
    hostile_name = "plan.md; touch pwned"
    (repo / hostile_name).write_text("a plan with a hostile NAME\n")
    _invoke(repo, shipped, ["run", "start", "hostile", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    resolved = _invoke(
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
            f"plan={hostile_name}",
        ],
    )
    assert resolved.exit_code == 0, resolved.output

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert not marker.exists(), "an emitted value was interpolated into a shell unquoted"
    state = load_run_state(repo, "r1")
    assert state.steps["consume"].stdout is not None
    assert hostile_name in state.steps["consume"].stdout


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


# ── review r5-b1: `--run-id` is operator input and becomes a path ──────


def test_start_refuses_a_traversing_run_id(tmp_path: Path) -> None:
    """`--run-id ../../../escaped` exited 0 and wrote the run file OUTSIDE
    `runs/` — the success line prints the id, not the path, so the escape
    was invisible."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "../../../escaped"],
    )

    assert result.exit_code == 2, result.output
    assert list(tmp_path.rglob("escaped.yaml")) == []


def test_start_refuses_a_run_id_with_a_slash(tmp_path: Path) -> None:
    """`weird/id` wrote `runs/weird/id.yaml` — invisible to
    `find_run_for_plan`'s non-recursive glob, and rejected by
    `run_item_id`, so the run could never be archived OR dispatched."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(
        repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "weird/id"]
    )

    assert result.exit_code == 2, result.output
    assert not (repo / "docs" / "superpowers" / "runs" / "weird").exists()


def test_the_run_id_rule_is_at_least_as_strict_as_run_item_ids() -> None:
    """`fr` may not import `fr_dispatch`, so the rule is duplicated. This
    pins the duplicate to its original in both directions: everything
    `validate_run_id` ACCEPTS, `run_item_id` accepts too, and everything
    `run_item_id` rejects, `validate_run_id` rejects as well.

    It is deliberately *stricter* on `.` and `..`: those are legal id
    segments but illegal file stems, and a run id is both.
    """
    import pytest
    from fr.run.model import RunStateError, validate_run_id

    for bad in ("", "a/b", "../../escape"):
        with pytest.raises(RunStateError):
            validate_run_id(bad)
        with pytest.raises(ValueError):
            run_item_id("acme/demo", bad)

    for file_hostile in (".", ".."):
        with pytest.raises(RunStateError):
            validate_run_id(file_hostile)

    for good in ("2026-08-31-feat-x", "r1", "2026-08-14-ticket-polling"):
        assert validate_run_id(good) == good
        assert run_item_id("acme/demo", good).endswith(f"/run/{good}")


# ── review r5-b2: an absolute `--emitted` path breaks run↔plan matching ─

_EMIT_SHAPE = """
workflow: emitter
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan, pr]
  - id: after
    kind: cli
    run: "true"
"""
"""`emits: [plan, pr]` — `--emitted` refuses an artifact the step does not
declare (review r5-e2), and the `pr` case below is about a NON-repo-tracked
artifact being stored verbatim, so the shape has to declare it."""


def _started_emitter(tmp_path: Path):
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "emitter", _EMIT_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "emitter", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def test_an_absolute_emitted_plan_path_is_stored_repo_relative(tmp_path: Path) -> None:
    """Stored verbatim, an absolute path matched neither
    `archive.find_run_for_plan` nor `adopt.adoptable_plans` — both compare
    against a repo-relative posix path, so both silently no-opped."""
    from fr.archive import find_run_for_plan

    repo, shipped = _started_emitter(tmp_path)
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-08-31-demo"
    plan_dir.mkdir(parents=True)

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            f"plan={plan_dir}",
        ],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].emitted == {"plan": "docs/superpowers/plans/2026-08-31-demo"}
    assert find_run_for_plan(repo, Path("docs/superpowers/plans/2026-08-31-demo")) == "r1"


def test_an_emitted_path_outside_the_repo_is_refused(tmp_path: Path) -> None:
    repo, shipped = _started_emitter(tmp_path)
    outside = tmp_path.parent / "elsewhere" / "plan"

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            f"plan={outside}",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "outside the repo" in result.output


def test_a_non_repo_tracked_artifact_is_stored_verbatim(tmp_path: Path) -> None:
    """`pr` is a URL and `report`/`journal:*` have no repo path — rewriting
    them as repo-relative would be nonsense."""
    repo, shipped = _started_emitter(tmp_path)

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            "pr=https://github.com/acme/demo/pull/7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["plan"].emitted == {
        "pr": "https://github.com/acme/demo/pull/7"
    }


# ── review r5-b3: `advance` must not re-open a finished run ────────────


def test_advance_on_a_finished_run_does_not_reopen_its_last_step(tmp_path: Path) -> None:
    """After the last step is `done` and `fr run check` exits 0, one more
    `advance` flipped it back to `running` — and for a `cli` last step
    would have re-executed the command."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert load_run_state(repo, "r1").steps["bye"].state == "done"
    before = (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text()

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "complete" in result.output
    assert (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text() == before


def test_a_finished_agent_run_is_not_re_dispatched(tmp_path: Path) -> None:
    """The `cli` case would re-execute; the `agent` case re-emitted a brief
    and marked a done step `running`, so a harness would dispatch it again."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "agentic", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert (
        _invoke(
            repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"]
        ).exit_code
        == 0
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "dispatch brief" not in result.output
    assert load_run_state(repo, "r1").steps["plan"].state == "done"


# =========================================================================
# review r5-e1: a run id is a filename, an item-id segment and a shell token
# =========================================================================


@pytest.mark.parametrize(
    "bad",
    [
        "   ",  # whitespace only
        "\t",
        "-weird",  # git reads a leading dash as a pathspec, argparse as an option
        "--help",
        "a\\b",  # a separator on the other platform, an escape in most shells
        "a\x00b",  # NUL: unrepresentable in a filename
        "a\nb",  # control character: invisible in a terminal
        "a b",  # one token that silently becomes two
        "a:b",
        "a*b",
        "café",  # non-ASCII: encodable, but not portably comparable
        "." * 3,
        "x" * 129,  # over RUN_ID_MAX_LENGTH
    ],
)
def test_validate_run_id_is_an_allowlist_not_a_denylist(bad: str) -> None:
    """A denylist of `/` and `..` still admitted a leading `-`, a backslash, a
    NUL, whitespace and a 4000-character name."""
    from fr.run.model import RunStateError, validate_run_id

    with pytest.raises(RunStateError):
        validate_run_id(bad)


@pytest.mark.parametrize("good", ["r1", "2026-08-31-feat-x", "a.b_c-1", "X", "9", "x" * 128])
def test_validate_run_id_admits_ordinary_ids(good: str) -> None:
    from fr.run.model import validate_run_id

    assert validate_run_id(good) == good


@pytest.mark.parametrize(
    ("branch", "expect_tail"),
    [
        ("feat/ticket-polling", "feat-ticket-polling"),
        ("feat/../x", "feat-..-x"),
        ("-weird", "weird"),
        ("wip #3", "wip-3"),
        ("feat/Ünicode", "feat-nicode"),
        ("///", None),
    ],
)
def test_derive_run_id_always_produces_a_valid_id(branch: str, expect_tail: str | None) -> None:
    """`derive_run_id` FEEDS `validate_run_id`, so a legal git branch must
    never produce an id the validator then refuses — that would make
    `fr run start` impossible on that branch."""
    import datetime as _dt

    from fr.commands.run_cmd import derive_run_id
    from fr.run.model import validate_run_id

    derived = derive_run_id(branch, today=_dt.date(2026, 8, 31))

    assert validate_run_id(derived) == derived
    if expect_tail is None:
        assert derived == "2026-08-31"
    else:
        assert derived == f"2026-08-31-{expect_tail}"


def test_derive_run_id_stays_within_the_length_limit() -> None:
    import datetime as _dt

    from fr.commands.run_cmd import derive_run_id
    from fr.run.model import RUN_ID_MAX_LENGTH, validate_run_id

    derived = derive_run_id("feat/" + "x" * 500, today=_dt.date(2026, 8, 31))

    assert len(derived) <= RUN_ID_MAX_LENGTH
    assert validate_run_id(derived) == derived


def test_start_refuses_a_run_id_colliding_only_by_case(tmp_path: Path) -> None:
    """macOS/APFS and Windows are case-insensitive, so `Run-1` and `run-1` are
    one file there and two on Linux."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _write_shape(shipped, "other", _CLI_ONLY_SHAPE.replace("workflow: cli-only", "workflow: other"))
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "run-1"]
        ).exit_code
        == 0
    )

    result = _invoke(
        repo, shipped, ["run", "start", "other", "--branch", "feat/x", "--run-id", "Run-1"]
    )

    assert result.exit_code == 2, result.output
    assert "only by case" in result.output


# --- review r5-e5: a second run on the same branch and shape --------------


def test_start_refuses_a_second_run_of_the_same_shape_on_this_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )

    result = _invoke(
        repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r2"]
    )

    assert result.exit_code == 2, result.output
    assert "already has a" in result.output
    assert "fr run status r1" in result.output
    assert not (repo / "docs" / "superpowers" / "runs" / "r2.yaml").exists()


def test_a_different_shape_on_the_same_branch_is_allowed(tmp_path: Path) -> None:
    """The refusal is about the same SHAPE, not about the branch: a research
    run alongside a delivery run is a legitimate thing to want."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _write_shape(shipped, "other", _CLI_ONLY_SHAPE.replace("workflow: cli-only", "workflow: other"))
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )

    result = _invoke(
        repo, shipped, ["run", "start", "other", "--branch", "feat/x", "--run-id", "r2"]
    )

    assert result.exit_code == 0, result.output


def test_start_refuses_a_shape_that_does_not_validate(tmp_path: Path) -> None:
    """review r5-b6/e5: `check_workflow` runs on the RESOLVED manifest, before
    isolation is ensured — a bad shape costs no worktree and no container."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "dangling",
        "workflow: dangling\nschema: 1\nunit: run\n"
        "steps:\n  - id: a\n    kind: agent\n    needs: [ghost]\n",
    )

    result = _invoke(
        repo, shipped, ["run", "start", "dangling", "--branch", "feat/x", "--run-id", "r1"]
    )

    assert result.exit_code == 2, result.output
    assert "ghost" in result.output
    assert not (repo / "docs" / "superpowers" / "runs").exists()


# =========================================================================
# review r5-e2: `--emitted` is data an agent reports; validate it
# =========================================================================


def _emitting_repo(tmp_path: Path):
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "emitter", _EMIT_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "emitter", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _resolve(repo: Path, shipped: Path, *emitted: str):
    argv = ["run", "resolve", "r1", "--step", "plan", "--state", "done"]
    for pair in emitted:
        argv += ["--emitted", pair]
    return _invoke(repo, shipped, argv)


def test_an_emitted_path_containing_an_equals_sign_is_not_truncated(tmp_path: Path) -> None:
    """Split on the FIRST `=` only. A path may legitimately contain one."""
    repo, shipped = _emitting_repo(tmp_path)
    odd = repo / "docs" / "superpowers" / "plans" / "a=b"
    odd.mkdir(parents=True)

    result = _resolve(repo, shipped, "plan=docs/superpowers/plans/a=b")

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["plan"].emitted == {
        "plan": "docs/superpowers/plans/a=b"
    }


@pytest.mark.parametrize("pair", ["plan=", "=x", "   =x", "plan=   "])
def test_an_empty_emitted_name_or_value_is_refused(tmp_path: Path, pair: str) -> None:
    """`plan=` records the repo ROOT as the plan — the most wrong value
    available, and the one an empty shell variable produces."""
    repo, shipped = _emitting_repo(tmp_path)

    result = _resolve(repo, shipped, pair)

    assert result.exit_code == 2, result.output
    assert "empty" in result.output


def test_an_artifact_the_step_does_not_emit_is_refused_naming_the_declared_ones(
    tmp_path: Path,
) -> None:
    """An artifact the manifest never mentions is a shape/agent mismatch. The
    run would carry a key nothing will ever read."""
    repo, shipped = _emitting_repo(tmp_path)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "specs" / "x.md").write_text("# x\n")

    result = _resolve(repo, shipped, "spec=docs/superpowers/specs/x.md")

    assert result.exit_code == 2, result.output
    assert "does not emit 'spec'" in result.output
    assert "plan" in result.output  # names what it DOES emit


def test_the_same_artifact_given_twice_is_refused(tmp_path: Path) -> None:
    repo, shipped = _emitting_repo(tmp_path)
    for name in ("a", "b"):
        (repo / "docs" / "superpowers" / "plans" / name).mkdir(parents=True)

    result = _resolve(
        repo,
        shipped,
        "plan=docs/superpowers/plans/a",
        "plan=docs/superpowers/plans/b",
    )

    assert result.exit_code == 2, result.output
    assert "twice" in result.output


def test_an_emitted_artifact_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    repo, shipped = _emitting_repo(tmp_path)

    result = _resolve(repo, shipped, "plan=docs/superpowers/plans/never-written")

    assert result.exit_code == 2, result.output
    assert "does not exist" in result.output


def test_symlinked_roots_on_both_sides_still_resolve_relative(tmp_path: Path) -> None:
    """An fr worktree lives under `~/.cache`, which on macOS is reached
    through `/private/var/...`. Resolving only ONE side left a file plainly
    inside the repo with no common prefix, and `relative_to` raised."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    repo, shipped = _emitting_repo(link)
    # `repo` is reached through the SYMLINK; the artifact is named through the
    # REAL path. Only resolving both sides makes them the same repository.
    assert str(repo).startswith(str(link))
    (repo / "docs" / "superpowers" / "plans" / "p").mkdir(parents=True)
    through_real = repo.resolve() / "docs" / "superpowers" / "plans" / "p"
    assert str(through_real).startswith(str(real))

    result = _resolve(repo, shipped, f"plan={through_real}")

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["plan"].emitted == {"plan": "docs/superpowers/plans/p"}


# =========================================================================
# review r5-e3: terminal states, a missing file, and a shape that moved
# =========================================================================


def test_resolve_on_a_completed_run_is_refused_like_advance(tmp_path: Path) -> None:
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "agentic", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert (
        _invoke(
            repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"]
        ).exit_code
        == 0
    )

    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"])

    assert result.exit_code == 2, result.output
    assert "complete" in result.output


def test_amending_emitted_on_a_completed_run_is_still_allowed(tmp_path: Path) -> None:
    """A wrong `emitted` on a `done` step was unamendable — and it is the key
    `fr archive` and `fr run adopt` match on."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    (repo / "docs" / "superpowers" / "plans" / "right").mkdir(parents=True)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "agentic", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert (
        _invoke(
            repo, shipped, ["run", "resolve", "r1", "--step", "plan", "--state", "done"]
        ).exit_code
        == 0
    )
    before_cursor = load_run_state(repo, "r1").cursor

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            "plan=docs/superpowers/plans/right",
        ],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].emitted == {"plan": "docs/superpowers/plans/right"}
    assert state.steps["plan"].state == "done"
    assert state.cursor == before_cursor, "amending must not move the cursor"


@pytest.mark.parametrize("verb", ["status", "advance", "resolve", "check"])
def test_a_missing_run_file_exits_two_naming_it(tmp_path: Path, verb: str) -> None:
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    argv = ["run", verb, "nope"]
    if verb == "resolve":
        argv += ["--step", "hello", "--state", "done"]

    result = _invoke(repo, shipped, argv)

    assert result.exit_code == 2, result.output
    assert "nope.yaml" in result.output.replace("\n", "")


@pytest.mark.parametrize("verb", ["status", "advance", "resolve", "check"])
def test_an_unparseable_run_file_exits_two_never_tracebacks(tmp_path: Path, verb: str) -> None:
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("cursor: [unclosed\n")
    argv = ["run", verb, "r1"]
    if verb == "resolve":
        argv += ["--step", "hello", "--state", "done"]

    result = _invoke(repo, shipped, argv)

    assert result.exit_code == 2, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def _started_two_step(tmp_path: Path):
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )
    return repo, shipped


@pytest.mark.parametrize(
    ("mutated", "expect"),
    [
        # a step ADDED
        (
            _CLI_ONLY_SHAPE + '  - id: extra\n    kind: cli\n    run: "true"\n',
            "added: extra",
        ),
        # a step REMOVED
        (
            _CLI_ONLY_SHAPE.replace('  - id: bye\n    kind: cli\n    run: "true"\n', ""),
            "removed: bye",
        ),
        # a step RENAMED — both halves reported
        (_CLI_ONLY_SHAPE.replace("- id: bye", "- id: farewell"), "added: farewell"),
    ],
)
def test_a_shape_whose_steps_moved_is_refused_with_a_diff(
    tmp_path: Path, mutated: str, expect: str
) -> None:
    """A run's cursor is a position in a step list. A step added, removed or
    renamed used to surface as a `KeyError` or a `ValueError` from
    `list.index` deep inside `advance` — or, for an added step, as nothing at
    all: the new step silently never ran."""
    repo, shipped = _started_two_step(tmp_path)
    _write_shape(shipped, "cli-only", mutated)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert expect in result.output.replace("\n", "")


def test_a_shape_whose_schema_version_moved_is_refused(tmp_path: Path) -> None:
    """`state.workflow` is `"<name>@<schema>"`. The suffix used to be sliced
    off and discarded, so a run kept advancing against a step grammar its
    cursor was never computed for."""
    repo, shipped = _started_two_step(tmp_path)
    assert load_run_state(repo, "r1").workflow == "cli-only@1"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE.replace("schema: 1", "schema: 2"))

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "schema" in result.output


def test_an_unchanged_shape_still_advances(tmp_path: Path) -> None:
    """The drift check must not fire on the ordinary case."""
    repo, shipped = _started_two_step(tmp_path)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["hello"].state == "done"


def test_start_resolves_the_shape_inside_the_workspace(tmp_path: Path) -> None:
    """`advance` runs in the WORKSPACE, and a repo override lives at
    `docs/superpowers/workflows/<name>.yaml` — a different file in the base
    clone and in the worktree. Starting against one and advancing against the
    other is the drift case, arranged by fr itself (review r5-e3)."""
    import subprocess

    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    # A repo override that exists ONLY in the workspace.
    override = repo / "docs" / "superpowers" / "workflows" / "cli-only.yaml"
    override.write_text(
        "workflow: cli-only\nschema: 1\nunit: run\n"
        "steps:\n  - id: only-here\n    kind: cli\n    run: 'true'\n"
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)

    assert (
        _invoke(
            repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
        ).exit_code
        == 0
    )

    assert set(load_run_state(repo, "r1").steps) == {"only-here"}
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
