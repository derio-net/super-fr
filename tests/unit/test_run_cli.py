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
import re
import shlex
from pathlib import Path

import pytest
from fr.cli import app
from fr.run import units
from fr.run.model import load_run_state
from fr_dispatch.work_item import run_item_id
from typer.testing import CliRunner

# --- reading a cursor by MEANING, never by storage ---------------------------
#
# These tests were written against three maps (`StepRecord.items`,
# `StepRecord.dispatch`, top-level `RunState.accounting`) that the v5 cursor
# folds into one (`StepRecord.units`, spec 2026-09-20-unit-record-unification
# §4.A). What they ASSERT did not change — "this unit is running", "this unit
# has one attempt, claimed", "this unit's snapshot measured 100 output tokens"
# — so they read through `fr.run.units`, the one module that knows the shape,
# and the next shape change leaves this file alone.


def _attempts_by_unit(record) -> dict[str, list] | None:
    """`{unit key: [attempt, ...]}` for every unit of `record` that has any
    attempt, or `None` when none does — what `record.dispatch` used to be."""
    found = {
        key: list(units.attempts(record, key))
        for key in units.unit_keys(record)
        if units.attempts(record, key)
    }
    return found or None


class _Snapshot:
    """One unit's cost, flattened the way the v4 `PhaseAccounting` read: the
    five V1 sizes, the four V2 figures (`None` when unmeasured), and `at`."""

    def __init__(self, state, key: str) -> None:
        estimate = units.estimate_of(state, key)
        assert estimate is not None
        measured = units.measured_of(state, key)
        self.at = units.estimated_at(state, key)
        for name in type(estimate).model_fields:
            setattr(self, name, getattr(estimate, name))
        for name in units.MeasuredTokens.model_fields:
            setattr(self, name, None if measured is None else getattr(measured, name))
        self.measured_tokens = None if measured is None else measured.total


def _accounting(state) -> dict[str, _Snapshot]:
    """`{unit key: snapshot}` for every unit with a recorded cost, key-sorted."""
    return {key: _Snapshot(state, key) for key in units.accounted_keys(state)}


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


_HARNESS_DETECTION_KEYS = ("FR_HARNESS", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT")


def _invoke_as_harness(
    repo: Path, shipped: Path, argv: list[str], harness_env: dict[str, str | None]
):
    """Like `_invoke`, but with every harness-detection signal cleared first
    (`os.environ` in THIS process carries `CLAUDECODE=1` — it is a Claude
    Code session — so a test asserting "no notice on claude-code" or "an
    unrecognised harness" would silently pass or fail on the ambient
    environment rather than the one it declares). `harness_env` values of
    `None` unset a key for the invocation (click's `CliRunner.isolation`
    deletes it); anything else sets it."""
    env: dict[str, str | None] = {
        **os.environ,
        "VK_REPO_ROOT": str(repo),
        "FR_SHIPPED_WORKFLOWS_DIR": str(shipped),
    }
    # `None` (not a pop) so click's `CliRunner.isolation` actively DELETES the
    # key from the real `os.environ` for the duration of the call — a pop
    # here only edits this local dict and leaves this process's actual
    # CLAUDECODE=1 (it IS a Claude Code session) untouched underneath.
    for key in _HARNESS_DETECTION_KEYS:
        env[key] = None
    for key in list(env):
        if key.startswith(("OPENCODE", "HERMES")):
            env[key] = None
    env.update(harness_env)
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


# --- Task 2 (Phase 5): fr run advance — the harness degradation notice ---


def test_advance_prints_the_degradation_notice_on_opencode(tmp_path: Path) -> None:
    """spec §3.D.1: a `gate: operator` step blocking on a harness where
    `operator-gate` is not `enforced` prints a notice — and the notice text
    comes from the matrix row's `scope_note`, not a hardcoded string
    (otherwise the matrix is decoration)."""
    from fr.harness import load_matrix

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], {}
    )
    result = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})
    assert result.exit_code == 0, result.output
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "operator-gate")
    scope_note = surface.harnesses["opencode"].scope_note
    assert scope_note is not None
    assert scope_note in result.output, result.output
    assert "opencode" in result.output
    assert "answered_by: agent" in result.output
    assert "STOP" in result.output


def test_advance_prints_no_notice_when_the_harness_enforces_the_gate(tmp_path: Path) -> None:
    """claude-code's `operator-gate` row is `enforced`, and since debug journal
    C1 that means `resolve` VERIFIES an answered question in the session
    transcript — so it is quiet exactly when that transcript is readable. (It
    used to be quiet unconditionally, on the strength of a tool existing.)"""
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-e")
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], {}
    )
    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "advance", "r1"],
        {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s-e", "FR_TRANSCRIPT_ROOT": str(root)},
    )
    assert result.exit_code == 0, result.output
    assert "advisory" not in result.output
    assert "answered_by: agent" not in result.output


def test_advance_degrades_loudly_on_claude_code_when_it_cannot_verify(tmp_path: Path) -> None:
    """Operator decision C1 ("Both"): where the mechanism behind `enforced`
    cannot run — no readable transcript — Claude Code gets the same STOP notice
    OpenCode and Hermes do, instead of the silence the #497 run got."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], {}
    )
    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "advance", "r1"],
        {
            "CLAUDECODE": "1",
            "CLAUDE_CODE_SESSION_ID": "nobody",
            "FR_TRANSCRIPT_ROOT": str(tmp_path),
        },
    )
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "claude-code" in flat
    assert "advisory" in flat
    assert "STOP" in flat


def test_advance_prints_the_degradation_notice_when_the_harness_is_unrecognised(
    tmp_path: Path,
) -> None:
    """Fail loud (spec §3.D.1): an environment fr cannot place at all is
    treated as degraded too, not silently skipped — a wrong notice costs a
    confusing paragraph, a missing one costs a silent skipped gate."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], {}
    )
    result = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {})
    assert result.exit_code == 0, result.output
    assert "answered_by: agent" in result.output
    assert "STOP" in result.output


def test_advance_rejects_an_unrecognised_fr_harness_value(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke_as_harness(
        repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"], {}
    )
    result = _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "clawd-code"}
    )
    assert result.exit_code == 2
    assert "FR_HARNESS" in result.output


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


def test_advance_onto_a_still_held_agent_step_refuses_and_still_executes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """This test used to be `..._brief_is_re_emitted_idempotently_while_running`
    and asserted `exit_code == 0` on the second advance — i.e. it PINNED the
    behaviour gh-499 reported as the double-dispatch hazard. Phase 4 inverts
    the expectation: the second advance refuses (exit 2).

    Everything the old test actually protected is kept, because none of it
    changed: `advance` still executes nothing for an `agent` step (the
    `_boom` monkeypatch is the structural half of `no-claude-p-batch`), and
    the step is still left `running` — a refusal writes no state at all."""
    import fr.commands.run_cmd as run_cmd

    def _boom(*args, **kwargs):
        raise AssertionError("must never execute anything for an agent step")

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)  # see the test above
    _invoke(repo, shipped, ["run", "advance", "r1"])
    before = load_run_state(repo, "r1")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "ALREADY HELD" in result.output
    assert load_run_state(repo, "r1") == before  # a refusal writes nothing
    assert load_run_state(repo, "r1").steps["plan"].state == "running"


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


def test_a_run_inherited_from_the_base_branch_does_not_block_a_new_branch(
    tmp_path: Path,
) -> None:
    """Found by Test Plan item 1 on OpenCode, on merged code.

    `_existing_run_for_workflow`'s docstring claimed the scan is "scoped to the
    workspace, which IS the branch ... every run file here belongs to that
    branch by construction". That holds for runs CREATED in the workspace and
    is false for runs INHERITED by it: an fr-isolation worktree is a fresh
    checkout of `origin/main`, so it carries every run cursor ever merged and
    not yet archived. One merged `fr-goal` cursor therefore blocked every
    subsequent `fr-goal` run in the repo — the shape works exactly once between
    archives — and the refusal said "branch <new> already has a run", naming a
    branch that had none.

    Scoping the comparison to `state.branch` makes the code do what the
    docstring always said."""
    repo = _repo(tmp_path, branch="feat/new")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    # The inherited cursor: written into the runs dir the way a checkout of
    # `main` carries it, naming a DIFFERENT branch. Planted as a file rather
    # than created by a second `fr run start`, because that is how it really
    # arrives — via git, not the CLI.
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "old.yaml").write_text(
        "run: old\n"
        "workflow: cli-only@1\n"
        "branch: feat/other\n"
        "started: '2026-09-18T00:00:00+00:00'\n"
        "cursor: only\n"
        "steps:\n"
        "  only:\n"
        "    state: done\n"
    )

    result = _invoke(
        repo, shipped, ["run", "start", "cli-only", "--branch", "feat/new", "--run-id", "new"]
    )

    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "superpowers" / "runs" / "new.yaml").exists()


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


# --- nested for_each groups: per-phase sub-cursor (methodology restoration) ---

_GROUPED_SHAPE = """
workflow: grouped
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan]
  - id: implement
    kind: agent
    needs: [plan]
    for_each: phase
    tier: from_phase
    emits: [journal:plan]
    steps:
      - id: code
        kind: agent
        agent: super-fr:fr-phase-executor
        needs: [plan]
        emits: [journal:plan]
      - id: peer-review
        kind: agent
        skill: superpowers:requesting-code-review
        needs: [journal:plan]
        emits: [journal:plan]
  - id: deliver
    kind: cli
    run: "true"
    needs: [journal:plan]
"""

_FIXTURE_PLAN = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _started_grouped_with_plan(
    repo: Path,
    shipped: Path,
    plan_rel: str | None = None,
    *,
    phase_tier: str | None = None,
    strip_tier: bool = False,
) -> str:
    """Start against the grouped shape and resolve `plan` with a real
    one-phase plan on disk, so the group can enumerate its items.

    `phase_tier` writes a `tier:` into the copied fixture's phase header —
    what the shipped `fr-goal` shape's `tier: from_phase` sentinel points at.
    """
    import shutil

    if plan_rel is not None:
        # gh#519 shape: the caller already wrote the plan (e.g. `_plan_with_tags`
        # for its manual-phase coverage) and just wants it resolved onto the run.
        slug = plan_rel.rstrip("/").rsplit("/", 1)[-1]
        plan_dir = repo / plan_rel
    else:
        from tests.unit.skeleton_override import write_skeleton_override

        slug = "2026-05-09-fixture-minimal"
        plan_dir = repo / "docs" / "superpowers" / "plans" / slug
        shutil.copytree(_FIXTURE_PLAN, plan_dir)
        # One agentic phase, marked skeleton: a self-review error since debug
        # journal C2 — recorded as the sanctioned override, see the helper.
        write_skeleton_override(repo)
    # SET, never append: the shared fixture carries its OWN `tier: standard`
    # (gh#506 added one), so inserting a second key leaves a duplicate that
    # PyYAML silently resolves to the LAST occurrence — the fixture's value,
    # not the one the test asked for. That is the duplicate-key hazard
    # `.claude/rules/artifact-versioning.md` names, and it is exactly what
    # made two tests here assert against a tier they had not chosen.
    # `phase_tier=None` leaves the fixture alone (what most callers want);
    # `strip_tier=True` removes it, so "this phase declares no tier" is
    # actually true when a test says so.
    if phase_tier is not None or strip_tier:
        phase_yaml = plan_dir / "01.yaml"
        header = [ln for ln in phase_yaml.read_text().split("\n") if not ln.startswith("  tier:")]
        if phase_tier is not None:
            header.insert(header.index("  tag: agentic") + 1, f"  tier: {phase_tier}")
        phase_yaml.write_text("\n".join(header))
    _invoke(repo, shipped, ["run", "start", "grouped", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])  # plan running + brief
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
            f"plan=docs/superpowers/plans/{slug}",
        ],
    )
    assert result.exit_code == 0, result.output
    return f"docs/superpowers/plans/{slug}"


def test_advance_grouped_step_dispatches_the_first_pending_member(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    brief = _brief_of(result.output)
    assert brief["step"] == "code"
    assert brief["group"] == "implement"
    assert brief["agent"] == "super-fr:fr-phase-executor"
    assert brief["for_each"] == "phase"
    state = load_run_state(repo, "r1")
    assert state.cursor == "implement"
    assert state.steps["implement"].state == "running"


def test_advance_grouped_step_member_brief_resolves_the_phases_tier(tmp_path: Path) -> None:
    """D5: `tier` stays the manifest literal (`from_phase`); `resolved_tier`
    carries the actual tier of the phase the member brief names — read off
    the plan already parsed for `_accounting_snapshot`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)  # fixture phase 1 carries tier: standard

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    brief = _brief_of(result.output)
    assert brief["tier"] == "from_phase"
    assert brief["resolved_tier"] == "standard"


def test_advance_grouped_step_member_brief_resolved_tier_is_none_when_the_phase_declares_no_tier(
    tmp_path: Path,
) -> None:
    """The dispatch-time observable form of phase 2's untiered-plan warning:
    an agentic phase with no `tier` in its header resolves to `None`, not a
    guess and not a refusal (fail soft, matching the accounting snapshot)."""
    import shutil

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    slug = "2026-05-09-fixture-minimal-notier"
    dest = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(_FIXTURE_PLAN, dest)
    phase_file = dest / "01.yaml"
    phase_file.write_text(phase_file.read_text().replace("  tier: standard\n", ""))
    _invoke(repo, shipped, ["run", "start", "grouped", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])  # plan running + brief
    resolved = _invoke(
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
            f"plan=docs/superpowers/plans/{slug}",
        ],
    )
    assert resolved.exit_code == 0, resolved.output

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    brief = _brief_of(result.output)
    assert brief["tier"] == "from_phase"
    assert brief["resolved_tier"] is None


def test_build_brief_the_group_step_itself_carries_no_resolved_tier() -> None:
    """A group spans every phase, so there is no single tier to resolve —
    only an item-scoped member brief can answer the question (D5).
    `_build_brief` is the group/flat builder (untouched by D5); called
    directly on a `for_each` step with nested members, the same one
    `_advance_group`'s gated branch prints for a blocked group."""
    from fr.commands.run_cmd import _build_brief
    from fr.run.model import RunState
    from fr.workflow.model import Step

    group = Step(
        id="implement",
        kind="agent",
        for_each="phase",
        steps=(Step(id="code", kind="agent", agent="super-fr:fr-phase-executor"),),
    )
    state = RunState(
        run="r1",
        workflow="grouped@1",
        branch="b",
        started="2026-09-20T00:00:00Z",
        cursor="implement",
        steps={},
    )

    brief = _build_brief(group, state)

    assert "resolved_tier" not in brief


def test_resolve_member_items_completes_the_group_in_order(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    first = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
    )
    assert first.exit_code == 0, first.output
    mid = load_run_state(repo, "r1")
    assert mid.steps["implement"].state == "running"
    assert units.unit_states(mid.steps["implement"]) == {"phase/1/code": "done"}
    assert mid.cursor == "implement"

    # Each member is BRIEFED before it is resolved. This test used to resolve
    # `peer-review` straight after `code`, which fr accepted — the defect found
    # live on PR #508's Test Plan: a `done` unit no `advance` ever opened, so no
    # write-claim, no holder, no cost (`test_run_resolve_requires_advance.py`).
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # peer-review

    second = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1", "--state", "done"],
    )
    assert second.exit_code == 0, second.output
    done = load_run_state(repo, "r1")
    assert done.steps["implement"].state == "done"
    assert done.cursor == "deliver"


