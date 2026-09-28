"""gh#778: the raw-input relay's prose homes must name what the engine emits.

`fr.operator_input.OPERATOR_INPUT_RULE` rides every member brief and the
handoff; fr-goal §5/§6 must tell the orchestrator to relay the brief's
`operator_input` into the executor's and the reviewer's prompts, and the
executor's agent file must carry the rule's load-bearing sentences.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.operator_input import OPERATOR_INPUT_RULE

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT = REPO_ROOT / "plugins" / "super-fr" / "agents" / "fr-phase-executor.md"
FR_GOAL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"


def _section(text: str, prefix: str) -> str:
    m = re.search(rf"^### {re.escape(prefix)}.*?(?=^### |\Z)", text, re.S | re.M)
    assert m, f"no section {prefix!r}"
    return m.group(0)


def test_fr_goal_relays_operator_input_into_implement_and_review() -> None:
    text = FR_GOAL.read_text()
    assert "operator_input" in _section(text, "5. implement")
    assert "operator_input" in _section(text, "6. review-phase")


def test_agent_file_carries_the_rules_load_bearing_tokens() -> None:
    text = AGENT.read_text()
    assert "The spec governs" in OPERATOR_INPUT_RULE and "`input-`" in OPERATOR_INPUT_RULE
    assert "The spec governs" in text
    assert "`input-`" in text
