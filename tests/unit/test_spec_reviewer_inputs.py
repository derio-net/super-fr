"""gh#699: what the `spec-review` reviewer is handed, and what it is not.

A reviewer dispatched at `spec-review` once went looking for the brainstorm
step's record and filed its absence as a finding. That absence is by design:
a step record is transient (spec 2026-09-25 §5.C) — `brainstorm`'s is applied
to the spec journal and deleted by the resolve that applies it, before
`spec-review` can open, and `spec-review`'s own record is the YAML the
reviewer returns. So the reviewer's inputs are the spec and the spec journal,
and both the orchestrator's dispatch instructions and the agent's own Inputs
section must say that no step record is one of them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "plugins/super-fr/agents/fr-spec-reviewer.md"
SKILL = ROOT / "plugins/super-fr/skills/fr-goal/SKILL.md"


def _squash(text: str) -> str:
    return " ".join(text.split())


def test_the_reviewer_agent_says_no_step_record_is_an_input() -> None:
    text = _squash(AGENT.read_text())
    inputs = text[text.index("## Inputs") : text.index("## What you check")]
    assert "No step record is an input" in inputs
    assert "deleted when `brainstorm` resolved" in inputs
    assert "never a finding" in inputs


def test_fr_goal_dispatches_the_reviewer_with_the_spec_and_journal_only() -> None:
    text = _squash(SKILL.read_text())
    assert "with the spec and spec-journal paths — only those: no step record is an input" in text