def test_resolve_member_failed_fails_the_group_and_holds_the_cursor(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "failed"],
    )
    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["implement"].state == "failed"
    assert state.cursor == "implement"


def test_resolve_member_with_an_artifact_neither_member_nor_group_emits_is_refused(
    tmp_path: Path,
) -> None:
    """`--emitted` names are validated against the member's (or its group's)
    declared emits — a member must not record an artifact the shape never
    mentions for it."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--state",
            "done",
            "--emitted",
            "spec=docs/spec.md",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "does not emit 'spec'" in result.output


def test_resolve_on_a_step_with_no_emits_still_refuses_emitted(tmp_path: Path) -> None:
    """Rule 3 has no member-shaped hole: a top-level step declaring no `emits`
    refuses `--emitted` even when the path exists — recording it would carry
    a key nothing will ever read."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "quiet",
        "workflow: quiet\nschema: 1\nunit: run\nsteps:\n  - id: quiet\n    kind: agent\n",
    )
    (repo / "docs" / "spec.md").write_text("# spec\n")
    _invoke(repo, shipped, ["run", "start", "quiet", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "quiet",
            "--state",
            "done",
            "--emitted",
            "spec=docs/spec.md",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "does not emit 'spec'" in result.output


def test_resolve_unknown_member_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "ghost", "--item", "phase/1", "--state", "done"],
    )
    assert result.exit_code == 2, result.output
    assert "ghost" in result.output


def test_resolve_member_for_an_unknown_phase_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/9", "--state", "done"],
    )
    assert result.exit_code == 2, result.output
    assert "phase/9" in result.output


def test_group_member_changes_are_drift(tmp_path: Path) -> None:
    """Member add/remove after start refuses with a diff, like top-level drift."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _write_shape(shipped, "grouped", _GROUPED_SHAPE.replace("peer-review", "peer-review-v2"))

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "peer-review" in result.output


def test_status_shows_group_items(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code
    _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
    )

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert "phase/1/code" in result.output


# --- V1 context accounting: advance records, status reports (phase 4) ---


def _seed_journal(repo: Path, shipped: Path) -> None:
    from fr.journal.model import journal_path

    slug = "2026-05-09-fixture-minimal"
    _invoke(
        repo,
        shipped,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            slug,
            "--kind",
            "discovery",
            "--title",
            "a find",
            "--body",
            "details",
            "--phase",
            "1",
            "--id",
            "d1",
        ],
    )
    _invoke(
        repo,
        shipped,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            slug,
            "--kind",
            "finding",
            "--title",
            "a bug",
            "--body",
            "broken",
            "--phase",
            "1",
            "--state",
            "open",
            "--id",
            "f1",
        ],
    )
    return journal_path(repo, "plan", slug)


def test_advance_records_a_context_snapshot_for_the_dispatched_unit(
    tmp_path: Path,
) -> None:
    """What the dispatched executor is about to re-read — journal size, the
    composed handoff size, spec + plan bytes — recorded under the unit's key."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    journal = _seed_journal(repo, shipped)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    snap = _accounting(load_run_state(repo, "r1"))["phase/1/code"]
    assert snap.journal_entries == 2
    assert snap.journal_lines == len(journal.read_text().splitlines())
    assert snap.handoff_chars > 0
    assert snap.spec_bytes >= 0
    assert snap.plan_bytes > 0


def test_the_attempt_is_dispatched_at_the_moment_its_estimate_was_assembled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONE timestamp (spec 2026-09-20-unit-record-unification §4.F). The
    estimate is assembled BEFORE the brief is built and the attempt is opened
    AFTER it; the attempt's `dispatched` doubles as the start of its
    measurement window, so it must be the EARLIER moment. If `_open_dispatch`
    stamped its own clock instead, the window would start after the dispatch
    it measures — invisibly, because at one-second resolution the two moments
    are almost always the same string.

    So the clock is made to TICK on every read: each `_now()` call returns a
    later second. With the two moments wired apart, `units.with_estimate`
    refuses the mismatch and this `advance` fails."""
    import datetime as dt

    import fr.commands.run_cmd as run_cmd

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    ticks = iter(range(10_000))
    start = dt.datetime(2026, 9, 20, 9, 0, 0, tzinfo=dt.UTC)
    reads: list[str] = []

    def ticking() -> str:
        moment = (start + dt.timedelta(seconds=next(ticks))).isoformat()
        reads.append(moment)
        return moment

    monkeypatch.setattr(run_cmd, "_now", ticking)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    (attempt,) = units.attempts(state.steps["implement"], "phase/1/code")
    assert attempt.estimate is not None
    assert units.estimated_at(state, "phase/1/code") == attempt.dispatched
    assert len(reads) > 1, "the clock was read once — this test cannot tell moments apart"
    assert attempt.dispatched == reads[0], (
        "`dispatched` must be the FIRST moment this advance read — before the estimate was "
        f"assembled and before the brief — not a later one (reads: {reads})"
    )


def test_advance_is_idempotent_over_the_snapshot(tmp_path: Path) -> None:
    """Re-dispatching the same unit refreshes the one snapshot rather than
    stacking them.

    The re-dispatch is `--redispatch` since phase 4: a bare second `advance`
    on a held unit now REFUSES (gh-499) and never reaches the snapshot at
    all, which would have left this test passing for a reason that has
    nothing to do with what it asserts."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    second = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert second.exit_code == 0, second.output
    accounting = _accounting(load_run_state(repo, "r1"))

    assert list(accounting) == ["phase/1/code"]


def test_status_reports_snapshots_and_a_total(tmp_path: Path) -> None:
    """Per-unit context sizes plus a running total — estimates labeled as
    estimates (no harness token API in V1)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert "phase/1/code" in result.output
    assert "journal 2 entries" in result.output
    assert "total" in result.output
    assert "est" in result.output


# --- V2 measured tokens: resolve records them, status never blurs them with
# --- an estimate (spec §5.C, phase 4) -------------------------------------

_USAGE = {
    "input_tokens": 1,
    "cache_creation_input_tokens": 1000,
    "cache_read_input_tokens": 20000,
    "output_tokens": 50,
}
"""Per ASSISTANT record; the captured subagent fixture has two of them, so a
correct reader doubles each figure."""


def _invoke_measurable(repo: Path, shipped: Path, argv: list[str], root: Path, session_id: str):
    """`_invoke` plus the two env keys a Claude Code tool call always carries.

    `FR_TRANSCRIPT_ROOT` points at a session tree the test built from the
    CAPTURED fixtures — never at `~/.claude/projects` (the suite's autouse
    fixture in `conftest.py` keeps it off the operator's machine by default).
    """
    env = {
        **os.environ,
        "VK_REPO_ROOT": str(repo),
        "FR_SHIPPED_WORKFLOWS_DIR": str(shipped),
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": session_id,
    }
    return runner_cli.invoke(app, argv, env=env)


def _transcript_stamp(at: str) -> str:
    """The cursor writes `+00:00` at second precision; a transcript writes the
    captured `...Z` form with milliseconds. Same instant, harness spelling."""
    return at.replace("+00:00", ".000Z")


def test_resolve_records_measured_tokens_for_the_unit_it_closes(tmp_path: Path) -> None:
    """End to end: advance dispatches (and stamps the window's start), the
    harness writes its transcript, resolve reads it back into the SAME
    accounting record the V1 sizes live in.

    The UNCLAIMED path, so the window is what selects — and since phase 4 the
    window is offered only for an attempt THIS session dispatched (§4.D.1),
    the `advance` has to declare the same session the `resolve` does. It used
    to be a bare `_invoke`, which passed only because the authoring machine
    was itself a Claude Code session whose id leaked through `os.environ`.
    """
    from tests.unit.transcript_sessions import dispatched_at

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-1")
    at = _accounting(load_run_state(repo, "r1"))["phase/1/code"].at
    assert at is not None
    dispatched_at(root, _transcript_stamp(at), session_id="sess-1", usage=_USAGE)

    result = _invoke_measurable(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
        root,
        "sess-1",
    )

    assert result.exit_code == 0, result.output
    snap = _accounting(load_run_state(repo, "r1"))["phase/1/code"]
    assert snap.input_tokens == 2
    assert snap.cache_creation_input_tokens == 2000
    assert snap.cache_read_input_tokens == 40000
    assert snap.output_tokens == 100
    assert snap.measured_tokens == 2 + 2000 + 40000 + 100
    # the V1 sizes are untouched — this is one record, not two
    assert snap.journal_entries == 2
    assert snap.handoff_chars > 0


def test_resolve_records_the_served_model_not_the_claimed_alias(tmp_path: Path) -> None:
    """2026-09-21 debug journal C3: the cursor recorded `model: opus` — the
    alias the orchestrator typed — while the executor's own transcript said
    `claude-opus-5` on every assistant record, and fr was already reading that
    transcript for `measured:`. A claim held beside the measurement that
    contradicts it. The captured fixture has the same split: its metadata says
    `sonnet` (the request), its assistant records `claude-sonnet-5` (the
    model that actually served it). The measurement wins."""
    from fr.run import units

    from tests.unit.transcript_sessions import dispatched_at

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-1")
    at = _accounting(load_run_state(repo, "r1"))["phase/1/code"].at
    assert at is not None
    dispatched_at(root, _transcript_stamp(at), session_id="sess-1", usage=_USAGE)

    result = _invoke_measurable(
        repo,
        shipped,
        [
            "run", "resolve", "r1", "--step", "code", "--item", "phase/1",
            "--state", "done", "--model", "sonnet",
        ],
        root,
        "sess-1",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/code")
    assert attempt is not None
    assert attempt.model == "claude-sonnet-5"


def _orchestrator_session(root: Path, session_id: str, model: str) -> None:
    """A captured orchestrator transcript whose last main-thread assistant
    record says `model` — what a session looks like after `/model <model>`."""
    from tests.unit.transcript_sessions import ORCHESTRATOR, copy_of, records, write_session

    rows = records(ORCHESTRATOR)
    last = copy_of(next(r for r in rows if r.get("type") == "assistant"))
    last["message"]["model"] = model
    write_session(root, session_id=session_id, rows=[*rows, last])


def test_advance_records_the_observed_model_of_an_orchestrator_run_step(tmp_path: Path) -> None:
    """2026-09-21 debug journal C3: every orchestrator-run unit of the first
    fr-goal run after #508 (spec-review, plan, review-phase, deliver) recorded
    no model, although the whole run went through on claude-sonnet-5. The
    transcript names the model; fr now records what it OBSERVES — never a tier
    resolution, which is what once wrote seven false reviews into the archive."""
    from fr.run import units

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    root = tmp_path / "projects"
    _orchestrator_session(root, "sess-o", "claude-sonnet-5")
    _invoke_measurable(
        repo,
        shipped,
        ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"],
        root,
        "sess-o",
    )
    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-o")

    assert result.exit_code == 0, result.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/plan")
    assert attempt is not None
    assert attempt.agent_type is None
    assert attempt.model == "claude-sonnet-5"


def test_advance_warns_when_the_orchestrator_is_not_on_its_bound_model(tmp_path: Path) -> None:
    """Record + warn, never block (operator decision, debug journal C3): an
    `orchestrator` key in models.yaml is the contract, the transcript is the
    observation, and a mismatch is said out loud on every `advance` — the
    run is not refused, because the operator's `/model` choice outranks it."""
    repo = _repo(tmp_path)
    (repo / "docs" / "superpowers").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "superpowers" / "models.yaml").write_text(
        "claude-code:\n  orchestrator: claude-opus-5\n"
    )
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    root = tmp_path / "projects"
    _orchestrator_session(root, "sess-o", "claude-sonnet-5")
    _invoke_measurable(
        repo,
        shipped,
        ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"],
        root,
        "sess-o",
    )
    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-o")

    assert result.exit_code == 0, result.output
    flat = " ".join(result.stderr.split())
    assert "orchestrator is running on claude-sonnet-5" in flat
    assert "orchestrator to claude-opus-5" in flat


def test_advance_is_silent_when_the_orchestrator_matches_its_binding(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs" / "superpowers").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "superpowers" / "models.yaml").write_text(
        "claude-code:\n  orchestrator: claude-opus-5\n"
    )
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    root = tmp_path / "projects"
    _orchestrator_session(root, "sess-o", "claude-opus-5")
    _invoke_measurable(
        repo,
        shipped,
        ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"],
        root,
        "sess-o",
    )
    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-o")

    assert result.exit_code == 0, result.output
    assert "orchestrator is running on" not in result.stderr


def test_resolve_records_nothing_when_no_transcript_can_be_read(tmp_path: Path) -> None:
    """Degradation is never a zero: an unmeasurable unit keeps `None` in all
    four fields, which is what `status` reports as an absence."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke_measurable(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
        tmp_path / "no-such-transcript-root",
        "sess-1",
    )

    assert result.exit_code == 0, result.output
    snap = _accounting(load_run_state(repo, "r1"))["phase/1/code"]
    assert snap.measured_tokens is None
    assert snap.input_tokens is None
    assert snap.handoff_chars > 0, "the V1 estimate survives the missing measurement"


# --- cost is per ATTEMPT: a redispatch never overwrites the abandoned spend
# --- (decision u2, spec §1.B / §4.D, phase 4) -----------------------------

_USAGE_FIRST = {
    "input_tokens": 3,
    "cache_creation_input_tokens": 30,
    "cache_read_input_tokens": 300,
    "output_tokens": 3000,
}
_USAGE_SECOND = {
    "input_tokens": 7,
    "cache_creation_input_tokens": 70,
    "cache_read_input_tokens": 700,
    "output_tokens": 7000,
}
FIRST_TOTAL = 2 * (3 + 30 + 300 + 3000)
SECOND_TOTAL = 2 * (7 + 70 + 700 + 7000)
"""The captured subagent fixture has TWO assistant records, so a correct
reader doubles each figure. The two dispatches are deliberately far apart in
size: a test where both attempts cost the same cannot tell a swap from a
match."""

_SAME_INSTANT = "2026-09-20T11:30:00.000Z"
"""Both subagent transcripts are written at the SAME instant on purpose. No
time window can separate two dispatches that overlap, and gh#514's
`select_dispatch` returns NOTHING for an ambiguous window — so every figure
these tests assert can only have come from selection by AGENT ID."""


def _redispatched_unit(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The u2 regression, run end to end: advance -> claim -> `--abandoned`
    -> advance -> claim -> resolve, with a real transcript for each attempt.

    Returns `(repo, shipped, transcript root)`. Every invocation declares its
    session (`CLAUDE_CODE_SESSION_ID`) rather than inheriting the authoring
    machine's: this phase is ABOUT session identity, so a test that reads it
    off the environment proves nothing on any other machine.
    """
    from tests.unit.transcript_sessions import add_dispatch, write_session

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")

    def call(argv: list[str]) -> None:
        result = _invoke_measurable(repo, shipped, argv, root, "sess-1")
        assert result.exit_code == 0, result.output

    unit = ["--step", "code", "--item", "phase/1"]
    call(["run", "advance", "r1"])
    call(["run", "claim", "r1", *unit, "--agent", "a1f1"])
    add_dispatch(
        session,
        timestamp=_SAME_INSTANT,
        agent_id="a1f1",
        tool_use_id="toolu_first",
        usage=_USAGE_FIRST,
    )
    call(["run", "claim", "r1", *unit, "--abandoned"])
    call(["run", "advance", "r1"])
    call(["run", "claim", "r1", *unit, "--agent", "b2e2"])
    add_dispatch(
        session,
        timestamp=_SAME_INSTANT,
        agent_id="b2e2",
        tool_use_id="toolu_second",
        usage=_USAGE_SECOND,
    )
    call(["run", "resolve", "r1", *unit, "--state", "done"])
    return repo, shipped, root


def test_each_attempt_of_a_redispatched_unit_carries_its_own_cost(tmp_path: Path) -> None:
    """Spec §1.B's live defect, pinned: the v4 shape APPENDED the attempt and
    OVERWROTE the unit's one cost snapshot, so fr kept an abandoned agent's
    identity and discarded its spend.

    Two attempts, two estimates, two measurements, neither borrowed."""
    repo, _shipped, _root = _redispatched_unit(tmp_path)

    first, second = _dispatch_of(repo, "implement", "phase/1/code")

    assert (first.outcome, second.outcome) == ("abandoned", "done")
    assert first.agent == "a1f1" and second.agent == "b2e2"
    assert first.estimate is not None, "the abandoned attempt keeps its own estimate"
    assert second.estimate is not None
    assert first.measured is not None and first.measured.total == FIRST_TOTAL
    assert second.measured is not None and second.measured.total == SECOND_TOTAL


def test_claim_abandoned_measures_the_attempt_it_closes(tmp_path: Path) -> None:
    """The spend most worth seeing is the spend that produced nothing (§4.D).

    Measured AT the abandon, not later: the assertion is made before the
    second `advance` exists, so nothing but `claim --abandoned` can have
    written it."""
    from tests.unit.transcript_sessions import add_dispatch, write_session

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    unit = ["--step", "code", "--item", "phase/1"]
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-1")
    _invoke_measurable(
        repo, shipped, ["run", "claim", "r1", *unit, "--agent", "a1f1"], root, "sess-1"
    )
    add_dispatch(
        session,
        timestamp=_SAME_INSTANT,
        agent_id="a1f1",
        tool_use_id="toolu_first",
        usage=_USAGE_FIRST,
    )

    result = _invoke_measurable(
        repo, shipped, ["run", "claim", "r1", *unit, "--abandoned"], root, "sess-1"
    )

    assert result.exit_code == 0, result.output
    (only,) = _dispatch_of(repo, "implement", "phase/1/code")
    assert only.outcome == "abandoned"
    assert only.measured is not None and only.measured.total == FIRST_TOTAL


def test_advance_records_the_session_that_dispatched_the_attempt(tmp_path: Path) -> None:
    """`session` is derived from fr's OWN environment when the attempt opens,
    the same way `harness` is (§4.D.1) — it is never reported by the agent."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke_measurable(
        repo, shipped, ["run", "advance", "r1"], tmp_path / "projects", "sess-7"
    )

    assert result.exit_code == 0, result.output
    (opened,) = _dispatch_of(repo, "implement", "phase/1/code")
    assert opened.session == "sess-7"
    assert opened.harness == "claude-code"


def test_an_attempt_opened_by_a_harness_with_no_session_records_none(tmp_path: Path) -> None:
    """No session concept, no session — never a guess, and never this
    process's own id borrowed for a harness that did not report one."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "advance", "r1"],
        {"FR_HARNESS": "opencode", "CLAUDE_CODE_SESSION_ID": None},
    )

    assert result.exit_code == 0, result.output
    (opened,) = _dispatch_of(repo, "implement", "phase/1/code")
    assert opened.session is None


