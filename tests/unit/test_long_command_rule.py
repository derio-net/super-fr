"""gh#582: the long-command rule has two homes, and they must agree.

`fr.harness.long_commands.LONG_COMMAND_RULES` is what `fr run advance` puts
in every phase-member brief (the executor reads it when it acts); the
executor agent's `**Harness — long commands:**` clause is the same rule in
its system prompt. The #564 smoke showed the clause alone is not enough, and
two copies that drift would be worse than one. So each harness's load-bearing
token must appear in both, and fr-goal must tell the orchestrator to relay the
brief's rule rather than paraphrase the task around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.harness.long_commands import (
    LONG_COMMAND_RULES,
    NEUTRAL_LONG_COMMAND_RULE,
    long_command_rule,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT = REPO_ROOT / "plugins" / "super-fr" / "agents" / "fr-phase-executor.md"
FR_GOAL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"

# The token without which a reader on that harness does the wrong thing.
LOAD_BEARING = {
    "claude-code": "run_in_background",
    "opencode": "600000",
    "hermes": "background=true",
}


def _agent_clause() -> str:
    text = AGENT.read_text()
    start = text.index("**Harness — long commands:**")
    end = text.find("\n\n", start)
    return text[start : end if end != -1 else None]


def test_every_supported_harness_has_a_rule() -> None:
    assert set(LONG_COMMAND_RULES) == set(LOAD_BEARING)


@pytest.mark.parametrize("harness", sorted(LOAD_BEARING))
def test_brief_rule_and_agent_clause_share_the_load_bearing_token(harness: str) -> None:
    token = LOAD_BEARING[harness]
    assert token in LONG_COMMAND_RULES[harness]
    assert token in _agent_clause(), f"agent clause lost {token!r} for {harness}"


def test_unknown_harness_gets_the_neutral_rule() -> None:
    assert long_command_rule(None) == NEUTRAL_LONG_COMMAND_RULE
    assert long_command_rule("codex") == NEUTRAL_LONG_COMMAND_RULE
    assert "2 minutes" in NEUTRAL_LONG_COMMAND_RULE


def test_fr_goal_tells_the_orchestrator_to_relay_the_rule() -> None:
    assert "long_commands" in FR_GOAL.read_text(), (
        "fr-goal §5 must tell the orchestrator to put the brief's `long_commands` "
        "rule into the executor's task prompt verbatim (gh#582)"
    )
