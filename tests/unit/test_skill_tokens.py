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
FR_GOAL = REPO_ROOT / "plugins/super-fr/skills/fr-goal/SKILL.md"
FR_PHASE_EXECUTOR = REPO_ROOT / "plugins/super-fr/agents/fr-phase-executor.md"
FR_PHASE_EXECUTOR_MIRRORS = sorted((REPO_ROOT / ".opencode/agent").glob("fr-phase-executor*.md"))


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


def test_fr_phase_executor_and_all_opencode_mirrors_carry_the_context_discipline_norm() -> None:
    """The sixth contract norm (spec §5.B1) and the pre-existing #461 norm
    ("the return value is the only reporting channel") must both be stated,
    not implied, in the canonical agent AND all four OpenCode mirrors — #461
    is closed here by verification, not by new prose (spec §5.D)."""
    assert len(FR_PHASE_EXECUTOR_MIRRORS) == 4, (
        f"expected 4 .opencode/agent/fr-phase-executor*.md mirrors, "
        f"found {[p.name for p in FR_PHASE_EXECUTOR_MIRRORS]}"
    )
    for path in (FR_PHASE_EXECUTOR, *FR_PHASE_EXECUTOR_MIRRORS):
        # Normalized (whitespace-collapsed) because the source prose wraps at
        # ~90 chars — a literal substring check is brittle to where a line
        # break happens to fall, the same trap "raw rich output" asserts hit.
        t = " ".join(path.read_text().lower().split())
        assert "re-derive from the code what the handoff already states" in t, path
        assert "narrowest thing that answers the question" in t, path
        assert "do not re-read a file you have already read this session" in t, path
        assert "never paste verbatim tool output into the return" in t, path
        assert "return" in t and "reporting channel" in t, path


def test_fr_goal_dispatch_brief_asks_for_a_summary_not_pasted_output() -> None:
    """spec §5.B2: fr-goal's own dispatch-brief guidance must agree with the
    executor contract it dispatches into — a pass/fail summary and journal
    ids, never pasted output (#461, closed by verification)."""
    t = FR_GOAL.read_text()
    assert "never pasted output" in t.lower()
    assert "pass/fail summary" in t.lower()