_TWO_UNIT_RUN = """\
run: r9
workflow: grouped@1
branch: b
started: '2026-09-20T09:00:00+00:00'
cursor: implement
steps:
  implement:
    state: running
    items:
      phase/1/code: done
      phase/2/code: running
accounting:
  phase/1/code:
    at: '2026-09-20T09:00:01+00:00'
    journal_entries: 2
    journal_lines: 40
    handoff_chars: 900
    spec_bytes: 200
    plan_bytes: 300
    input_tokens: 1
    cache_creation_input_tokens: 1000
    cache_read_input_tokens: 20000
    output_tokens: 50
  phase/2/code:
    at: '2026-09-20T09:30:01+00:00'
    journal_entries: 3
    journal_lines: 60
    handoff_chars: 1300
    spec_bytes: 200
    plan_bytes: 300
"""


def _write_run(repo: Path, text: str, run_id: str = "r9") -> Path:
    """Write the v4-shaped cursor `text` — THROUGH the real 4 -> 5 rewrite.

    `_TWO_UNIT_RUN` is typed in the v4 shape on purpose and stays that way: it
    is a pre-dispatch-record cursor (cost, no attempts), which is what most
    real cursors are, and running it through `fr.run.legacy.v4_to_v5` means
    every `fr run status` assertion below is made about a MIGRATED cursor —
    synthesized attempts and all — rather than about a v5 file typed to look
    like one.
    """
    import yaml
    from fr.artifacts.registry import artifact_kind
    from fr.run.legacy import v4_to_v5

    data = v4_to_v5(yaml.safe_load(text))
    data = {"schema_version": artifact_kind("run").current_version, **data}
    path = repo / "docs" / "superpowers" / "runs" / f"{run_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _flat(result) -> str:
    """Rich soft-wraps to the terminal width, so a raw-output assertion can
    pass at one width and fail at another. Normalising whitespace is what
    makes these assertions about the TEXT rather than about the terminal."""
    return " ".join(result.output.split())


def test_status_never_renders_a_measurement_and_an_estimate_the_same_way(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_run(repo, _TWO_UNIT_RUN)

    flat = _flat(_invoke(repo, shipped, ["run", "status", "r9"]))

    # the measured unit: the four figures, named as measured
    assert (
        "measured: 21051 tok billed across the dispatch's turns "
        "(in 1, cache-create 1000, cache-read 20000, out 50)" in flat
    )
    # the estimated unit: still an estimate, and SAID to be one
    assert "not measured: no transcript figure for this unit" in flat
    assert "tok est" in flat
    # and each belongs to the right unit — ordering ties figure to key without
    # depending on where rich decided to wrap. Since phase 4 the figures sit
    # BENEATH their own attempt inside the steps block rather than in an
    # accounting section of their own, so the ordering is read over the whole
    # output; the keys still bracket their figures.
    assert (
        flat.index("phase/1/code")
        < flat.index("measured: 21051 tok")
        < flat.index("phase/2/code")
        < flat.index("not measured:")
    )
    assert "measured total: 21051 tok over 1 of 2 dispatched attempts" in flat


def test_status_says_out_loud_when_nothing_could_be_measured(tmp_path: Path) -> None:
    """The failure this wording exists to prevent: estimates rendered as if
    they were measurements, with nothing on screen saying which they are."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    unmeasured = "\n".join(line for line in _TWO_UNIT_RUN.splitlines() if "_tokens:" not in line)
    _write_run(repo, unmeasured + "\n")

    flat = _flat(_invoke(repo, shipped, ["run", "status", "r9"]))

    assert "measured total: none" in flat
    assert "no transcript figure for any of the 2 dispatched attempts" in flat
    assert "tok est" in flat
    assert "measured: 21051" not in flat


def test_status_renders_a_measured_zero_as_a_measurement(tmp_path: Path) -> None:
    """A unit that genuinely spent nothing is measured. Rendering it as "not
    measured" would be the same lie in the other direction."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    zeroed = _TWO_UNIT_RUN
    for key, value in (
        ("input_tokens: 1", "input_tokens: 0"),
        ("cache_creation_input_tokens: 1000", "cache_creation_input_tokens: 0"),
        ("cache_read_input_tokens: 20000", "cache_read_input_tokens: 0"),
        ("output_tokens: 50", "output_tokens: 0"),
    ):
        zeroed = zeroed.replace(key, value)
    _write_run(repo, zeroed)

    flat = _flat(_invoke(repo, shipped, ["run", "status", "r9"]))

    assert (
        "measured: 0 tok billed across the dispatch's turns "
        "(in 0, cache-create 0, cache-read 0, out 0)" in flat
    )
    assert "measured total: 0 tok over 1 of 2 dispatched attempts" in flat


def test_status_says_a_measured_figure_came_from_a_transcript(tmp_path: Path) -> None:
    """A number with no provenance is the thing this phase exists to avoid.

    Named for what it checks. It was previously called
    `test_status_names_the_harness_whose_transcript_it_read`, which the body
    could not deliver: `_with_measurement` keeps only the four figures, so the
    cursor has no record of WHICH harness produced them and the rendering
    cannot name one. A test whose name asserts more than its body is the exact
    defect this repo keeps finding; renaming is the honest fix, and carrying
    provenance into the cursor is the follow-up (v1 stores figures; which agent
    produced them stays recoverable from the transcript).
    """
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_run(repo, _TWO_UNIT_RUN)

    flat = _flat(_invoke(repo, shipped, ["run", "status", "r9"]))

    assert "cumulative harness accounting" in flat


def test_status_says_the_measured_figure_is_not_the_estimate(tmp_path: Path) -> None:
    """The two numbers are labeled differently AND are different quantities.

    The estimate is one dispatch's assembled context; the measurement is
    cumulative billing across every turn of that dispatch, dominated by
    cache re-reads. On a real unit of the run that built this they differed by
    ~1,426x, which reads as a broken estimator unless the line says what it
    counts.
    """
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_run(repo, _TWO_UNIT_RUN)

    flat = _flat(_invoke(repo, shipped, ["run", "status", "r9"]))

    assert "billed across the dispatch's turns" in flat
    assert "NOT comparable to the one-dispatch" in flat


# --- status says what fr can and cannot see (spec §4.D / §4.D.1, phase 4) --


def test_status_renders_each_attempts_cost_beneath_its_own_holder(tmp_path: Path) -> None:
    """EVERY attempt, not just the last. The v4 shape rendered one cost line
    per unit, so a redispatched unit showed the retry's figures and the
    abandoned agent's spend was nowhere on screen.

    Ordering is the assertion that ties a figure to a holder without
    depending on where rich decided to wrap."""
    repo, shipped, root = _redispatched_unit(tmp_path)

    flat = _flat(_invoke_measurable(repo, shipped, ["run", "status", "r1"], root, "sess-1"))

    assert (
        flat.index("agent a1f1")
        < flat.index(f"measured: {FIRST_TOTAL} tok")
        < flat.index("agent b2e2")
        < flat.index(f"measured: {SECOND_TOTAL} tok")
    ), flat
    # the two quantities stay labelled as different quantities (gh#514)
    assert flat.count("NOT comparable to the one-dispatch") == 2
    assert "tok est" in flat


def test_status_totals_include_the_abandoned_attempts_spend(tmp_path: Path) -> None:
    """Totals sum ATTEMPTS. A denominator of units would report better
    coverage than there is the moment one unit is redispatched."""
    repo, shipped, root = _redispatched_unit(tmp_path)

    flat = _flat(_invoke_measurable(repo, shipped, ["run", "status", "r1"], root, "sess-1"))

    # 3 dispatched attempts, not 2: the flat `plan` step opened one of its
    # own, and a denominator that quietly omitted it would report better
    # coverage than there is.
    assert (
        f"measured total: {FIRST_TOTAL + SECOND_TOTAL} tok over 2 of 3 dispatched attempts" in flat
    )


def test_status_says_a_cost_from_another_session_is_not_observable_from_here(
    tmp_path: Path,
) -> None:
    """§4.D.1: the cursor travelled with the branch; the transcripts did not.

    An absent figure that could still arrive ("not measured") and one this
    session can never produce ("not observable from here") are different
    facts, and an operator deciding whether to wait needs the difference."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-a")

    elsewhere = _flat(_invoke_measurable(repo, shipped, ["run", "status", "r1"], root, "sess-b"))
    here = _flat(_invoke_measurable(repo, shipped, ["run", "status", "r1"], root, "sess-a"))

    assert "not observable from here" in elsewhere
    assert "not observable from here" not in here, (
        "the SAME attempt read from the session that dispatched it is merely unmeasured"
    )
    assert "not measured: no transcript figure" in here


def test_advance_refusing_another_sessions_holder_says_it_cannot_see_it(tmp_path: Path) -> None:
    """The second host's first move (§4.D.1). Without this sentence the
    operator waits on an agent that died with its host — the refusal names a
    holder, and every other refusal fr prints means "someone is working"."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    root = tmp_path / "projects"
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-a")

    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-b")

    assert result.exit_code == 2, result.output
    flat = _flat(result)
    assert "ANOTHER session" in flat
    assert "not observable from here" in flat
    assert "fr run claim r1 --step code --item phase/1 --abandoned" in flat


def test_advance_refusing_its_own_sessions_holder_says_nothing_about_sessions(
    tmp_path: Path,
) -> None:
    """The ordinary case must not acquire the scary sentence: this session's
    own agent is alive as far as anything here knows."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    root = tmp_path / "projects"
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-a")

    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-a")

    assert result.exit_code == 2, result.output
    flat = _flat(result)
    assert "is ALREADY HELD by" in flat
    assert "ANOTHER session" not in flat


# --- write-claim: one writer at a time (phase 5, contract runtime) ---


def test_advance_marks_the_dispatched_unit_running(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    state = load_run_state(repo, "r1")
    assert units.unit_states(state.steps["implement"]) == {"phase/1/code": "running"}


def test_resolve_while_another_unit_is_running_is_refused(tmp_path: Path) -> None:
    """A finished executor that keeps writing, or an orchestrator writing
    alongside it, shows up here as two outstanding units — the second resolve
    is refused naming the first, instead of interleaving silently."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code, marks running

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1", "--state", "done"],
    )

    assert result.exit_code == 2, result.output
    assert "phase/1/code" in result.output
    state = load_run_state(repo, "r1")
    assert state.steps["implement"].state == "running"
    assert state.cursor == "implement"


def test_serial_resolves_still_flow(tmp_path: Path) -> None:
    """The refusal above must not break the ordinary serial discipline:
    resolve the running unit first, then the next dispatches."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code
    assert (
        _invoke(
            repo,
            shipped,
            ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
        ).exit_code
        == 0
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches peer-review

    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["step"] == "peer-review"


# ---------------------------------------------------------------------------
# Phase 4 — gate provenance (spec `2026-09-18-harness-parity-matrix-design`
# §3.D.2/§3.D.3). `StepRecord.answered_by` records WHO cleared an operator
# gate, and `fr run check` reports an agent-cleared one without changing its
# exit code.
# ---------------------------------------------------------------------------


def _clear_cli_gate(repo: Path, shipped: Path, *extra: str):
    """Start the `gated` shape, block on its gate, and clear it."""
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    return _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done", *extra],
    )


def test_clearing_a_gate_without_answered_by_records_the_agent(tmp_path: Path) -> None:
    """The DEFAULT is the conservative claim (spec §3.D.2): an unmodified
    caller records `agent`, so nothing is silently upgraded to "a human
    answered"."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped)

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.gate == "cleared"
    assert record.answered_by == "agent"


def test_clearing_a_gate_with_answered_by_operator_records_the_operator(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped, "--answered-by", "operator")

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].answered_by == "operator"


