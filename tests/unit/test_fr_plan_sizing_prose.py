"""fr-plan and fr-goal size phases to the spec's asks (spec
2026-09-28-phase-sizing-design.md §E, Test Plan item 6; super-fr#745, #760).

Modelled on `test_fr_plan_tier_prose.py`: the assertions pin MEANING that
survives rewording (the rule exists, names its vocabulary), not one sentence.
The mirrors are covered by the existing sync tripwires.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_PLAN = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-plan" / "SKILL.md"
FR_GOAL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"

SIZING_SENTENCE = "one agentic phase per independently reviewable ask"
WAIVERS = ("tier:", "risk-first:", "review-size:")


def _flat(path: Path) -> str:
    """The file with whitespace runs collapsed, so a wrapped line still matches."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _goal_section_3() -> str:
    text = _flat(FR_GOAL)
    start = text.index("### 3. plan")
    return text[start : text.index("### 4.", start)]


def test_fr_plan_no_longer_asks_for_four_to_six_phases() -> None:
    text = _flat(FR_PLAN)
    assert "Prefer 4–6 phases" not in text
    assert "4–6 phases" not in text and "4-6 phases" not in text


def test_fr_plan_states_one_phase_per_ask() -> None:
    assert SIZING_SENTENCE in _flat(FR_PLAN).lower()


def test_fr_plan_tells_the_planner_to_record_an_ask_split_for_each_later_phase() -> None:
    text = _flat(FR_PLAN)
    assert "phase-split-<plan>-p<N>" in text
    assert "`ask:`" in text
    for token in WAIVERS:
        assert f"`{token}`" in text, f"fr-plan never names the {token} split reason"


def test_fr_plan_makes_a_verification_step_a_test_plan_line() -> None:
    text = _flat(FR_PLAN)
    assert "Test Plan line" in text
    assert "verify: live" in text


def test_fr_plan_folds_the_skeleton_into_the_first_asks_phase() -> None:
    assert "the skeleton is the first ask's phase" in _flat(FR_PLAN).lower()


def test_fr_plan_keeps_steps_bite_sized_within_a_one_phase_plan() -> None:
    text = _flat(FR_PLAN).lower()
    assert "bite-sized steps" in text
    assert "spec design section" in text


def test_fr_goal_section_3_carries_the_same_sizing_rule() -> None:
    section = _goal_section_3()
    assert SIZING_SENTENCE in section.lower()
    assert "phase-split-<plan>-p<N>" in section
    assert "Test Plan line" in section


def test_r5_the_split_command_names_the_spec_journal_slug() -> None:
    """Review r5: `--slug` takes the spec's JOURNAL slug (the stem without
    `-design`), which `<spec-slug>` did not say."""
    for text in (_flat(FR_PLAN), _goal_section_3()):
        assert "--slug <spec-slug>" not in text
        assert "--slug <spec-journal-slug>" in text
        assert "without `-design`" in text


def test_r1_the_skills_say_how_to_supersede_a_split_decision() -> None:
    for text in (_flat(FR_PLAN), _goal_section_3()):
        assert "phase-split-<plan>-p<N>-<k>" in text
