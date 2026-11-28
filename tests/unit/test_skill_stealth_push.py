"""Under stealth no code reaches the target before `deliver`, and every code push asks
(spec 2026-11-28-alacarte-settings R10). The canonical skills say so; the mirror tripwires
carry the text to the OpenCode and Hermes copies."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

SKILLS = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "skills"


def _text(skill: str) -> str:
    return " ".join((SKILLS / skill / "SKILL.md").read_text().split()).lower()


@pytest.mark.parametrize(
    "phrase",
    [
        "Under stealth no executor pushes",
        "no phase uses `tests: ci` as its own evidence",
        "The first code push is at `deliver`'s open, where `fr push` asks",
        "a cross-host `--resume` before `deliver` does not carry",
        "On a harness whose transcript fr cannot read, a stealth run cannot push or open its "
        "PR through fr and stops at `deliver`'s open",
        "Under stealth, never brief `tests: ci`",
        "Under stealth, do not push here",
    ],
)
def test_fr_goal_states_the_stealth_push_rule(phrase: str) -> None:
    assert phrase.lower() in _text("fr-goal")


@pytest.mark.parametrize(
    "phrase",
    [
        "Under stealth every code push asks",
        "On a harness whose transcript fr cannot read, a stealth session cannot push or open "
        "its PR through fr",
    ],
)
def test_fr_debugging_states_the_stealth_push_rule(phrase: str) -> None:
    assert phrase.lower() in _text("fr-debugging")