def test_provenance_survives_the_advance_that_follows_a_cleared_cli_gate(tmp_path: Path) -> None:
    """A cleared `cli` gate returns the step to `pending`, so the NEXT
    `advance` rebuilds its record through `_complete_step`. Provenance has to
    be carried forward there exactly like `gate`, or the one surface that
    reports it (`fr run check`) goes quiet the moment the step runs."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped)

    _invoke(repo, shipped, ["run", "advance", "r1"])

    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "done"
    assert record.answered_by == "agent"


def test_a_gated_agent_step_records_provenance_too(tmp_path: Path) -> None:
    """The measured failure (spec §1) was a `kind: agent` + `gate: operator`
    step self-resolving to `done` on a harness with no question tool. If
    provenance only covered the `cli` branch it would miss exactly that."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    (repo / "s.md").write_text("# spec\n")
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

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
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "done"
    assert record.answered_by == "agent"


def test_a_gated_agent_step_can_record_an_operator(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    (repo / "s.md").write_text("# spec\n")
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

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
            "--answered-by",
            "operator",
        ],
    )

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].answered_by == "operator"


# --- debug journal C1: on Claude Code the gate is VERIFIED, not trusted -----


def _gated_agent_blocked(tmp_path: Path, root: Path, session: str) -> tuple[Path, Path, str]:
    """A `gated-agent` run blocked on its brainstorm gate, driven as a Claude
    Code session whose transcript lives under `root`. Returns the block time."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "superpowers" / "specs" / "2026-09-21-x-design.md").write_text("# spec\n")
    argv = ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"]
    _invoke_measurable(repo, shipped, argv, root, session)
    _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, session)
    blocked_at = load_run_state(repo, "r1").steps["brainstorm"].at
    assert blocked_at is not None
    return repo, shipped, blocked_at


_RESOLVE_BRAINSTORM = [
    "run", "resolve", "r1", "--step", "brainstorm", "--state", "done",
    "--emitted", "spec=docs/superpowers/specs/2026-09-21-x-design.md",
]  # fmt: skip


def test_a_gate_cleared_with_no_question_in_the_transcript_is_refused(tmp_path: Path) -> None:
    """The first fr-goal run after #508, exactly: Claude Code, a readable
    transcript, no question asked, `resolve --state done` — which succeeded and
    recorded `answered_by: agent` while `parity.yaml` called the gate
    `enforced`. Observed-unasked is now a refusal naming both ways forward."""
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")

    result = _invoke_measurable(repo, shipped, _RESOLVE_BRAINSTORM, root, "s-g")

    assert result.exit_code == 2, result.output
    flat = " ".join(result.stderr.split())
    assert "no answered question" in flat
    assert "--no-questions" in flat
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_a_gate_whose_question_was_answered_records_the_operator(tmp_path: Path) -> None:
    """Provenance is DERIVED, not claimed: no `--answered-by` passed, and the
    record still says `operator`, because the transcript shows the answer."""
    from fr.run.telemetry import parse_timestamp

    from tests.unit.transcript_sessions import asked_at

    root = tmp_path / "projects"
    repo, shipped, blocked_at = _gated_agent_blocked(tmp_path, root, "s-g")
    after = parse_timestamp(blocked_at)
    assert after is not None
    asked_at(root, after.strftime("%Y-%m-%dT%H:%M:%S.999Z"), session_id="s-g")

    result = _invoke_measurable(repo, shipped, _RESOLVE_BRAINSTORM, root, "s-g")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "done"
    assert record.answered_by == "operator"


def test_an_operator_claim_the_transcript_contradicts_is_refused(tmp_path: Path) -> None:
    """`--answered-by operator` used to be an unverified claim. Against a
    transcript that shows no answer it is refused, not recorded."""
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")

    result = _invoke_measurable(
        repo, shipped, [*_RESOLVE_BRAINSTORM, "--answered-by", "operator"], root, "s-g"
    )

    assert result.exit_code == 2, result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_no_questions_needs_a_reason_and_records_it_on_the_spec_journal(tmp_path: Path) -> None:
    """The explicit, visible bypass: `--no-questions --reason …` clears the gate
    as `agent`, and the reason lands on the spec journal the same resolve
    emits — where the PR body's decisions section reads it."""
    from fr.journal.model import journal_path, parse_journal

    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")

    bare = _invoke_measurable(repo, shipped, [*_RESOLVE_BRAINSTORM, "--no-questions"], root, "s-g")
    assert bare.exit_code == 2, bare.output
    assert "--reason" in " ".join(bare.stderr.split())

    result = _invoke_measurable(
        repo,
        shipped,
        [*_RESOLVE_BRAINSTORM, "--no-questions", "--reason", "every decision was in the ask"],
        root,
        "s-g",
    )

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "done"
    assert record.answered_by == "agent"
    entries = parse_journal(journal_path(repo, "spec", "2026-09-21-x").read_text())
    assert [(e.kind, e.id) for e in entries] == [("decision", "gate-no-questions-brainstorm")]
    assert "every decision was in the ask" in entries[0].body


def test_an_unobservable_gate_degrades_loudly_instead_of_refusing(tmp_path: Path) -> None:
    """No readable transcript (a session id fr cannot find): fr cannot verify,
    so it keeps the pre-C1 behaviour — and SAYS it could not verify, rather than
    passing silently the way it did on the #497 run."""
    root = tmp_path / "projects"
    root.mkdir()
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-missing")

    result = _invoke_measurable(repo, shipped, _RESOLVE_BRAINSTORM, root, "s-missing")

    assert result.exit_code == 0, result.output
    assert "could not verify" in " ".join(result.stderr.split())
    assert load_run_state(repo, "r1").steps["brainstorm"].answered_by == "agent"


def test_no_questions_with_nowhere_to_record_the_reason_is_refused(tmp_path: Path) -> None:
    """Review r1-5: without a spec to journal it on, the reason would only reach
    stderr — "on the record" in name only. Refused, and the gate stays shut."""
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")
    argv = ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done"]

    result = _invoke_measurable(
        repo, shipped, [*argv, "--no-questions", "--reason", "why"], root, "s-g"
    )

    assert result.exit_code == 2, result.output
    assert "nowhere to record its reason" in " ".join(result.stderr.split())
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_the_no_questions_decision_is_logged_once(tmp_path: Path) -> None:
    """Review r1-6: the entry id is stable, so a retry cannot log it twice."""
    from fr.journal.model import journal_path, parse_journal

    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")
    journal = journal_path(repo, "spec", "2026-09-21-x")
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "# Journal: 2026-09-21-x\n\n"
        "<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm "
        "created=2026-09-21T00:00:00 -->\n"
        "### gate-no-questions-brainstorm · decision · an earlier attempt\n\nfirst\n"
    )

    result = _invoke_measurable(
        repo, shipped, [*_RESOLVE_BRAINSTORM, "--no-questions", "--reason", "again"], root, "s-g"
    )

    assert result.exit_code == 0, result.output
    ids = [e.id for e in parse_journal(journal.read_text())]
    assert ids == ["gate-no-questions-brainstorm"]


def test_gate_flags_on_a_resolve_that_clears_no_gate_are_refused(tmp_path: Path) -> None:
    """Review r1-7: silently ignored flags read as honoured ones."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "plan", "--state", "done", "--no-questions",
         "--reason", "x"],
    )  # fmt: skip

    assert result.exit_code == 2, result.output
    assert "clears none" in " ".join(result.output.split())


def test_a_resolve_that_clears_no_gate_records_no_provenance(tmp_path: Path) -> None:
    """`answered_by` is a property of a GATE, not of a resolve — the same
    shape as `gate: cleared` itself. An ungated agent step records `None`
    even when `--answered-by` is passed, so the field never claims an
    authorization that was never asked for."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "plan", "--state", "done", "--answered-by", "operator"],
    )

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["plan"].answered_by is None


def test_a_declined_gate_records_no_provenance(tmp_path: Path) -> None:
    """A declined gate was not cleared, and `answered_by` is set only when a
    gate is cleared."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated", _GATE_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo, shipped, ["run", "resolve", "r1", "--step", "brainstorm", "--state", "failed"]
    )

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "failed"
    assert record.answered_by is None


def test_an_unknown_answered_by_is_refused(tmp_path: Path) -> None:
    """A typo must not be recorded as a third provenance nobody reads."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped, "--answered-by", "the-cat")

    assert result.exit_code == 2, result.output
    assert "answered-by" in result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].gate != "cleared"


def test_a_new_run_is_born_stamped_with_the_current_run_version(tmp_path: Path) -> None:
    """Moving the `run` kind's `current_version` makes every run file fr
    itself writes stale unless `start` stamps the new one — and a run that is
    stale from birth makes the first non-interactive `fr` command refuse."""
    import yaml as _yaml
    from fr.artifacts.registry import artifact_kind

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])

    path = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    written = _yaml.safe_load(path.read_text())
    assert written["schema_version"] == artifact_kind("run").current_version
    assert artifact_kind("run").read_version(path) == artifact_kind("run").current_version


# --- §3.D.3: `fr run check` reports, and its exit code is unchanged ---------


def test_check_reports_an_agent_cleared_gate_and_still_exits_zero(tmp_path: Path) -> None:
    """The exit code IS the contract here. Making an agent-cleared gate
    non-zero would turn every legitimate non-interactive dispatch red — the
    hard-refusal option the operator rejected (spec §3.D.3)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped)

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "brainstorm" in result.output
    assert "answered_by: agent" in result.output


def test_check_says_nothing_about_a_gate_the_operator_answered(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "operator")

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "answered_by" not in result.output


def test_check_still_exits_nonzero_on_a_failed_step_that_had_an_agent_cleared_gate(
    tmp_path: Path,
) -> None:
    """The existing freshness contract is untouched: the report is additive,
    not a replacement for the one thing `check` already failed on."""
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

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 1, result.output
    assert "answered_by: agent" in result.output


# --- `fr run gates` (Phase 5, review r4-i2): the PR-body "Operator gates" ---
# --- section source. Never blank — always says something, even "none". ----


def test_gates_reports_none_when_the_workflow_declares_no_operator_gates(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    assert result.exit_code == 0, result.output
    assert "no `gate: operator` steps" in result.output


def test_gates_reports_who_cleared_an_operator_answered_gate(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "operator")

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    assert result.exit_code == 0, result.output
    # r5-m3: `gates` feeds the PR BODY, so it now says what `check` says
    # rather than a terser bookkeeping line.
    assert "brainstorm: operator gate answered by the operator" in result.output


def test_gates_reports_an_agent_cleared_gate_with_the_same_wording_as_check(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped)

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    assert result.exit_code == 0, result.output
    # r5-m3: this test's NAME already claimed parity with `check`; until the
    # fix it asserted a terser line that differed. Now it is true.
    assert "operator gate cleared by the agent (answered_by: agent)" in result.output
    assert "no operator answered it" in result.output


def test_gates_never_renders_blank_on_a_pre_provenance_cursor(tmp_path: Path) -> None:
    """The r4-i2 shape: a cursor written before `answered_by` existed. A
    blank "Operator gates" section on a PR body reads as "the feature never
    ran" — so this must name the gap explicitly, not fall silent."""
    import yaml as _yaml

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped)
    path = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    raw = _yaml.safe_load(path.read_text())
    del raw["steps"]["brainstorm"]["answered_by"]  # simulate a pre-field cursor
    path.write_text(_yaml.safe_dump(raw, sort_keys=False))

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    assert result.exit_code == 0, result.output
    assert "brainstorm" in result.output
    assert "provenance not recorded" in result.output
    assert "predates" in result.output


# --- dispatch record: opened exactly when `advance` moves a unit to
# `running` — spec §4.B.1 (Phase 2) ---

_FLAT_AGENT_COLLISION_SHAPE = """
workflow: flat-agent-collision
schema: 1
unit: run
steps:
  - id: phase/1/implement-phase
    kind: agent
    agent: super-fr:fr-phase-executor
    tier: standard
"""
"""Spec review finding r1: nothing in `check_workflow` stops a step id that
LOOKS like a grouped member's `items` key. A flat step literally named
`phase/1/implement-phase` is the adversarial case the `step/` prefix exists
for — without it this step's dispatch key would collide with a grouped
member's."""


def _write_repo_models(repo: Path, text: str) -> None:
    path = repo / "docs" / "superpowers" / "models.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_advance_grouped_member_opens_a_dispatch_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case (a): a grouped member's record is keyed like its `items` entry,
    `agent_type` is the member's own `agent:`, and `model` is the resolved
    tier binding.

    The tier is bound under a REAL tier name (`fr.types.PhaseHeader.tier`'s
    closed vocabulary), reached through the shape's `from_phase` sentinel and
    the plan phase header — not under a models.yaml key literally called
    `from_phase`, which no operator would ever write and which made this
    assertion pass while real dispatches recorded `model: null` (finding f4).
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    # DECLARED, not ambient: a tier resolves to a model only for a harness, and
    # this process is itself a Claude Code session, so without this the
    # assertion below would be about the machine rather than about fr (f11).
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="hard")
    _write_repo_models(repo, "claude-code:\n  hard: claude-opus-5\n")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])
    assert dispatch is not None
    assert list(dispatch) == ["phase/1/code"]
    records = dispatch["phase/1/code"]
    assert len(records) == 1
    record = records[0]
    assert record.dispatched
    assert record.agent_type == "super-fr:fr-phase-executor"
    assert record.model == "claude-opus-5"
    assert record.returned is None
    assert record.outcome is None


def test_advance_records_the_harness_it_detected_to_resolve_the_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record must name the harness its `model` binding came from.

    `_resolved_model` already calls `detect_harness` — a tier resolves to a
    model only *for a harness* — and then discarded it, so a record could
    carry `model: claude-opus-5` with `harness: null` while fr knew perfectly
    well which harness picked that model at that moment (finding f8). An
    orchestrator-run step is never claimed, so nothing would ever fill it in
    afterwards either.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="hard")
    _write_repo_models(repo, "claude-code:\n  hard: claude-opus-5\n")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    record = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"][0]
    assert record.model == "claude-opus-5"
    assert record.harness == "claude-code", "the model's own harness must be recorded with it"


def test_advance_records_no_harness_when_detection_is_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is guessed — an undetectable harness stays absent, the same
    rule an unbound tier follows (spec §4.A)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    for key in ("FR_HARNESS", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("fr.commands.run_cmd.detect_harness", lambda _env: None)
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="hard")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    record = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"][0]
    assert record.harness is None
    assert record.model is None


def test_advance_resolves_the_from_phase_sentinel_against_the_plan_phase_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`tier: from_phase` is a SENTINEL, not a tier (finding f4).

    Both `implement` and `implement-phase` carry it in the shipped `fr-goal`
    shape, and `fr.types.PhaseHeader.tier`'s vocabulary is
    mechanical/standard/hard — so handing `from_phase` to `fr models resolve`
    can only ever miss, and every real fr-goal dispatch recorded
    `model: null`. That is the field dead exactly where #503's cost-attribution
    motivation needs it. The record resolves the sentinel against the plan's
    own phase header; the BRIEF deliberately does not (see the test below),
    because there the sentinel is an instruction to the harness.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "claude-code")  # declared, not ambient (f11)
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="standard")
    _write_repo_models(repo, "claude-code:\n  standard: claude-sonnet-5\n  hard: claude-opus-5\n")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    records = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"]
    assert records[0].model == "claude-sonnet-5"
    # The brief still carries the sentinel verbatim — it tells the harness to
    # look the phase up, which is a different job from recording what was sent.
    assert '"tier": "from_phase"' in result.output


