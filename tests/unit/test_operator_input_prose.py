"""gh#778: the raw-input relay's prose homes must name what the engine emits.

`fr.operator_input.OPERATOR_INPUT_RULE` rides every member brief and the
handoff; fr-goal §5/§6 must tell the orchestrator to relay the brief's
`operator_input` into the executor's and the reviewer's prompts, and the
executor's agent file must carry the rule's load-bearing sentences.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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


# --- #778 reopened (take 10): the agents fetch the input THEMSELVES ----------
#
# Relaying the brief's `operator_input` is an instruction to the ORCHESTRATOR,
# and an instruction absorbed under load: take 10's run A replaced the input
# with a pointer, run B's re-dispatched reviewers got none. So the delivery
# path no longer depends on the relay — each agent's own definition runs
# `fr journal handoff` (whose output opens with the operator input) as its
# first step, on every dispatch, whatever its prompt says.

REVIEWER = REPO_ROOT / "plugins" / "super-fr" / "agents" / "fr-phase-reviewer.md"
MANIFEST = REPO_ROOT / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml"


def _first_h2_section(text: str) -> str:
    m = re.search(r"^## .*?(?=^## |\Z)", text, re.S | re.M)
    assert m, "no ## section"
    return m.group(0)


def _tools(text: str) -> set[str]:
    m = re.search(r"^tools:\s*(.+)$", text, re.M)
    assert m, "no tools: line"
    return {t.strip() for t in m.group(1).split(",")}


@pytest.mark.parametrize("agent", [AGENT, REVIEWER], ids=lambda p: p.stem)
def test_each_agent_fetches_the_input_itself_before_anything_else(agent: Path) -> None:
    text = agent.read_text()
    first = _first_h2_section(text)
    assert "fr journal handoff --scope plan" in first, (
        f"{agent.name}: its FIRST section must run `fr journal handoff` itself — "
        "the orchestrator's relay is not a delivery path (#778, take 10)"
    )
    assert "## Operator input" in first
    # The self-fetch holds even when the prompt already carries a copy: a
    # paraphrase or a pointer looks like the input and is not.
    assert "every dispatch" in first


def test_the_executor_no_longer_expects_the_input_from_its_prompt() -> None:
    text = AGENT.read_text()
    assert "read-only, in your task prompt" not in text


def test_the_phase_reviewer_can_run_the_handoff_but_not_edit() -> None:
    tools = _tools(REVIEWER.read_text())
    assert "Bash" in tools
    assert not tools & {"Edit", "Write", "NotebookEdit", "Agent", "Task"}


def test_the_reviewer_carries_the_rules_load_bearing_tokens() -> None:
    text = REVIEWER.read_text()
    assert "The spec governs" in text
    assert "`input-`" in text


def test_review_phase_names_the_phase_reviewer_agent() -> None:
    from fr.workflow.model import parse_manifest

    manifest = parse_manifest(MANIFEST.read_text())
    members = {s.id: s for top in manifest.steps for s in (top, *top.steps)}
    assert members["review-phase"].agent == "super-fr:fr-phase-reviewer"


def test_fr_goal_dispatches_the_phase_reviewer() -> None:
    assert "fr-phase-reviewer" in _section(FR_GOAL.read_text(), "6. review-phase")
