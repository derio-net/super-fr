"""WHEN a dispatch's holder becomes known differs per harness — and fr says so.

Found live on PR #508's Test Plan. The claim protocol was designed and
live-verified on Claude Code, whose dispatch returns an id at once and runs the
child in the background; then declared, unobserved, for OpenCode, whose task
tool BLOCKS and hands back the child session id with the result. The first live
OpenCode run showed the id arrives too late to answer "who holds it right now":
status from inside the child read `HELD BY an unclaimed agent (opencode, …)`.

Nothing in fr's behaviour was wrong — the open record still refuses a second
dispatch, and harness + model are recorded at dispatch. What was wrong is what
fr SAID: a skill instruction ("the moment a dispatch goes out, name its
holder") that an OpenCode orchestrator cannot follow, and no parity cell that
admitted the difference. Same defect class as the OpenCode SDK-version claim
corrected in #508: asserted, not observed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.harness import load_matrix

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = [
    REPO_ROOT / "plugins/super-fr/skills/fr-goal/SKILL.md",
    REPO_ROOT / ".opencode/skills/fr-goal/SKILL.md",
    REPO_ROOT / ".hermes/skills/fr/fr-goal/SKILL.md",
]


def _row():
    (row,) = [s for s in load_matrix().surfaces if s.id == "dispatch-holder-identity"]
    return row


def test_holder_identity_is_its_own_surface_not_a_clause_of_dispatch() -> None:
    """Dispatch IS enforced on OpenCode; holder identity is not. One row could
    not say both, so the honest cell had nowhere to live."""
    assert _row().kind == "interaction"


def test_claude_code_is_the_only_harness_proven_to_know_the_holder_in_flight() -> None:
    cells = _row().harnesses
    assert cells["claude-code"].state == "enforced"
    for harness in ("opencode", "hermes"):
        assert cells[harness].state == "partial", harness
        assert cells[harness].scope_note


def test_the_opencode_cell_says_what_was_observed() -> None:
    note = " ".join(_row().harnesses["opencode"].scope_note.split()).lower()
    assert "returns" in note
    assert "unclaimed" in note
    assert "refuses" in note  # what still holds must not be lost in the correction


def test_the_hermes_cell_does_not_claim_an_observation_nobody_made() -> None:
    note = " ".join(_row().harnesses["hermes"].scope_note.split()).lower()
    assert "not been observed" in note
    assert "in flight" in note


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parts[-4])
def test_the_skill_tells_a_blocking_harness_when_it_can_claim(path: Path) -> None:
    text = " ".join(path.read_text().split())
    assert "BLOCKS" in text
    assert "claim it when the call returns, before you resolve" in text
    # The instruction it replaces was unconditional, and unfollowable there.
    assert "The moment a dispatch goes out, name its holder" not in text
