"""fr-brainstorming tells spec authors to write the `| ID | Requirement |` table
(spec 2026-11-26-spec-requirements-table R8)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins" / "super-fr" / "skills"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


def test_fr_brainstorming_names_the_table_its_stamp_and_the_escape() -> None:
    text = _skill("fr-brainstorming")
    assert "| ID | Requirement |" in text
    assert "fr_schema: 2" in text
    assert "\\|" in text
    assert "R1. <text>" not in text


@pytest.mark.parametrize("name", ["fr-acceptance", "fr-plan"])
def test_the_other_skills_call_it_a_table(name: str) -> None:
    text = _skill(name)
    assert "Requirements table" in text or "`## Requirements` table" in text
    assert "Requirements list" not in text and "`## Requirements` list" not in text
