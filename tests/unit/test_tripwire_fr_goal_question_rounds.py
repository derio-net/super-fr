"""CI tripwire: the fixed-size question-batch contract must not come back.

Spec `2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.A/§3.A.1
replaces fr-goal's old promise — "one batched Q&A of at most four questions"
— with "one operator gate, sized to the feature, one round or two when the
second is announced up front or the operator asks for it". §3.A.1 lists every
surface that stated the old contract and must be rewritten in this PR: the
canonical `fr-goal` and `fr-brainstorming` skills, their OpenCode and Hermes
mirrors, the fr-goal explainer, and the top-level README.

This is a prose-only phase (the record-declaration mechanism and the
transcript-verifying gate shipped in phases 1-2) — nothing here exercises
code, only wording, and only wording is what a rewrap or a "helpful"
paraphrase silently regresses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FR_GOAL_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-goal" / "SKILL.md",
)

FR_BRAINSTORMING_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-brainstorming" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-brainstorming" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-brainstorming" / "SKILL.md",
)

# §3.A.1's full list of surfaces stating the old contract.
ALL_SURFACES = (
    *FR_GOAL_COPIES,
    *FR_BRAINSTORMING_COPIES,
    REPO_ROOT / "docs" / "explainers" / "01-fr-goal.md",
    REPO_ROOT / "README.md",
)

# The fixed-batch contract's own vocabulary. None of it may survive anywhere
# in scope — a stray phrase from the old contract is the regression this
# tripwire exists to catch.
OLD_CONTRACT_PHRASES = (
    "max 4",
    "≤4 questions",
    "ONE batch",
    "one batched Q&A",
    "no more than four questions",
    "ask ONCE",
)

# The new contract's own vocabulary — must appear on the canonical fr-goal
# skill and both its mirrors.
NEW_CONTRACT_MARKERS = (
    "Round 1 of",
    "never a round 3",
    "questions:",
)


@pytest.mark.parametrize("surface", ALL_SURFACES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
@pytest.mark.parametrize("phrase", OLD_CONTRACT_PHRASES)
def test_old_fixed_batch_contract_is_gone(surface: Path, phrase: str) -> None:
    text = surface.read_text(encoding="utf-8")
    assert phrase not in text, (
        f"{surface.relative_to(REPO_ROOT)} still states the old fixed-batch "
        f"contract ({phrase!r}) — spec §3.A.1 rewrites every surface in this "
        "table to the sized-round contract; see §3.A for the replacement wording."
    )


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
@pytest.mark.parametrize("marker", NEW_CONTRACT_MARKERS)
def test_fr_goal_states_the_new_round_contract(skill: Path, marker: str) -> None:
    text = skill.read_text(encoding="utf-8")
    assert marker in text, (
        f"{skill.relative_to(REPO_ROOT)} is missing {marker!r} — spec §3.A/§3.A.1 "
        "requires the canonical fr-goal skill (and both mirrors) to state the "
        "round-1-of-N announcement, the never-a-round-3 rule, and the record's "
        "`questions:` declaration."
    )
