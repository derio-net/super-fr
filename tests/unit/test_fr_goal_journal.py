"""Phase 5: fr-goal skill wires subagent dispatch + journal + tiering.

Guards that the SKILL.md rewrite kept the load-bearing tokens — a future edit
that drops the dispatch, the journal handoff, or the tiering resolution should
fail here, not silently regress the runtime behavior.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_GOAL = REPO_ROOT / "plugins/super-fr/skills/fr-goal/SKILL.md"


def _text() -> str:
    return FR_GOAL.read_text()


def test_dispatches_fr_phase_executor() -> None:
    assert "fr-phase-executor" in _text()


def test_journal_render_derives_pr_body() -> None:
    t = _text()
    assert "fr journal render" in t
    assert "fr journal add" in t


def test_journal_check_gates_delivery() -> None:
    assert "fr journal check" in _text()


def test_tiering_via_fr_models() -> None:
    assert "fr models" in _text()


def test_inline_fallback_documented() -> None:
    """A blocked dispatch must fall back to inline — never hard-fail."""
    assert "inline" in _text().lower()


def test_duplicate_report_rule_documented() -> None:
    """An executor that both returns and messages: the return wins (#461)."""
    assert "keep the return" in _text()


# --- methodology restoration: the skill must narrate what the shape enforces ---


def test_nested_per_phase_review_loop_narrated() -> None:
    """The grouped `implement` loop is the mechanism; prose without it is
    what drifted."""
    t = _text()
    assert "review-phase" in t
    assert "fr journal handoff" in t


def test_phase_one_skeleton_mandate_narrated() -> None:
    assert "skeleton" in _text().lower()


def test_refactor_or_justify_narrated() -> None:
    t = _text()
    assert "no-refactor-because" in t
    assert "red → green → refactor" in t
