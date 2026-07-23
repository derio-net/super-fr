"""fr-goal step 6 must be harness-aware: Claude Code dispatches the
fr-phase-executor Agent; Hermes Agent uses its native `delegate_task`. And the
skill must stay under the 120-line cap while carrying the branch."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"


def test_fr_goal_names_delegate_task_for_hermes() -> None:
    text = SKILL.read_text()
    assert "delegate_task" in text, (
        "fr-goal step 6 must tell the Hermes harness to dispatch phases via "
        "delegate_task instead of the Claude Agent tool"
    )
    assert "fr-phase-executor" in text, "the Claude Code dispatch path must remain named"


def test_fr_goal_stays_under_120_lines() -> None:
    line_count = len(SKILL.read_text().strip().split("\n"))
    assert line_count <= 120, f"fr-goal SKILL.md is {line_count} lines (cap 120)"
