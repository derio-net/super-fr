"""Spec 2026-09-14-ste-output-tone §5.A-B: skills ask for fewer, shorter reports."""

from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills"
CONTRACT = "Each update is the result in 1–3 lines, then the next step."
# Brevity alone invites compressed, jargon-dense updates, and the clarity
# rules of the opt-in style never reach an operator who does not select it.
CLARITY = (
    'Short means split, not packed: plain words, name what an id refers to, keep the "because".'
)
# Each skill states the table form in its own sentence, so a bare token match
# cannot pass on text that says the opposite (phase 8 review, M5).
TABLES = {
    "fr-brainstorming": "presenting the rows as one table — `id | claim | level | defense`",
    "fr-acceptance": "as one table row each (`id | claim | level | defense`)",
    "fr-goal": "as one table (`id | claim | level | defense`)",
}


def _skill(name: str) -> str:
    return " ".join((SKILLS / name / "SKILL.md").read_text().split())


@pytest.mark.parametrize("name", ["fr-goal", "fr-debugging"])
def test_the_reporting_contract_is_in_the_skill(name: str) -> None:
    assert CONTRACT in _skill(name)


@pytest.mark.parametrize("name", ["fr-goal", "fr-debugging"])
def test_short_updates_stay_plain(name: str) -> None:
    assert CLARITY in _skill(name)


def test_fr_goal_no_longer_asks_to_say_what_you_tried() -> None:
    assert "say what you tried" not in _skill("fr-goal")


@pytest.mark.parametrize("name", sorted(TABLES))
def test_new_rows_are_presented_as_one_table(name: str) -> None:
    assert TABLES[name] in _skill(name)


@pytest.mark.parametrize("name", ["fr-brainstorming", "fr-acceptance", "fr-goal"])
def test_no_skill_still_asks_for_a_defense_per_row(name: str) -> None:
    assert "with a one-line defense" not in _skill(name)
    assert "each with a one-line defense" not in _skill(name)