def test_advance_records_no_model_when_the_phase_header_has_no_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unresolvable sentinel leaves `model` absent rather than guessed —
    the same rule as an unbound tier (spec §4.A)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, strip_tier=True)
    _write_repo_models(repo, "claude-code:\n  standard: claude-sonnet-5\n")

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    records = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"]
    assert records[0].model is None


def test_advance_grouped_member_does_not_reopen_a_dispatch_record_while_still_running(
    tmp_path: Path,
) -> None:
    """Since phase 4 the second `advance` never gets as far as the dispatch
    map: it is REFUSED (gh-499). The assertion below is unchanged and still
    the one that matters — no second record for a unit already held —
    but the exit code is now asserted too, so this test cannot pass merely
    because `advance` silently did nothing."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    second = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert second.exit_code == 2, second.output
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])
    assert dispatch is not None
    assert len(dispatch["phase/1/code"]) == 1


def test_advance_flat_agent_step_opens_a_dispatch_record_under_the_step_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case (b) / review r1: the flat key carries the literal `step/`
    prefix, asserted against a step id that itself reads like a grouped
    member's key — `phase/1/implement-phase` — so the two key spaces are
    provably disjoint rather than merely disjoint by convention."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "claude-code")  # declared, not ambient (f11)
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _write_repo_models(repo, "claude-code:\n  standard: claude-sonnet-5\n")
    _invoke(
        repo,
        shipped,
        ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps["phase/1/implement-phase"])
    assert dispatch is not None
    assert list(dispatch) == ["step/phase/1/implement-phase"]
    record = dispatch["step/phase/1/implement-phase"][0]
    assert record.agent_type == "super-fr:fr-phase-executor"
    assert record.model == "claude-sonnet-5"
    assert record.returned is None


def test_advance_does_not_reopen_a_dispatch_record_while_still_running(
    tmp_path: Path,
) -> None:
    """The flat-step twin of the test above, refused the same way."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    second = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert second.exit_code == 2, second.output
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps["brainstorm"])
    assert dispatch is not None
    assert len(dispatch["step/brainstorm"]) == 1


def test_advance_onto_a_gated_agent_step_opens_no_dispatch_record(tmp_path: Path) -> None:
    """Case (c): a gate marks the step `blocked`, never `running` — nothing
    was dispatched, so nothing is held (spec §4.B.1)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["brainstorm"].state == "blocked"
    assert _attempts_by_unit(state.steps["brainstorm"]) is None


def test_advance_orchestrator_run_agent_step_opens_a_dispatch_record_with_no_agent_type(
    tmp_path: Path,
) -> None:
    """Case (d): a `spec-review`-shaped step (`kind: agent`, no `agent:`)
    still opens a record — the orchestrator is doing the work itself, and
    #499's complaint is precisely that this state goes unrecorded otherwise."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps["brainstorm"])
    assert dispatch is not None
    record = dispatch["step/brainstorm"][0]
    assert record.dispatched
    assert record.agent_type is None
    assert record.model is None  # `brainstorm` here carries no `tier:`
    assert record.returned is None
    assert record.outcome is None


# --- `fr run claim` — the reported identity, idempotent, single-writer, and
# abandonable (spec §4.C, Phase 3) ---


def _dispatch_of(repo: Path, step_id: str, key: str) -> list:
    dispatch = _attempts_by_unit(load_run_state(repo, "r1").steps[step_id])
    assert dispatch is not None
    return dispatch[key]


def test_claim_fills_agent_harness_model_on_the_open_record(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])  # opens the dispatch record

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "add889a73824c8413",
            "--harness",
            "claude-code",
            "--model",
            "claude-opus-5",
        ],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")[0]
    assert record.agent == "add889a73824c8413"
    assert record.harness == "claude-code"
    assert record.model == "claude-opus-5"
    assert record.returned is None
    assert record.outcome is None


def test_claim_refuses_a_unit_with_no_open_record(tmp_path: Path) -> None:
    """A claim annotates a dispatch `fr run advance` already made; it does
    not invent one — no `advance` was ever run here."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )

    result = _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a1"],
    )

    assert result.exit_code == 2, result.output
    assert "no open dispatch" in result.output


def test_claim_is_idempotent_for_the_same_agent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    claim_argv = [
        "run",
        "claim",
        "r1",
        "--step",
        "phase/1/implement-phase",
        "--agent",
        "a1",
        "--harness",
        "claude-code",
    ]

    first = _invoke(repo, shipped, claim_argv)
    second = _invoke(repo, shipped, claim_argv)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    records = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")
    assert len(records) == 1
    assert records[0].agent == "a1"


def test_claim_refuses_a_different_agent_while_the_first_is_open(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a1"],
    )

    result = _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a2"],
    )

    assert result.exit_code == 2, result.output
    assert "a1" in result.output
    assert "a2" in result.output


def test_claim_omitted_harness_uses_detect_harness(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a1"],
        {"CLAUDECODE": "1"},
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")[0]
    assert record.harness == "claude-code"


def test_claim_records_no_harness_when_detection_returns_none(tmp_path: Path) -> None:
    """No invented `"unknown"` member (review finding r4) — an undetectable
    harness leaves the field absent, exactly like an unbound tier leaves
    `model` absent.

    `advance` runs undetectable too, not just `claim`: since finding f8 the
    record is BORN with the harness `advance` detected, so leaving `advance`
    on the ambient environment would have this test assert against a field
    `claim` never touched."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {})

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a1"],
        {},
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")[0]
    assert record.harness is None


def test_claim_refuses_an_unknown_harness_value(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "a1",
            "--harness",
            "carrier-pigeon",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "carrier-pigeon" in result.output


def test_claim_resolves_a_grouped_members_unit_key(tmp_path: Path) -> None:
    """The shared `_unit_key` path — `--step code --item phase/1` names the
    same key `advance` opened under `implement`'s `dispatch`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--agent",
            "a1",
        ],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.agent == "a1"


def test_claim_agent_required_without_abandoned(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "claim", "r1", "--step", "phase/1/implement-phase"])

    assert result.exit_code == 2, result.output
    assert "--agent" in result.output


# --- `--abandoned`: closing a dispatch without resolving the step (spec
# §4.C, §1.C, Phase 3 Task 2) ---


def test_claim_abandoned_sets_returned_and_outcome(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--abandoned"],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")[0]
    assert record.returned is not None
    assert record.outcome == "abandoned"


def test_claim_abandoned_leaves_the_flat_steps_state_running(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--abandoned"],
    )

    state = load_run_state(repo, "r1")
    assert state.steps["phase/1/implement-phase"].state == "running"


def test_claim_abandoned_leaves_the_grouped_members_item_running(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--abandoned"],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert units.unit_states(state.steps["implement"]) == {"phase/1/code": "running"}
    assert state.steps["implement"].state == "running"


def test_advance_after_abandon_briefs_again_and_appends_a_second_record(
    tmp_path: Path,
) -> None:
    """The next `advance` sees the unit as still pending (`items`/`state`
    untouched by `--abandoned`) and re-briefs it, appending a SECOND
    `DispatchRecord` — the first stays in the list, closed."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--abandoned"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "dispatch brief" in result.output
    records = _dispatch_of(repo, "implement", "phase/1/code")
    assert len(records) == 2
    assert records[0].outcome == "abandoned"
    assert records[0].returned is not None
    assert records[1].returned is None
    assert records[1].outcome is None


def test_advance_after_abandon_briefs_a_flat_step_again_too(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--abandoned"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    records = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")
    assert len(records) == 2
    assert records[0].outcome == "abandoned"
    assert records[1].returned is None


def test_claim_abandoned_refuses_when_no_open_record(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )

    result = _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--abandoned"],
    )

    assert result.exit_code == 2, result.output
    assert "no open dispatch" in result.output


def test_claim_abandoned_refuses_combined_with_agent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "a1",
            "--abandoned",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "--abandoned" in result.output


# ---------------------------------------------------------------------------
# Phase 4 — `advance` refuses a HELD unit (gh-499), `--redispatch` is the
# deliberate escape, and `resolve` closes the dispatch record (spec §4.C).
#
# gh-499's complaint is precisely that a brief looks like an instruction to
# act when the correct action is to wait, and that the usual
# two-agents-one-tree protection is unavailable here BY DESIGN: fr-goal
# dispatches phase executors into the isolation worktree that already exists,
# and `isolation: "worktree"` is forbidden for them (gh-420). So a refusal
# that fires when it should not wedges a live run, and one that stays silent
# reproduces the double-dispatch. Both directions are tested.
# ---------------------------------------------------------------------------


def _squash(output: str) -> str:
    """rich soft-wraps a refusal at the terminal's width, so a substring
    assertion over raw `result.output` is an assertion about `COLUMNS`. Same
    idiom `test_run_workspace.py` and `test_v2_pickup.py` already use."""
    return " ".join(output.split())


def test_advance_refuses_a_held_unit_and_prints_no_brief(tmp_path: Path) -> None:
    """Case (a): exit 2 and NOT ONE character of the JSON brief.

    The absence is the assertion — printing the brief alongside a refusal
    would leave the harness exactly the instruction-to-act gh-499 says must
    not be there."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    first = _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code
    assert first.exit_code == 0, first.output

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "ALREADY HELD" in _squash(result.output)
    assert "{" not in result.output  # no brief, of any shape
    assert "dispatch brief" not in result.output


def test_the_refusal_names_the_holder_agent_type_harness_and_dispatch_time(
    tmp_path: Path,
) -> None:
    """Case (b): who is holding it, what kind of agent, on which harness, and
    since when — the four facts an operator needs to decide whether to wait."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--agent",
            "add889a73824c8413",
            "--harness",
            "claude-code",
        ],
    )
    dispatched = _dispatch_of(repo, "implement", "phase/1/code")[0].dispatched

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    assert "add889a73824c8413" in flat
    assert "super-fr:fr-phase-executor" in flat
    assert "claude-code" in flat
    assert dispatched in flat
    assert "not yet returned" in flat


def test_the_refusal_says_an_unclaimed_agent_when_nobody_claimed(tmp_path: Path) -> None:
    """Case (c): fr knows a brief went out even when nobody said who took it,
    so the refusal still fires — an unclaimed hold is still a hold."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "an unclaimed agent" in _squash(result.output)


def test_the_refusal_prints_all_three_ways_forward(tmp_path: Path) -> None:
    """Case (d): spec §4.C's three escapes, each a copy-pastable command
    carrying this unit's own `--step`/`--item`. A refusal an operator cannot
    act on is a wedge."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    # `--state done`, not `done|failed`: the line is meant to be pasted, and `|`
    # is a pipe in every POSIX shell (gh#519 r1-f1 — this test pinned the defect).
    assert "fr run resolve r1 --step code --item phase/1 --state done" in flat
    assert "done|failed" not in flat
    assert "fr run claim r1 --step code --item phase/1 --abandoned" in flat
    assert "fr run advance r1 --redispatch" in flat


def test_advance_does_not_refuse_when_the_last_record_is_closed(tmp_path: Path) -> None:
    """Case (e): the refusal keys off `_dispatch_needs_open` — the ONE notion
    of "currently held" phase 3 already wrote — so a unit whose last attempt
    is CLOSED is not held and briefs normally. Here the close is
    `claim --abandoned`; the failed-and-retried route is covered once
    `resolve` closes records too
    (`test_advance_re_briefs_a_failed_unit_whose_record_resolve_closed`)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--abandoned"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "ALREADY HELD" not in result.output
    assert _brief_of(result.output)["item"] == "phase/1"


def test_a_flat_agent_step_is_refused_the_same_way(tmp_path: Path) -> None:
    """The flat and grouped paths share ONE message function, so they cannot
    drift: the same four facts and the same three escapes, with `--item`
    absent because a flat unit has none."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    # Named by its STEP id — what `--step` takes — never by the internal
    # `step/<id>` unit key, which no command accepts.
    assert "phase/1/implement-phase is ALREADY HELD by an unclaimed agent" in flat
    assert "step/phase/1/implement-phase" not in flat
    assert "super-fr:fr-phase-executor" in flat
    assert "fr run resolve r1 --step phase/1/implement-phase --state done" in flat
    assert "done|failed" not in flat
    assert "fr run claim r1 --step phase/1/implement-phase --abandoned" in flat
    assert "fr run advance r1 --redispatch" in flat
    assert "--item" not in flat
    assert "{" not in result.output


# --- `--redispatch`: the deliberate escape, not a second mode (P4.T2) -------


def test_redispatch_closes_the_holder_abandoned_and_appends_a_fresh_record(
    tmp_path: Path,
) -> None:
    """Case (a) + review finding r2: the old holder's id stays in the list.

    Overwriting the record would lose the one thing gh-503 asked for — who
    was holding this tree when we took it away from them — so the abandon
    and the new dispatch are two elements, oldest first."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--agent", "lost-one"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    records = _dispatch_of(repo, "implement", "phase/1/code")
    assert len(records) == 2
    assert records[0].agent == "lost-one"  # the forensic trail, intact
    assert records[0].outcome == "abandoned"
    assert records[0].returned is not None
    assert records[1].agent is None  # the new hold is unclaimed until claimed
    assert records[1].returned is None
    assert records[1].outcome is None


def test_redispatch_prints_the_brief_and_exits_zero(tmp_path: Path) -> None:
    """Case (b): the escape must actually get the operator a brief — a
    `--redispatch` that only closed the record would trade one wedge for
    another."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    assert "ALREADY HELD" not in result.output
    brief = _brief_of(result.output)
    assert brief["step"] == "code"
    assert brief["item"] == "phase/1"


def test_redispatch_on_a_never_dispatched_unit_is_refused_and_records_nothing(
    tmp_path: Path,
) -> None:
    """Case (c): an escape, not a second mode — and not a second way to START.

    gh#508 first built this as "exactly a plain advance"; gh#519 SPECIFIED the
    opposite (its spec §3.A: "`--redispatch` with nothing outstanding exits
    2"), published it in the explainer and cited it in the acceptance matrix.
    The two tests asserted opposite exit codes for one command on one fixture,
    so one had to yield, and the specified, documented behaviour is the one
    kept. What this test still owns is the half gh#519's sibling
    (`test_redispatch_with_nothing_outstanding_is_refused`) does not look at:
    the DISPATCH map. A refused `--redispatch` must not leave a record behind
    — not an open one (a hold nobody has) and not an invented closed one."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 2, result.output
    assert "nothing is running" in result.output
    assert "{" not in result.stdout, result.stdout
    assert not _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])


def test_redispatch_after_an_abandon_does_not_close_the_closed_record_again(
    tmp_path: Path,
) -> None:
    """The other no-op shape: the last record is already CLOSED, so there is
    nothing held. `--redispatch` appends the one new hold a plain advance
    would, not a third element."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--abandoned"],
    )
    abandoned_at = _dispatch_of(repo, "implement", "phase/1/code")[0].returned

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    records = _dispatch_of(repo, "implement", "phase/1/code")
    assert len(records) == 2
    assert records[0].returned == abandoned_at  # untouched


