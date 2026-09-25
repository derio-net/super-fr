"""The fr-audit skill ships, thin, over the `fr usage` engine (plan
2026-09-25-lean-cost-aware-process P1.T5; spec §5.A.6, Test Plan item 14).

Generic shape checks (frontmatter, under 120 lines, tool neutrality) already
run over every `plugins/*/skills/fr-*` by glob; these pin what is specific.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.commands import skills_cmd

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "plugins" / "super-fr" / "skills" / "fr-audit" / "SKILL.md"


def test_the_skill_exists_and_is_thin() -> None:
    text = SKILL.read_text()
    assert text.startswith("---\nname: fr-audit\n")
    assert len(text.splitlines()) < 120


@pytest.mark.parametrize(
    "needle",
    [
        "fr usage collect",
        "fr usage report",
        "--format html",
        "turns",  # how to read the split: turns are the cost unit
        "future",  # the future-state half is authored from a spec, not measured
    ],
)
def test_the_skill_names_its_engine_and_reading(needle: str) -> None:
    assert needle in SKILL.read_text()


def test_both_harness_mirrors_carry_it() -> None:
    assert (REPO / ".opencode" / "skills" / "fr-audit" / "SKILL.md").is_file()
    assert (REPO / ".hermes" / "skills" / "fr" / "fr-audit" / "SKILL.md").is_file()


def test_fr_skills_lists_fr_audit_with_its_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    skills_cmd.skills()
    out = capsys.readouterr().out
    assert re.search(r"^\s*fr-audit\b", out, re.MULTILINE), out
    assert "fr usage {collect,report}" in out
