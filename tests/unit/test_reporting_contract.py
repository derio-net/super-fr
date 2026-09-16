"""Spec 2026-09-14-ste-output-tone §5.A-B: skills ask for fewer, shorter reports."""

from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills"
CONTRACT = "Each update is the result in 1–3 lines, then the next step."
TABLE = "`id | claim | level | defense`"


def _skill(name: str) -> str:
    return " ".join((SKILLS / name / "SKILL.md").read_text().split())


@pytest.mark.parametrize("name", ["fr-goal", "fr-debugging"])
def test_the_reporting_contract_is_in_the_skill(name: str) -> None:
    assert CONTRACT in _skill(name)


def test_fr_goal_no_longer_asks_to_say_what_you_tried() -> None:
    assert "say what you tried" not in _skill("fr-goal")


@pytest.mark.parametrize("name", ["fr-brainstorming", "fr-acceptance"])
def test_new_rows_are_presented_as_one_table(name: str) -> None:
    assert TABLE in _skill(name)


def test_brainstorming_no_longer_asks_for_a_defense_each() -> None:
    assert "with a one-line defense each" not in _skill("fr-brainstorming")