def test_redispatch_works_on_a_flat_agent_step_too(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "lost-one"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    records = _dispatch_of(repo, "phase/1/implement-phase", "step/phase/1/implement-phase")
    assert len(records) == 2
    assert records[0].agent == "lost-one"
    assert records[0].outcome == "abandoned"
    assert records[1].returned is None
    assert load_run_state(repo, "r1").steps["phase/1/implement-phase"].state == "running"


def test_redispatch_leaves_the_run_artifact_structurally_valid(tmp_path: Path) -> None:
    """`--redispatch` APPENDS, and `fr.artifacts.structure.validate_run`
    enforces at most one open record per unit AND that the open one is the
    LAST element — so an abandon-then-append that got the order wrong would
    write an artifact `fr validate artifacts` refuses."""
    from fr.artifacts.structure import validate_run
    from fr.run.model import run_path

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])
    _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert validate_run(run_path(repo, "r1")) == []


# --- `resolve` closes the dispatch record, and accepts a late identity
# (spec §4.C, decision d2 — P4.T3) ---------------------------------------


def test_resolve_closes_a_grouped_members_record_with_the_state_as_outcome(
    tmp_path: Path,
) -> None:
    """Case (a), member half. `returned` and `outcome` are one fact
    (`DispatchRecord` enforces it), and the outcome IS `--state` — there is
    no third vocabulary for how a dispatch ended."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.returned is not None
    assert record.outcome == "done"


def test_resolve_failed_closes_the_record_with_outcome_failed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "failed"],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.outcome == "failed"
    assert record.returned is not None


def test_resolve_closes_a_flat_agent_steps_record(tmp_path: Path) -> None:
    """Case (a), flat half — the same `_unit_key` mapping, so the flat and
    grouped key spaces stay the one thing phase 3 made them."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    (repo / "s.md").write_text("# spec\n")
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

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
    record = _dispatch_of(repo, "brainstorm", "step/brainstorm")[0]
    assert record.returned is not None
    assert record.outcome == "done"


def test_resolve_fills_an_unclaimed_record_with_a_late_identity(tmp_path: Path) -> None:
    """Case (b) / decision d2: an orchestrator that never called `claim` can
    still say who held the unit, at the one moment it certainly knows —
    when the agent hands back."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--state",
            "done",
            "--agent",
            "late-one",
            "--harness",
            "claude-code",
            "--model",
            "claude-opus-5",
        ],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.agent == "late-one"
    assert record.harness == "claude-code"
    assert record.model == "claude-opus-5"
    assert record.outcome == "done"


def test_resolve_refuses_an_agent_that_disagrees_with_the_claim(tmp_path: Path) -> None:
    """Case (c): two ids on one hold is the two-writers hazard, and taking
    the `resolve` route instead of the `claim` route must not be a way
    around the refusal. Both ids are named — the operator has to be able to
    tell which one is wrong."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--agent", "holder-a"],
    )

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--state",
            "done",
            "--agent",
            "stranger-b",
        ],
    )

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    assert "holder-a" in flat
    assert "stranger-b" in flat
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.agent == "holder-a"
    assert record.returned is None  # refused, so NOT closed either


def test_resolve_accepts_the_same_agent_it_was_claimed_by(tmp_path: Path) -> None:
    """The idempotent half of (c): re-reporting the id already on the record
    is agreement, not conflict."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--agent", "holder-a"],
    )

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--state",
            "done",
            "--agent",
            "holder-a",
        ],
    )

    assert result.exit_code == 0, result.output
    record = _dispatch_of(repo, "implement", "phase/1/code")[0]
    assert record.agent == "holder-a"
    assert record.outcome == "done"


def test_resolve_a_gated_step_with_no_dispatch_record_still_works(tmp_path: Path) -> None:
    """Case (d): a gated step is marked `blocked`, never dispatched, so it
    has no record at all. `resolve` must close nothing and succeed —
    a run adopted from disk is the same shape, and it must not start
    failing because this feature landed."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    (repo / "s.md").write_text("# spec\n")
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    assert _attempts_by_unit(load_run_state(repo, "r1").steps["brainstorm"]) is None

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
    assert _attempts_by_unit(state.steps["brainstorm"]) is None  # nothing invented


def test_resolve_after_an_abandon_leaves_the_closed_record_alone(tmp_path: Path) -> None:
    """The other half of (d): there IS a record, but it is already closed.
    `resolve` must not re-close it with a second timestamp and a different
    outcome — `abandoned` is what happened to that attempt."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--abandoned"],
    )
    before = _dispatch_of(repo, "implement", "phase/1/code")[0]

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
    )

    assert result.exit_code == 0, result.output
    records = _dispatch_of(repo, "implement", "phase/1/code")
    assert len(records) == 1
    assert records[0] == before


def test_resolve_still_refuses_while_another_unit_is_running(tmp_path: Path) -> None:
    """The phase-5 "one writer at a time" refusal in `_resolve_member` is a
    DIFFERENT check — another UNIT is outstanding, not this one's holder —
    and both must survive. Pinned here because closing the dispatch record
    touches the same function."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches code

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1", "--state", "done"],
    )

    assert result.exit_code == 2, result.output
    assert "still running" in _squash(result.output)
    assert _dispatch_of(repo, "implement", "phase/1/code")[0].returned is None


def test_advance_re_briefs_a_failed_unit_whose_record_resolve_closed(tmp_path: Path) -> None:
    """P4.T1.S1(e)'s other route, now reachable: `resolve --state failed`
    closes the record, so the unit is no longer HELD and a retry briefs it
    again — appending a second attempt rather than being refused."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "failed"],
    )

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "ALREADY HELD" not in result.output
    records = _dispatch_of(repo, "implement", "phase/1/code")
    assert len(records) == 2
    assert records[0].outcome == "failed"
    assert records[1].returned is None


def test_completing_a_step_does_not_erase_its_dispatch_history(tmp_path: Path) -> None:
    """`_complete_step` rebuilds the `StepRecord` from scratch and carries
    `items`/`members` forward by hand — `dispatch` has to ride along too, or
    the forensic trail gh-503 asked for is deleted by the very act of
    finishing: the group's whole per-phase history would vanish at the
    moment its last member resolves."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches peer-review

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "peer-review",
            "--item",
            "phase/1",
            "--state",
            "done",
        ],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["implement"].state == "done"  # the group completed
    dispatch = _attempts_by_unit(state.steps["implement"])
    assert dispatch is not None, "completing the group deleted its dispatch history"
    assert sorted(dispatch) == ["phase/1/code", "phase/1/peer-review"]
    assert dispatch["phase/1/code"][0].outcome == "done"
    assert dispatch["phase/1/peer-review"][0].outcome == "done"


def test_resolve_refuses_an_unknown_harness_value(tmp_path: Path) -> None:
    """Same closed vocabulary `claim` validates against — one of
    `fr.harness`'s HARNESSES or nothing, never an invented fifth name."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--state",
            "done",
            "--agent",
            "a1",
            "--harness",
            "carrier-pigeon",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "carrier-pigeon" in _squash(result.output)


# ---------------------------------------------------------------------------
# Phase 5 — `fr run status` renders the holder; `fr run check` reports the
# open/unclaimed debt (spec §4.C, §4.B.1). Case letters follow P5.T1.S1.
# ---------------------------------------------------------------------------


def test_status_renders_held_by_and_the_claimed_identity(tmp_path: Path) -> None:
    """Case (a): a held (open) unit prints `HELD BY <agent> (<harness>,
    <model>) since <dispatched>`, indented under the unit's own line."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "add889a73824c8413",
            "--harness",
            "claude-code",
            "--model",
            "claude-opus-5",
        ],
    )

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"^ {6}HELD BY agent add889a73824c8413 \(claude-code, claude-opus-5\) since \S+$",
        result.output,
        re.MULTILINE,
    ), result.output


def test_status_renders_an_unclaimed_open_dispatch(tmp_path: Path) -> None:
    """Case (d): nobody has called `claim` yet — `an unclaimed agent`, not a
    guess and not a blank."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"^ {6}HELD BY an unclaimed agent( \([^)]+\))? since \S+$", result.output, re.MULTILINE
    ), result.output


def test_status_renders_a_settled_dispatch(tmp_path: Path) -> None:
    """Case (b): a closed record prints `<agent> (<harness>, <model>)
    <dispatched> -> <returned> <outcome>`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "add889a73824c8413",
            "--harness",
            "claude-code",
            "--model",
            "claude-opus-5",
        ],
    )

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "phase/1/implement-phase", "--state", "done"],
    )
    assert result.exit_code == 0, result.output

    status = _invoke(repo, shipped, ["run", "status", "r1"])

    assert status.exit_code == 0, status.output
    assert re.search(
        r"^ {6}agent add889a73824c8413 \(claude-code, claude-opus-5\) "
        r"\S+ -> \S+ done$",
        status.output,
        re.MULTILINE,
    ), status.output


def test_status_renders_held_by_the_orchestrator(tmp_path: Path) -> None:
    """Case (c): `agent_type: None` (an orchestrator-run `kind: agent` step,
    spec §4.B.1) renders `held by the orchestrator`, not a missing value."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])
    # FR_HARNESS pinned so the descriptor is deterministic: since finding f8
    # the record carries the harness `advance` detected, and this process IS a
    # Claude Code session, so the ambient environment would otherwise decide
    # what this assertion sees.
    _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "claude-code"}
    )  # brainstorm: agent_type None

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"^ {6}held by the orchestrator \(claude-code\) since \S+$", result.output, re.MULTILINE
    ), result.output


def test_status_shows_every_record_of_a_unit_oldest_first(tmp_path: Path) -> None:
    """Case (e): a `--redispatch`ed unit keeps every attempt, oldest first —
    the abandoned holder's line printed before the fresh, unclaimed one."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "code", "--item", "phase/1", "--agent", "lost-one"],
    )
    _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    lines = [
        line
        for line in result.output.splitlines()
        if "lost-one" in line or "unclaimed agent" in line
    ]
    assert len(lines) == 2, result.output
    assert "lost-one" in lines[0] and "abandoned" in lines[0]
    assert "unclaimed agent" in lines[1]


def test_status_output_is_byte_identical_for_a_run_with_no_dispatch_data(tmp_path: Path) -> None:
    """Case (f): a run whose steps never opened a dispatch record — every
    step here is `kind: cli` — renders exactly as it did before this phase."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    assert result.exit_code == 0, result.output
    assert result.output == (
        "run: r1\n"
        "workflow: cli-only@1\n"
        "branch: b\n"
        "cursor: hello\n"
        "  hello: pending\n"
        "  bye: pending\n"
    )


# --- `fr run check` reports open dispatches and counts unclaimed ones -------


def test_check_reports_an_open_dispatch_with_its_claimed_holder(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "a1"],
    )

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "step/phase/1/implement-phase" in result.output
    assert "agent a1" in result.output


def test_check_counts_an_unclaimed_open_dispatch_as_debt_not_a_failure(tmp_path: Path) -> None:
    """An unclaimed dispatch is visible debt, the same nagging shape
    `answered_by` already has (spec §4.C) — it must NOT change the exit code."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])  # opens, never claimed

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output  # the exit code IS the contract
    assert "1 unclaimed dispatch" in result.output


def test_check_does_not_count_a_closed_dispatch_as_open_or_unclaimed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat-agent-collision", _FLAT_AGENT_COLLISION_SHAPE)
    _invoke(
        repo, shipped, ["run", "start", "flat-agent-collision", "--branch", "b", "--run-id", "r1"]
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "phase/1/implement-phase", "--state", "done"],
    )

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "unclaimed" not in result.output
    assert "step/phase/1/implement-phase" not in result.output


def test_check_reports_an_orchestrator_open_dispatch_without_counting_it_unclaimed(
    tmp_path: Path,
) -> None:
    """An orchestrator-run step (`agent_type: None`) never carries an `agent`
    by design — it must not inflate the unclaimed count every single run."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "held by the orchestrator" in result.output
    assert "unclaimed dispatch" not in result.output


# ------------------------------------------------------------------------


# Grafted from gh#519 (fr run cursor cluster) when that branch was folded


# into this one: its coverage for #496 manual phases, #499's refusal, #500


# session binding and #501 composite ids. Kept whole rather than rewritten.


# ------------------------------------------------------------------------


_SHIPPED_FR_GOAL = (
    Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml"
)


_BACKDATED = "2026-01-01T00:00:00+00:00"


def _backdate(repo: Path, step_id: str) -> str:
    """Rewind a step record's `at` so a refresh is observable.

    `_now()` has second resolution, so two `advance`s in one test run land on
    the same timestamp far more often than not — asserting "`at` moved" would
    be a coin flip. Backdating makes the claim deterministic.
    """
    from fr.run.model import save_run_state

    state = load_run_state(repo, "r1")
    record = state.steps[step_id].model_copy(update={"at": _BACKDATED})
    save_run_state(repo, state.model_copy(update={"steps": {**state.steps, step_id: record}}))
    return _BACKDATED


def _drive_the_group(repo: Path, shipped: Path) -> list[str]:
    """advance → resolve until the group stops briefing, returning every
    stdout it produced along the way.

    The assertion that matters is over the WHOLE transcript — "no brief was
    ever built for phase 4" is a claim about every dispatch the run made, not
    about the one a single `advance` happened to emit.
    """
    outputs: list[str] = []
    for _ in range(20):
        advanced = _invoke(repo, shipped, ["run", "advance", "r1"])
        outputs.append(advanced.output)
        assert advanced.exit_code == 0, advanced.output
        if "{" not in advanced.output:
            return outputs  # the group completed instead of briefing a unit
        brief = _brief_of(advanced.output)
        resolved = _invoke(
            repo,
            shipped,
            [
                "run",
                "resolve",
                "r1",
                "--step",
                brief["step"],
                "--item",
                brief["item"],
                "--state",
                "done",
            ],
        )
        outputs.append(resolved.output)
        assert resolved.exit_code == 0, resolved.output
        if "implement: done" in resolved.output:
            return outputs  # the last member's resolve completed the group
    raise AssertionError("the group never completed")


def _fr_goal_at_implement(repo: Path, shipped: Path) -> None:
    """Drive the REAL shipped `fr-goal` manifest to its `implement` group.

    #501 is a message about `fr-goal`'s own ids (`phase/1/implement-phase`,
    workflow `'fr-goal'`), so the fixture is the shipped file itself rather
    than a convenient stand-in — this is the walking skeleton's proof that
    the CLI harness reaches the real runtime.
    """
    import shutil

    shipped.mkdir(parents=True, exist_ok=True)
    shutil.copy(_SHIPPED_FR_GOAL, shipped / "fr-goal.yaml")

    spec_rel = "docs/superpowers/specs/2026-09-20-fixture-design.md"
    (repo / spec_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / spec_rel).write_text("# Fixture\n")
    from tests.unit.skeleton_override import write_skeleton_override

    slug = "2026-05-09-fixture-minimal"
    plan_rel = f"docs/superpowers/plans/{slug}"
    shutil.copytree(_FIXTURE_PLAN, repo / plan_rel)
    write_skeleton_override(repo)  # sole-skeleton fixture, debug journal C2

    def step(argv: list[str]) -> None:
        result = _invoke(repo, shipped, argv)
        assert result.exit_code == 0, f"{argv}: {result.output}"

    step(["run", "start", "fr-goal", "--branch", "b", "--run-id", "r1"])
    step(["run", "advance", "r1"])  # brainstorm: blocked on its operator gate
    step(
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "brainstorm",
            "--state",
            "done",
            "--emitted",
            f"spec={spec_rel}",
        ]
    )
    step(["run", "advance", "r1"])  # spec-review: running
    step(["run", "resolve", "r1", "--step", "spec-review", "--state", "done"])
    step(["run", "advance", "r1"])  # plan: running
    step(
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            f"plan={plan_rel}",
        ]
    )
    step(["run", "advance", "r1"])  # plan-review: kind cli, executed here
    assert load_run_state(repo, "r1").cursor == "implement"


def _isolation_state_for(repo: Path, branch: str) -> None:
    """Record an isolation workspace for `branch`, as `fr isolation up` would.

    `_repo` builds a real linked worktree carrying a `.fr-isolation` marker,
    which is what `ensure_run_workspace` reads — but `sessions.attach` reads
    the isolation STATE file (`<common .git>/fr/isolation/<branch>.json`), a
    different artifact that only `up` writes. Without it `attach` raises
    `IsolationError`, which is the other test's subject.
    """
    from fr.isolation.types import IsolationState, save_state

    save_state(
        IsolationState(
            repo_root=repo,
            branch=branch,
            worktree=repo,
            profile="host",
            created_at="2026-09-20T00:00:00+00:00",
        )
    )


def _plan_with_tags(
    repo: Path,
    shapes: list[tuple[int, str, tuple[int, ...]]],
    *,
    slug: str = "2026-09-20-tagged",
) -> str:
    """Scaffold a real plan whose phases are exactly `(number, tag, deps)`.

    Built inline rather than copied from a fixture folder for the reason
    spec §1.4 measured: no plan folder on disk — live, archived or fixture —
    has a manual phase anywhere but its trailing block, so the shapes #496
    is about can only be constructed. One task, one step per phase, so
    `plan_locally_complete` is decided purely by whether the test ticks it.
    """
    from fr.plan_ops import PhaseSpec, create

    specs = repo / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec_rel = f"docs/superpowers/specs/{slug}-design.md"
    (repo / spec_rel).write_text(
        "# Tagged\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    create(
        repo_root=repo,
        slug=slug,
        spec=spec_rel,
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=n,
                title=f"Phase {n}",
                tag=tag,  # type: ignore[arg-type]
                depends_on=deps,
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": f"P{n}.T1.S1", "text": "do the thing"}],
                    },
                ),
            )
            for n, tag, deps in shapes
        ],
        prose="# x\n",
    )
    return f"docs/superpowers/plans/{slug}"


def test_run_start_binds_the_session_when_given_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#500: a run started with `--session` leaves the workspace attributable.

    Every fr-goal workspace reported `sessions=none` because `fr run start`
    entered isolation itself and never bound the caller (spec §3.C.1).
    """
    from fr.isolation.types import load_state

    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    repo = _repo(tmp_path, branch="feat/x")
    _isolation_state_for(repo, "feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "start",
            "cli-only",
            "--branch",
            "feat/x",
            "--run-id",
            "r1",
            "--session",
            "s1",
            "--harness",
            "claude-code",
        ],
    )

    assert result.exit_code == 0, result.output
    state = load_state(repo, "feat/x")
    assert state is not None
    assert [(b.session_id, b.harness) for b in state.sessions] == [("s1", "claude-code")]


