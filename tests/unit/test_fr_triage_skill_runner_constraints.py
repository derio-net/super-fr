"""The fr-triage skill states the runner constraint and the session-upkeep settings
(driver-sessions §E, R9). Read from the canonical source, never a mirror."""

from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills/fr-triage/SKILL.md"
HEADING = "Runner constraints and session upkeep"


def _paragraph() -> str:
    text = SKILL.read_text(encoding="utf-8")
    assert HEADING in text, f"the skill has no {HEADING!r} paragraph"
    return text.split(HEADING, 1)[1].split("\n## ", 1)[0]


def test_the_skill_states_the_herdr_only_rule() -> None:
    body = _paragraph()
    assert "herdr pane" in body and "fr triage batch drive" in body and "dispatch" in body


def test_the_skill_names_the_session_upkeep_settings() -> None:
    body = _paragraph()
    for name in ("post_merge_restart", "idle_session_minutes", "fr-herdr restart-idle"):
        assert name in body, name
