"""fr-plan never instructs a planner to write `tier` — break 2 of the
2026-09-20 phases-file-tier-reaches-dispatch spec (Background, "Three breaks,
not one"). fr-goal §3 already asserts "fr-plan tags each phase a `tier`";
until this test is green, that assertion is aspirational — the string `tier`
does not appear in `fr-plan/SKILL.md` at all.

Modelled on `test_fr_goal_dispatch_prose.py`: assertions pin MEANING that
survives rewording (a rule exists, names the vocabulary, distinguishes
agentic from manual), not an exact sentence, so ordinary editing does not
fail this test while a silent removal of the rule does.
"""

from __future__ import annotations

from pathlib import Path

from fr.types import PHASE_TIERS

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-plan" / "SKILL.md"
MIRROR = REPO_ROOT / ".opencode" / "skills" / "fr-plan" / "SKILL.md"


def test_the_canonical_skill_instructs_a_tier_on_agentic_phases() -> None:
    text = CANONICAL.read_text(encoding="utf-8")
    assert "tier" in text, (
        "fr-plan/SKILL.md never mentions `tier` — fr-goal §3's claim that "
        "'fr-plan tags each phase a tier' is currently untrue"
    )
    # Every tier name the model actually accepts (`fr.types.PHASE_TIERS`),
    # not a restated literal list — so a fourth tier added to the model
    # fails this test until the prose is updated to match.
    for tier in PHASE_TIERS:
        assert tier in text, f"fr-plan/SKILL.md never names the tier {tier!r}"
    assert "manual" in text.lower(), (
        "the rule must distinguish agentic phases (which take a tier) from "
        "manual phases (which don't — they're never dispatched to a model)"
    )


def test_the_opencode_mirror_carries_the_same_clause() -> None:
    canonical = CANONICAL.read_text(encoding="utf-8")
    mirror = MIRROR.read_text(encoding="utf-8")
    assert mirror == canonical, (
        "the opencode mirror has drifted from the canonical fr-plan skill — "
        "regenerate with `scripts/sync-opencode.py`, never hand-edit the mirror"
    )
    for tier in PHASE_TIERS:
        assert tier in mirror, f".opencode/skills/fr-plan/SKILL.md never names the tier {tier!r}"