def test_run_start_binds_the_ambient_session_when_none_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-09-21 debug journal C4: the first fr-goal run after the #508
    refactor reported `sessions=none` although every cursor attempt recorded
    the session id. The run was started as `uv run fr run start …` (this repo's
    AGENTS.md mandates `uv run fr`), which the bind hook's start-anchored
    `^fr …` regex never matches — and `start` bound nothing without an explicit
    `--session`, although it already knows the session (`current_session`, the
    same rule `advance` stamps every attempt with). A missing binding also
    silences the Stop idle guard (#518), which finds a run only through it.

    The engine now binds what it knows; the hook is no longer the only path.
    """
    from fr.isolation.types import load_state

    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    repo = _repo(tmp_path, branch="feat/x")
    _isolation_state_for(repo, "feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"],
        {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "ambient-1"},
    )

    assert result.exit_code == 0, result.output
    state = load_state(repo, "feat/x")
    assert state is not None
    assert [(b.session_id, b.harness) for b in state.sessions] == [("ambient-1", "claude-code")]


def test_run_start_binds_nothing_when_no_session_is_knowable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ambient default must never invent a session: no `--session` and no
    session id in the environment is exactly the pre-C4 behaviour."""
    from fr.isolation.types import load_state

    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    repo = _repo(tmp_path, branch="feat/x")
    _isolation_state_for(repo, "feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"],
        {"CLAUDE_CODE_SESSION_ID": None},
    )

    assert result.exit_code == 0, result.output
    state = load_state(repo, "feat/x")
    assert state is not None
    assert state.sessions == []


def test_run_start_warns_but_succeeds_when_attach_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed bind must never cost the operator a started run (spec §3.C.1).

    Bindings are traceability, not enforcement — the edit gate never consults
    one — so `attach` blowing up warns and the run file still exists.
    """
    from fr.isolation import sessions as _sessions
    from fr.isolation.types import IsolationError

    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    repo = _repo(tmp_path, branch="feat/x")
    _isolation_state_for(repo, "feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    def _boom(*args: object, **kwargs: object) -> None:
        raise IsolationError("no isolation workspace for branch 'feat/x'")

    monkeypatch.setattr(_sessions, "attach", _boom)

    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1", "--session", "s1"],
    )

    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "superpowers" / "runs" / "r1.yaml").is_file()
    assert "feat/x" in result.stderr
    assert "could not bind session" in result.stderr


def test_advance_refusing_a_running_agent_step_executes_and_writes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """Was `..._brief_is_re_emitted_idempotently_while_running`, which asserted
    exit 0 and a second brief — the #499 behaviour itself, pinned as if it were
    the contract. The claim worth keeping is the other one: the second
    `advance` still executes nothing (the no-claude-p-batch half) and now also
    writes nothing, so the run file is byte-identical across the refusal."""
    import fr.commands.run_cmd as run_cmd

    def _boom(*args, **kwargs):
        raise AssertionError("must never execute anything for an agent step")

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    monkeypatch.setattr(run_cmd.subprocess, "run", _boom)  # see the test above
    _invoke(repo, shipped, ["run", "advance", "r1"])
    before = (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text()

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "running"
    assert (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text() == before


def test_advance_refusing_a_running_unit_leaves_the_run_file_alone(tmp_path: Path) -> None:
    """Was `test_advance_is_idempotent_over_the_snapshot`: "re-dispatching the
    same unit (advance while running) refreshes the one snapshot rather than
    stacking them". A plain `advance` no longer re-dispatches at all (#499),
    so that claim moved to `--redispatch`
    (`test_redispatch_refreshes_the_dispatch_time_and_that_units_snapshot`).

    Kept, because the refusal has a claim of its own and this test was still
    passing for the WRONG reason without it: nothing at all is written, so the
    whole run file is byte-identical across the refused call."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    before = (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text()

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_text() == before
    assert list(_accounting(load_run_state(repo, "r1"))) == ["phase/1/code"]


def test_resolve_composite_member_id_teaches_the_two_flags(tmp_path: Path) -> None:
    """#501: `advance` prints `phase/1/implement-phase`, and pasting it into
    `--step` was refused with "not found in workflow", which sends the reader
    to the shape file instead of to the flag list."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches phase/1/implement-phase

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "phase/1/implement-phase", "--state", "done"],
    )

    assert result.exit_code == 2, result.output
    assert "--step implement-phase" in result.output
    assert "--item phase/1" in result.output


def test_advance_prints_the_resolve_command_before_the_json(tmp_path: Path) -> None:
    """The other half of #501: pre-empt the error rather than only improving
    it. `advance` already prints the composite in its human line; it now also
    prints the exact resolve command — BEFORE the JSON brief, because
    `run_cmd` treats the brief as the line a naive `tail -1` parses (the same
    ordering constraint the gate-degradation notice documents)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    expected = "fr run resolve r1 --step implement-phase --item phase/1 --state done"
    assert any(expected in line for line in result.output.splitlines()), result.output
    # The brief is still the last line `tail -1` reads.
    brief = json.loads(result.output.strip().splitlines()[-1])
    assert brief["step"] == "implement-phase"
    assert brief["item"] == "phase/1"


def test_the_printed_resolve_command_actually_runs_as_printed(tmp_path: Path) -> None:
    """Review `r1-f1`. The hint is printed under "resolve with:" and is meant
    to be PASTED, so the test pastes it: lift the command off stdout, split it
    the way a shell would, and run it.

    The bug this pins is not cosmetic. The first spelling ended
    `--state done|failed`, and `|` is a pipe in every POSIX shell — pasting it
    runs the resolve with `--state done` and THEN dies with
    `command not found: failed`, exit 127, over a run whose state has already
    moved. Asserting the absence of a `|` would pass for the wrong reason the
    moment someone wrote `<done|failed>`; running the line is what actually
    holds."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)

    advanced = _invoke(repo, shipped, ["run", "advance", "r1"])
    hint = next(line for line in advanced.output.splitlines() if "resolve with:" in line).split(
        "resolve with:", 1
    )[1]

    # A shell would treat any of these as control operators, not argv.
    pasteable, _, _ = hint.partition("(or ")
    assert not set(pasteable) & set("|&;<>()$`"), f"not pasteable: {pasteable!r}"

    argv = shlex.split(pasteable)
    assert argv[:2] == ["fr", "run"], argv
    result = _invoke(repo, shipped, argv[1:])  # drop the literal `fr`

    assert result.exit_code == 0, result.output
    assert "implement-phase phase/1: done" in result.output


def test_the_composite_id_refusal_survives_a_narrow_console(tmp_path: Path) -> None:
    """Review `r1-f2`. `_find_step`'s message ends in the flag pair the reader
    is supposed to copy, and rich folds at width 80 whenever stderr is not a
    tty — which is exactly when a harness captures it. Without `soft_wrap` the
    pair breaks mid-line and the one actionable thing on the page becomes
    unusable."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "phase/1/implement-phase", "--state", "done"],
    )

    assert result.exit_code == 2, result.output
    assert any(
        "--step implement-phase --item phase/1" in line for line in result.output.splitlines()
    ), result.output


def test_advance_refuses_a_running_member(tmp_path: Path) -> None:
    """#499, the grouped half. `_advance_group`'s pending-picker was
    `items.get(key) != "done"`, which cannot tell `running` from `pending`, so
    a second `advance` re-emitted a byte-identical brief for a unit already
    dispatched.

    Why this is worse than a papercut (spec §1.1): fr-goal §5 dispatches phase
    executors into the ONE isolation worktree that already exists —
    `isolation: "worktree"` is refused for them by design (#420) — so the usual
    two-agents-one-tree protection is deliberately unavailable. A second brief
    means two executors editing the same files and committing to the same
    branch."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    first = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert first.exit_code == 0, first.output
    # Decision u1: the dispatch record is the witness, so the moment the
    # refusal names is the RECORD's `dispatched`, not the group's `at` — the
    # two are separate `_now()` calls and only usually the same second.
    dispatched_at = _dispatch_of(repo, "implement", "phase/1/implement-phase")[0].dispatched
    assert dispatched_at

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    # HELD, not RUNNING: `advance` opened a record, so there IS a holder to
    # name — unclaimed, because nobody ran `fr run claim`. RUNNING is now the
    # wording for the one case with no record at all
    # (`test_a_running_member_with_no_dispatch_record_is_still_refused`).
    flat = _squash(result.output)
    assert "phase/1/implement-phase is ALREADY HELD by an unclaimed agent" in flat
    assert "ALREADY RUNNING" not in flat
    assert dispatched_at in result.output, result.output
    # both ways forward, and the resolve one is the two-flag form (#501)
    assert "fr run resolve r1 --step implement-phase --item phase/1 --state done" in result.output
    assert "--redispatch" in result.output
    # nothing a harness could mistake for an instruction to act
    assert "{" not in result.stdout, result.stdout


def test_advance_refuses_a_running_top_level_agent_step(tmp_path: Path) -> None:
    """#499, the ungrouped half. `advance_cmd`'s `agent` branch marked the
    step `running` only when it was not already, then printed the brief
    unconditionally — so the state was right and the output lied."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    first = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert first.exit_code == 0, first.output
    step_at = load_run_state(repo, "r1").steps["plan"].at
    dispatched_at = _dispatch_of(repo, "plan", "step/plan")[0].dispatched
    assert dispatched_at

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    # `_AGENT_SHAPE`'s step names no `agent:`, so the orchestrator runs it
    # itself and IS the holder (decision u1: the record is the witness).
    flat = _squash(result.output)
    assert "plan is ALREADY HELD by the orchestrator" in flat
    assert "ALREADY RUNNING" not in flat
    assert dispatched_at in result.output, result.output
    # no `--item` for a top-level step: it has no unit to address
    assert "fr run resolve r1 --step plan --state done" in result.output
    assert "--item" not in result.output, result.output
    assert "{" not in result.stdout, result.stdout
    # and the refusal wrote nothing
    assert load_run_state(repo, "r1").steps["plan"].at == step_at
    assert len(_dispatch_of(repo, "plan", "step/plan")) == 1


_RECORDLESS_SHAPES = ("adopted", "migrated")
"""The two ways a v5 cursor holds a `running` unit fr never RECORDED
dispatching. `adopted`: no attempt at all (`fr run adopt`, or a v2-v4 cursor
that had no cost snapshot either). `migrated`: exactly one attempt, the
`synthesized` one the 4 -> 5 rewrite creates to carry a pre-dispatch-record
cost snapshot — the MAJORITY of real migrated cursors. Neither is a witness."""


def _forget_dispatch_records(repo: Path, step_id: str, *, shape: str = "adopted") -> None:
    """Make `step_id` look the way a cursor written BEFORE the dispatch record
    existed looks once it reaches v5: running, and with no witness.

    That shape is real, not hypothetical — `run` 2 -> 3 -> 4 are stamp-only
    migrations, so a v2 cursor caught mid-dispatch arrives exactly like this
    (gh#517's own cursor did: `deliver: running`, no `dispatch`). Built by
    letting the real CLI dispatch and then un-recording it, so everything else
    about the cursor is what fr wrote.

    This is the one place in this file that touches `StepRecord.units`
    directly: `fr.run.units` deliberately has no "drop the history" verb.
    """
    from fr.run.model import Attempt, save_run_state

    assert shape in _RECORDLESS_SHAPES
    state = load_run_state(repo, "r1")
    forgotten = {}
    for key, unit in (state.steps[step_id].units or {}).items():
        kept: tuple = ()
        if shape == "migrated" and unit.attempts and unit.attempts[-1].estimate is not None:
            last = unit.attempts[-1]
            kept = (Attempt(dispatched=last.dispatched, estimate=last.estimate, synthesized=True),)
        if unit.state is not None or kept:
            forgotten[key] = unit.model_copy(update={"attempts": kept})
    record = state.steps[step_id].model_copy(update={"units": forgotten or None})
    save_run_state(repo, state.model_copy(update={"steps": {**state.steps, step_id: record}}))


