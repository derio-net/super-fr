"""Phase 6: fr-debugging records to the debug-scope journal.

Guards that fr-debugging step 3 writes the investigation via the `fr journal`
debug scope (not a hand-written debugging/<slug>.md) and step 4 derives its PR
body from `fr journal render --scope debug`.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_DEBUGGING = REPO_ROOT / "plugins/super-fr/skills/fr-debugging/SKILL.md"


def _text() -> str:
    return FR_DEBUGGING.read_text()


def test_records_to_debug_scope_journal() -> None:
    assert "fr journal add --scope debug" in _text()


def test_pr_body_rendered_from_debug_journal() -> None:
    assert "fr journal render --scope debug" in _text()


def test_new_journals_live_in_journals_tree() -> None:
    """New debug journals go under journals/, not the old debugging/ write path."""
    assert "journals/" in _text()


def test_mentions_hypothesis_trail_kinds() -> None:
    """The rejected-hypotheses trail — the crash-safe payoff — must be recorded."""
    t = _text()
    assert "hypothesis" in t and "ruled-out" in t
