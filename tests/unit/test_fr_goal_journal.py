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
