"""gh#761: standalone fr-brainstorming opens its operator gate BEFORE asking.

`brainstorm` is `gate: operator`; the gate opens (blocks) only on `fr run
advance`, and `resolve` counts answered questions since it blocked. A skill
that starts the cursor and then asks has every answer land before the gate,
invisible to `resolve`. The skill must say to start as `standalone` and to
advance before the first question.
"""

from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills/fr-brainstorming/SKILL.md"


def test_standalone_start_declares_its_driver_and_advances_before_asking() -> None:
    text = " ".join(SKILL.read_text().split())
    start = text.index("fr run start fr-goal --branch <feature-branch> --driver standalone")
    advance = text.index("**before the first question**, run `fr run advance <run-id>`")
    assert start < advance
    assert "Never ask while the gate is closed." in text
