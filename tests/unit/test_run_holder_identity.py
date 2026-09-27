"""Who holds an OpenCode-dispatched unit — gh#537 and gh#530.

gh#537: an OpenCode started from a Claude Code shell inherits `CLAUDECODE=1`
and `CLAUDE_CODE_SESSION_ID`, and fr recorded `claude-code` and a Claude Code
session as the holder of a unit OpenCode dispatched. `advance` must record the
harness fr actually runs under, and a session only when that harness owns the
session key it read.

gh#530: the child session is the one party that knows the holder while it
holds the unit — but it knows a session id and an agent name, not a step or
item. `fr run claim --open-unit` claims THE open, unclaimed unit that was
dispatched to that agent, and refuses (exit 2) rather than guess.
"""

from __future__ import annotations

import os
from pathlib import Path

from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _AGENT_TWO_STEP_SHAPE,
    _FLAT_AGENT_COLLISION_SHAPE,
    _attempts_by_unit,
    _invoke_as_harness,
    _repo,
    _write_shape,
)

_KEY = "step/phase/1/implement-phase"

# fr runs in-process under CliRunner, so ITS ancestry starts at this pytest
# process: OpenCode is placed here (nearest), Claude Code one hop further out
# — an OpenCode launched from a Claude Code shell.
_OPENCODE_UNDER_CLAUDE = {
    "CLAUDECODE": "1",
    "CLAUDE_PID": str(os.getppid()),
    "CLAUDE_CODE_SESSION_ID": "d756f763-cc-session",
    "OPENCODE": "1",
    "OPENCODE_PID": str(os.getpid()),
}


def _started(tmp_path: Path, shape: str = _FLAT_AGENT_COLLISION_SHAPE) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    name = shape.split("workflow:", 1)[1].split()[0]
    _write_shape(shipped, name, shape)
    started = _invoke_as_harness(
        repo, shipped, ["run", "start", name, "--branch", "b", "--run-id", "r1"], {}
    )
    assert started.exit_code == 0, started.output
    return repo, shipped


def _attempt(repo: Path, step: str = "phase/1/implement-phase", key: str = _KEY):
    found = _attempts_by_unit(load_run_state(repo, "r1").steps[step])
    assert found is not None
    return found[key][-1]


# --- gh#537: advance records the harness fr runs under ----------------------


def test_advance_under_opencode_launched_from_claude_code_records_opencode(
    tmp_path: Path,
) -> None:
    repo, shipped = _started(tmp_path)

    result = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], _OPENCODE_UNDER_CLAUDE)

    assert result.exit_code == 0, result.output
    attempt = _attempt(repo)
    assert attempt.harness == "opencode"
    # The inherited Claude Code session is not OpenCode's: recording it would
    # name a session that never held this unit.
    assert attempt.session is None


def test_advance_under_claude_code_still_records_its_session(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "advance", "r1"],
        {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "cc-own-session"},
    )

    assert result.exit_code == 0, result.output
    attempt = _attempt(repo)
    assert attempt.harness == "claude-code"
    assert attempt.session == "cc-own-session"


# --- gh#530: the child claims the one open unit dispatched to it -------------


def _open_unit_claim(repo: Path, shipped: Path, *extra: str, agent_type: str | None = None):
    argv = ["run", "claim", "--open-unit", "--agent", "ses_child", "--harness", "opencode"]
    if agent_type is not None:
        argv += ["--agent-type", agent_type]
    return _invoke_as_harness(repo, shipped, [*argv, *extra], {})


def test_open_unit_claim_names_the_child_and_the_tier_agent_that_ran(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _open_unit_claim(
        repo,
        shipped,
        "--model",
        "github-copilot/gpt-5.6-terra",
        agent_type="fr-phase-executor-standard",
    )

    assert result.exit_code == 0, result.output
    attempt = _attempt(repo)
    assert attempt.agent == "ses_child"
    assert attempt.agent_type == "fr-phase-executor-standard"
    assert attempt.harness == "opencode"
    assert attempt.model == "github-copilot/gpt-5.6-terra"
    assert attempt.returned is None


def test_open_unit_claim_is_idempotent_for_the_same_child(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    first = _open_unit_claim(repo, shipped, agent_type="fr-phase-executor-standard")
    second = _open_unit_claim(repo, shipped, agent_type="fr-phase-executor-standard")

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert _attempt(repo).agent == "ses_child"


def test_open_unit_claim_refuses_a_child_of_an_unrelated_agent(tmp_path: Path) -> None:
    """Any subagent's first tool call reaches the plugin. An `explore` child
    spawned while a phase is open is not that phase's holder."""
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _open_unit_claim(repo, shipped, agent_type="explore")

    assert result.exit_code == 2, result.output
    assert "no open unit dispatched to 'explore'" in result.output
    assert _attempt(repo).agent is None


def test_open_unit_claim_refuses_when_nothing_is_open(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)

    result = _open_unit_claim(repo, shipped, agent_type="fr-phase-executor-standard")

    assert result.exit_code == 2, result.output
    assert "no open" in result.output


def test_open_unit_claim_never_claims_work_the_orchestrator_runs_itself(tmp_path: Path) -> None:
    """An attempt with no `agent_type` is the orchestrator's own work; no
    child holds it, so no child may claim it."""
    repo, shipped = _started(tmp_path, _AGENT_TWO_STEP_SHAPE)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _open_unit_claim(repo, shipped, agent_type="fr-phase-executor")

    assert result.exit_code == 2, result.output
    assert "no open unit" in result.output
    assert _attempt(repo, "brainstorm", "step/brainstorm").agent is None


def test_open_unit_claim_refuses_a_unit_another_child_already_holds(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})
    _invoke_as_harness(
        repo,
        shipped,
        ["run", "claim", "r1", "--step", "phase/1/implement-phase", "--agent", "ses_first"],
        {"FR_HARNESS": "opencode"},
    )

    result = _open_unit_claim(repo, shipped, agent_type="fr-phase-executor-standard")

    assert result.exit_code == 2, result.output
    assert "no open unit" in result.output
    assert _attempt(repo).agent == "ses_first"


def test_open_unit_does_not_combine_with_a_named_unit(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _open_unit_claim(repo, shipped, "--step", "phase/1/implement-phase")

    assert result.exit_code == 2, result.output
    assert "does not combine" in result.output
    assert _attempt(repo).agent is None


def test_a_claim_refuses_an_agent_type_that_is_not_the_dispatched_agent(tmp_path: Path) -> None:
    """`--agent-type` records what RAN; it may name the dispatched agent or one
    of its `-<tier>` variants, never a different agent."""
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _invoke_as_harness(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "ses_child",
            "--agent-type",
            "fr-spec-reviewer-standard",
        ],
        {"FR_HARNESS": "opencode"},
    )

    assert result.exit_code == 2, result.output
    assert "was dispatched to" in result.output
    assert _attempt(repo).agent is None


def test_a_named_claim_records_the_tier_agent_that_ran(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})

    result = _invoke_as_harness(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            "phase/1/implement-phase",
            "--agent",
            "ses_child",
            "--agent-type",
            "fr-phase-executor-standard",
        ],
        {"FR_HARNESS": "opencode"},
    )

    assert result.exit_code == 0, result.output
    assert _attempt(repo).agent_type == "fr-phase-executor-standard"
