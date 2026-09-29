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


def test_fr_renders_the_pr_body() -> None:
    """Spec 2026-09-25 §5.C.4: the PR body is fr's render (`pr-body.md`), not
    one the orchestrator assembles from `fr journal render` by hand."""
    t = _text()
    assert "pr-body.md" in t
    assert "--record" in t


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


def test_ready_checklist_guard_documented() -> None:
    """The PR body carries a Ready-checklist guard — the operator's checklist,
    not the orchestrator's (#814)."""
    t = _text()
    assert "Ready-checklist" in t
    assert "review ok" in t


def _deliver_section() -> str:
    """§8 only, whitespace-normalised, so a rewrap never fails a token."""
    t = _text()
    start = t.index("### 8. deliver")
    end = t.index("### Post-merge close-out", start)
    return " ".join(t[start:end].split())


def test_deliver_review_ok_and_ready_transition_are_the_operators() -> None:
    """#814, take 10 run A: §8 named "explicit review ok" as a ready condition
    without naming its owner, so the orchestrator took its own dispatched
    reviewer as the ok, ticked the box and ran `glab mr update --ready`."""
    s = _deliver_section()
    assert "the explicit review ok is the operator's" in s
    assert "the ready transition is the operator's" in s
    assert "never tick" in s
    assert "never mark the PR ready" in s
    # the old grant of the transition to the orchestrator is gone
    assert "ONLY when all three hold: mark it ready" not in s


def test_deliver_pushes_and_opens_the_draft_pr_before_the_full_suite() -> None:
    """#799: the local suite ran before the push, so CI and the ~10 min local
    suite never overlapped. Push + draft PR first, then the suite."""
    s = _deliver_section()
    push = s.index("push the branch and open or refresh the draft PR")
    suite = s.index("run the full suite YOURSELF")
    assert push < suite


def test_deliver_closeout_line_is_the_last_thing_relayed() -> None:
    """#814, take 10 run B: fr printed the closeout line and the final message
    dropped it. The relay is the last line of the final message."""
    s = _deliver_section()
    assert "the last line of your final message" in s


def test_fr_debugging_closeout_line_is_the_last_thing_relayed() -> None:
    t = " ".join(
        (REPO_ROOT / "plugins/super-fr/skills/fr-debugging/SKILL.md").read_text().split()
    )
    assert "the last line of your final message" in t


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
