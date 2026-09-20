"""Skill/agent prose tokens for the restored fr-goal methodology.

Companion to `test_fr_goal_journal.py` (which owns fr-goal's guards): the
same load-bearing tokens in fr-plan, fr-execute and fr-phase-executor —
a future edit that drops the skeleton mandate, the refactor contract, or
the handoff pointer should fail here, not silently regress the behavior.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_PLAN = REPO_ROOT / "plugins/super-fr/skills/fr-plan/SKILL.md"
FR_EXECUTE = REPO_ROOT / "plugins/super-fr/skills/fr-execute/SKILL.md"
FR_PHASE_EXECUTOR = REPO_ROOT / "plugins/super-fr/agents/fr-phase-executor.md"


def test_fr_plan_names_the_skeleton_mandate() -> None:
    t = FR_PLAN.read_text()
    assert "skeleton" in t.lower()


def test_fr_plan_names_phase_granularity_guidance() -> None:
    """The cost consequence of phase count is stated where phases are
    authored — with the live numbers behind it (`fr run status`)."""
    t = FR_PLAN.read_text()
    assert "4–6 phases" in t
    assert "fr run status" in t


def test_fr_plan_names_refactor_or_justify() -> None:
    t = FR_PLAN.read_text()
    assert "no-refactor-because" in t
    assert "red → green → refactor" in t


def test_fr_execute_names_refactor_or_justify() -> None:
    t = FR_EXECUTE.read_text()
    assert "no-refactor-because" in t


def test_fr_phase_executor_names_the_handoff_and_the_contract() -> None:
    """The brief source is the curated handoff (raw render is the STOP-path
    escape hatch), and the five contract norms are stated, not implied."""
    t = FR_PHASE_EXECUTOR.read_text()
    assert "fr journal handoff" in t
    assert "fr journal render" in t
    assert "no-refactor-because" in t
    assert "single writer" in t.lower()
    assert "return" in t.lower() and "reporting channel" in t.lower()


# --- The dispatch contract (#428) ------------------------------------------
#
# The executor is a leaf on both harnesses (no `Agent` tool on Claude Code,
# `task: deny` on OpenCode), so a step telling it to dispatch a subagent is
# unexecutable by construction. `fr plan self-review` errors on such a step at
# authoring time; these three tests pin the *execution*-time half — the prose
# contract that refuses the tick — plus the fr-plan guidance that prevents the
# step being written at all. One assert per load-bearing token.


def test_fr_phase_executor_names_the_dispatch_refusal() -> None:
    """The capability absence AND the consequence: a dispatch step is a
    BLOCKER that leaves the step unticked, not a deviation that ticks."""
    t = FR_PHASE_EXECUTOR.read_text()
    assert "no `Agent` tool" in t
    assert "task: deny" in t
    assert "BLOCKER" in t
    assert "unticked" in t


def test_fr_execute_names_the_dispatch_refusal() -> None:
    """fr-execute carries the same contract: it is the skill an OpenCode or
    Hermes child loads, so the contract cannot live only in the Claude Code
    agent file."""
    t = FR_EXECUTE.read_text()
    assert "no `Agent` tool" in t
    assert "task: deny" in t
    assert "BLOCKER" in t
    assert "unticked" in t


def test_fr_plan_names_outcomes_not_mechanisms() -> None:
    """Where the error is born: a step naming a tool rots the moment the
    actor changes, and rots silently."""
    t = FR_PLAN.read_text()
    assert "outcomes, not mechanisms" in t
    assert "#428" in t