@pytest.mark.parametrize("shape", _RECORDLESS_SHAPES)
def test_a_running_member_with_no_dispatch_record_is_still_refused(
    tmp_path: Path, shape: str
) -> None:
    """Decision u1's fallback, grouped half. The record is the witness — but a
    unit that is `running` with NO record has no witness to consult, and "no
    open record" must not be read as "free": that would silently re-open
    gh#499 for every cursor that predates the record. It is refused on its
    state, in the wording that names only the clock, because there is no
    holder to name and inventing one would be worse than saying less."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _forget_dispatch_records(repo, "implement", shape=shape)
    before = load_run_state(repo, "r1")
    if shape == "migrated":  # the helper really did leave the synthesized attempt
        (only,) = units.attempts(before.steps["implement"], "phase/1/implement-phase")
        assert only.synthesized is True
    dispatched_at = before.steps["implement"].at

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    assert f"phase/1/implement-phase is ALREADY RUNNING (dispatched {dispatched_at})" in flat
    assert "ALREADY HELD" not in flat
    assert "{" not in result.stdout, result.stdout
    assert load_run_state(repo, "r1") == before  # a refusal writes nothing


def test_a_running_flat_step_with_no_dispatch_record_is_still_refused(tmp_path: Path) -> None:
    """The same fallback at the other call site — the exact shape gh#517's
    real cursor arrived in (`deliver: running`, no `dispatch`)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _forget_dispatch_records(repo, "plan")
    before = load_run_state(repo, "r1")
    dispatched_at = before.steps["plan"].at

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    assert f"plan is ALREADY RUNNING (dispatched {dispatched_at})" in flat
    assert "ALREADY HELD" not in flat
    assert "{" not in result.stdout, result.stdout
    assert load_run_state(repo, "r1") == before


@pytest.mark.parametrize("shape", _RECORDLESS_SHAPES)
def test_redispatch_is_the_way_out_of_a_recordless_running_unit(tmp_path: Path, shape: str) -> None:
    """A refusal with no escape is a wedge. `claim --abandoned` cannot help
    here — there is no record to close — so `--redispatch` has to: it
    re-briefs, and opens the first record this unit has ever had."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])
    _forget_dispatch_records(repo, "implement", shape=shape)

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["item"] == "phase/1"
    records = [
        r for r in _dispatch_of(repo, "implement", "phase/1/implement-phase") if not r.synthesized
    ]
    assert len(records) == 1
    assert records[0].returned is None
    # ...and the synthesized attempt, where there was one, is still there,
    # untouched and first: it was never a hold, so it was never "abandoned".
    every = _dispatch_of(repo, "implement", "phase/1/implement-phase")
    assert [bool(r.synthesized) for r in every] == (
        [True, False] if shape == "migrated" else [False]
    )
    if shape == "migrated":
        assert every[0].returned is None and every[0].outcome is None


def test_a_failed_unit_whose_only_attempt_is_synthesized_can_still_be_retried(
    tmp_path: Path,
) -> None:
    """The regression that would have blocked real in-flight runs on the day
    they were migrated. A unit that FAILED before the dispatch record existed
    had a cost snapshot and no record, and v4 `advance` simply re-briefed it.
    The 4 -> 5 rewrite gives that snapshot a synthesized attempt with no
    `returned`; read as a hold, `advance` refuses to retry the unit and names
    a holder that never existed. It is history, not a hold: the retry opens a
    NEW attempt beside it, and the cursor stays structurally valid (one open
    attempt — the synthesized one is never counted as open)."""
    from fr.artifacts.registry import artifact_kind
    from fr.run.model import run_path

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    failed = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "implement-phase", "--item", "phase/1"]
        + ["--state", "failed"],
    )
    assert failed.exit_code == 0, failed.output
    _forget_dispatch_records(repo, "implement", shape="migrated")
    key = "phase/1/implement-phase"
    before = load_run_state(repo, "r1").steps["implement"]
    assert units.unit_state(before, key) == "failed"
    assert [a.synthesized for a in units.attempts(before, key)] == [True]

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    flat = _squash(result.output)
    assert "ALREADY HELD" not in flat and "ALREADY RUNNING" not in flat, flat
    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["item"] == "phase/1"
    first, second = units.attempts(load_run_state(repo, "r1").steps["implement"], key)
    assert first.synthesized is True and first.returned is None, "history, left alone"
    assert second.synthesized is None and second.returned is None, "the retry is the hold"
    assert artifact_kind("run").validate(run_path(repo, "r1")) == []


def test_advance_still_briefs_a_blocked_gated_agent_step(tmp_path: Path) -> None:
    """Spec §3.A, "Unchanged". A `gate: operator` step is `blocked`, never
    `running`, and its brief is how the operator's question gets ASKED — the
    skill named in it is the thing that produces the answer the gate waits
    for. The #499 refusal sits after `_gate_pending`, so the two never
    interact and a re-entering orchestrator still sees what to dispatch."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "gated-agent", _GATED_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "gated-agent", "--branch", "b", "--run-id", "r1"])

    first = _invoke(repo, shipped, ["run", "advance", "r1"])
    second = _invoke(repo, shipped, ["run", "advance", "r1"])

    for result in (first, second):
        assert result.exit_code == 0, result.output
        assert "blocked on operator gate" in result.output
        assert _brief_of(result.output)["step"] == "brainstorm"
        assert "ALREADY RUNNING" not in result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


_BACKDATED = "2026-01-01T00:00:00+00:00"


def test_redispatch_re_emits_the_brief_for_the_outstanding_unit_only(tmp_path: Path) -> None:
    """`--redispatch` is the deliberate escape for a genuinely lost agent. It
    re-briefs the unit that IS outstanding — never a different one, and never
    by resetting anything already recorded back to pending."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches phase/1/code
    assert (
        _invoke(
            repo,
            shipped,
            ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
        ).exit_code
        == 0
    )
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches phase/1/peer-review

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["step"] == "peer-review"
    items = units.unit_states(load_run_state(repo, "r1").steps["implement"])
    assert items == {"phase/1/code": "done", "phase/1/peer-review": "running"}


def test_redispatch_refreshes_the_dispatch_time_and_that_units_snapshot(
    tmp_path: Path,
) -> None:
    """It refreshes `at` — so the ALREADY RUNNING refusal that follows names
    the re-dispatch, not the original — and rewrites that unit's accounting
    snapshot rather than stacking a second one."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _seed_journal(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches phase/1/code
    stale = _backdate(repo, "implement")

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["implement"].at != stale
    assert list(_accounting(state)) == ["phase/1/code"]


def test_redispatch_with_nothing_outstanding_is_refused(tmp_path: Path) -> None:
    """Spec §3.A: it exits 2 rather than quietly degrading into an ordinary
    advance. The operator reaching for the flag believes an agent is running;
    if none is, the mental model is wrong and saying so is the point."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 2, result.output
    assert "nothing is running" in result.output
    assert "{" not in result.stdout, result.stdout
    # and it did NOT fall through and dispatch the first pending unit
    assert units.unit_states(load_run_state(repo, "r1").steps["implement"]) == {}


def test_redispatch_never_executes_a_cli_step(tmp_path: Path) -> None:
    """A `cli` step is never `running` — fr executes it inline — so the flag
    has nothing to re-brief there and must not become a second way to run a
    command."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"])

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 2, result.output
    assert "nothing is running" in result.output
    assert load_run_state(repo, "r1").steps["hello"].state == "pending"


def test_redispatch_re_briefs_a_running_top_level_step(tmp_path: Path) -> None:
    """The escape exists at both call sites, or the ungrouped half of #499
    would be a wedge with no way out."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "agentic", _AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "agentic", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    stale = _backdate(repo, "plan")

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["step"] == "plan"
    state = load_run_state(repo, "r1")
    assert state.steps["plan"].state == "running"
    assert state.steps["plan"].at != stale


def test_the_refusals_two_commands_actually_run_as_printed(tmp_path: Path) -> None:
    """Review `r1-f1`, applied to the new surface. The refusal's whole point is
    that it names both ways forward, so both have to be pasteable: no shell
    metacharacter anywhere in the span a reader would copy, and the
    `--state failed` alternative kept OUTSIDE the command as prose. This lifts
    `re-brief anyway:` off the refusal and RUNS it, rather than asserting the
    absence of a `|` — which would pass for the wrong reason the moment
    someone wrote `<done|failed>`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _fr_goal_at_implement(repo, shipped)
    _invoke(repo, shipped, ["run", "advance", "r1"])

    refusal = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert refusal.exit_code == 2, refusal.output
    lines = refusal.output.splitlines()

    resolve_span, _, _ = (
        next(line for line in lines if "resolve it:" in line)
        .split("resolve it:", 1)[1]
        .partition("(or ")
    )
    assert not set(resolve_span) & set("|&;<>()$`"), f"not pasteable: {resolve_span!r}"

    rebrief = next(line for line in lines if "re-brief anyway:" in line).split(
        "re-brief anyway:", 1
    )[1]
    assert not set(rebrief) & set("|&;<>()$`"), f"not pasteable: {rebrief!r}"
    argv = shlex.split(rebrief)
    assert argv[:2] == ["fr", "run"], argv

    result = _invoke(repo, shipped, argv[1:])  # drop the literal `fr`

    assert result.exit_code == 0, result.output
    assert _brief_of(result.output)["step"] == "implement-phase"


def test_a_manual_phase_is_never_dispatched(tmp_path: Path) -> None:
    """#496, spec §3.D.3. Three agentic phases and a trailing `[manual]` one:
    the fan-out enumerates six units (3 phases × 2 members), never seven, and
    the phase it skipped is named in the cursor and at group completion."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(
        repo,
        [(1, "agentic", ()), (2, "agentic", ()), (3, "agentic", ()), (4, "manual", ())],
    )
    _started_grouped_with_plan(repo, shipped, plan_rel)

    outputs = _drive_the_group(repo, shipped)

    # (a) no brief was ever built for the manual phase
    briefs = [_brief_of(out) for out in outputs if "{" in out]
    assert [b["item"] for b in briefs] == [f"phase/{n}" for n in (1, 1, 2, 2, 3, 3)], [
        b["item"] for b in briefs
    ]
    # (b) the cursor records the deliberate omission
    items = units.unit_states(load_run_state(repo, "r1").steps["implement"])
    assert items.get("phase/4") == "manual", items
    # (c) group completion counts what was dispatched, and names what was not
    done_line = next(
        line for out in outputs for line in out.splitlines() if "implement: done" in line
    )
    assert "6 members done" in done_line, done_line
    assert "phase 4" in done_line and "manual" in done_line, done_line
    # (d) and `fr run status` shows it beside every other item
    status = _invoke(repo, shipped, ["run", "status", "r1"])
    assert "phase/4: manual" in status.output, status.output


def test_an_already_complete_manual_phase_is_still_recorded_manual(tmp_path: Path) -> None:
    """The fan-out filters on `tag: manual` alone — completion does not enter
    into it (review `r4-f1` draws the outstanding/manual distinction for the
    AUTHORING rule; this pins what the RUNTIME does with the other case).

    fr-goal §3's front-load shape is `1 [manual] (ticked, the operator's go),
    2 agentic`, and a ticked manual phase waits on nobody — but it is still
    not work this run did. Recording it `done` would claim a dispatch that
    never happened; recording it `manual` says what is true and keeps the two
    writers of `items` (`advance` and `fr run adopt`) able to agree without
    either of them consulting completion.
    """
    from fr.plan_ops import tick

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(repo, [(1, "manual", ()), (2, "agentic", ()), (3, "agentic", ())])
    tick(repo / plan_rel, "P1.T1.S1")
    _started_grouped_with_plan(repo, shipped, plan_rel)

    outputs = _drive_the_group(repo, shipped)

    briefs = [_brief_of(out) for out in outputs if "{" in out]
    assert [b["item"] for b in briefs] == [f"phase/{n}" for n in (2, 2, 3, 3)]
    items = units.unit_states(load_run_state(repo, "r1").steps["implement"])
    assert items.get("phase/1") == "manual", items


def test_resolving_a_manual_phase_member_names_the_tag(tmp_path: Path) -> None:
    """Spec §3.D.3. "not a phase member of 'implement' — expected phase/<n>
    for phases [1]" reads as a bug in the phase list when phase 2 plainly
    exists in the plan. The key is absent because it was deliberately never
    dispatched, and the refusal has to say which of the two it is."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(repo, [(1, "agentic", ()), (2, "manual", ())])
    _started_grouped_with_plan(repo, shipped, plan_rel)
    _invoke(repo, shipped, ["run", "advance", "r1"])  # dispatches phase/1/code

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/2", "--state", "done"],
    )

    assert result.exit_code == 2, result.output
    assert "`tag: manual`" in result.output, result.output
    assert "phase 2" in result.output, result.output
    assert "not a phase member" not in result.output, result.output


def test_a_middle_manual_phase_is_refused_at_group_start(tmp_path: Path) -> None:
    """Spec §3.D.2 point 2 — the preflight, defence in depth.

    `fr plan self-review` is the primary gate, but this shape (a repo-authored
    one, like an `fr run adopt`ed run) has no `plan-review` step, so the plan
    reaches the fan-out unchecked. `1 agentic, 2 manual (unticked), 3 agentic`
    is the one shape the rule forbids: phase 3 would run while a human is
    still owed phase 2. It is refused before ANY unit is dispatched — the
    hazard is the plan's, not this phase's.
    """
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(repo, [(1, "agentic", ()), (2, "manual", ()), (3, "agentic", ())])
    _started_grouped_with_plan(repo, shipped, plan_rel)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "phase 2 is `tag: manual`" in result.output, result.output
    assert "phase 3" in result.output, result.output
    # nothing was briefed, and nothing was claimed
    assert "{" not in result.stdout, result.stdout
    assert units.unit_states(load_run_state(repo, "r1").steps["implement"]) == {}
    assert load_run_state(repo, "r1").steps["implement"].state == "pending"


# --- #575 spec §3.D.5: an honest run-not-found at every load site ------------


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "status", "nope"],
        ["run", "gates", "nope"],
        ["run", "advance", "nope"],
        ["run", "resolve", "nope", "--step", "hello", "--state", "done"],
        ["run", "claim", "nope", "--step", "hello", "--agent", "a1"],
        ["run", "check", "--idle", "nope"],
    ],
    ids=["status", "gates", "advance", "resolve", "claim", "check-idle"],
)
def test_a_missing_run_is_explained_at_every_load_site(tmp_path: Path, argv: list[str]) -> None:
    """`_load_or_exit` and the three direct `load_run_state` call sites all
    answer through `preserve.explain_missing`, not a bare `no run state at`."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    started = _invoke(
        repo, shipped, ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output

    result = _invoke(repo, shipped, argv)

    assert result.exit_code == 2, result.output
    assert "no run state at" not in result.output
    assert "and fr has no record of one (never started here, or a mistyped id)" in result.stderr
    assert "Runs in this checkout: r1." in result.stderr


def test_start_refusing_an_existing_run_id_names_advance(tmp_path: Path) -> None:
    """After `up` restores a run, `fr run start` again with the same id is
    refused — and the refusal names `fr run advance <id>` as the way on
    (spec §3.D.4)."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)
    argv = ["run", "start", "cli-only", "--branch", "feat/x", "--run-id", "r1"]
    assert _invoke(repo, shipped, argv).exit_code == 0

    result = _invoke(repo, shipped, argv)

    assert result.exit_code == 2, result.output
    assert "already exists" in result.output
    assert "fr run advance r1" in result.output
