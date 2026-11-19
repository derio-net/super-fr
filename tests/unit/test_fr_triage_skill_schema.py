"""Skill prose states what the engine does (spec 2026-11-19 R7, R8, R9)."""

from __future__ import annotations

import re
from pathlib import Path

from fr.triage.model import JUDGEMENTS_SCHEMA

SKILLS = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


def test_the_triage_skill_states_the_judgements_schema_the_engine_writes() -> None:
    found = re.findall(r"`?schema: (\d+)`?", _skill("fr-triage"))
    assert found, "fr-triage SKILL.md names no judgements `schema: <n>`"
    assert {int(n) for n in found} == {JUDGEMENTS_SCHEMA}


def test_the_acceptance_skill_does_not_say_a_live_row_nags_whatever_its_status() -> None:
    text = " ".join(_skill("fr-acceptance").split())
    assert "whatever its status" not in text
    assert "`fr acceptance status` lists it only while it is debt" in text


def test_the_progress_skill_does_not_group_status_with_the_yes_commands() -> None:
    text = _skill("fr-progress")
    assert "`fr status`/`fr repair`/`fr migrate v1-to-v2` preview by default" not in text
    assert "has no `--yes`" in text
