"""R15 (spec 2026-11-04-repo-feature-settings): every shipped skill or agent that writes,
nags about or renders a configurable feature reads the effective settings."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READERS = (
    "plugins/super-fr/skills/fr-brainstorming/SKILL.md",
    "plugins/super-fr/skills/fr-acceptance/SKILL.md",
    "plugins/super-fr/skills/fr-goal/SKILL.md",
    "plugins/super-fr/skills/fr-plan/SKILL.md",
    "plugins/super-fr/skills/fr-progress/SKILL.md",
    "plugins/super-fr/skills/fr-devops-gate/SKILL.md",
    "plugins/super-fr/agents/fr-spec-reviewer.md",
)


@pytest.mark.parametrize("rel", READERS)
def test_the_skill_reads_the_effective_settings(rel: str) -> None:
    text = " ".join((ROOT / rel).read_text().split())
    assert "fr settings show --json" in text, rel


def test_the_spec_reviewer_raises_nothing_a_setting_turned_off() -> None:
    text = " ".join((ROOT / READERS[-1]).read_text().split())
    assert "Under `artifacts.test_plan: off` a missing Test Plan is not a finding" in text
    assert "under `artifacts.acceptance: off` absent or unlinked rows are not a finding" in text
