"""CI tripwire: an agent told to use a skill must be able to load one.

Debug journal `2026-09-21-fr-goal-first-run-contracts`, C7. `fr-phase-executor`
was told to "implement the phase TDD via `superpowers:test-driven-development` /
`fr-execute`", and its `tools:` allowlist was `Read, Edit, Write, Bash, Grep,
Glob` — no `Skill`. The executor transcript of the first fr-goal run after the
#508 refactor shows zero skill loads across 79 records: it could not comply,
and nothing said so. Same capability-boundary class as #428 (a plan step asking
the executor to dispatch, with no tool to dispatch with), read from the other
side: there the step was unexecutable, here the agent body is.

Checked structurally, at authoring time: every canonical agent whose body names
a skill to use carries `Skill` in `tools:`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS = sorted((REPO_ROOT / "plugins" / "super-fr" / "agents").glob("*.md"))

# A skill reference is a namespaced skill id (`superpowers:x`, `super-fr:x`) or
# one of this repo's own shipped skill names used bare.
_SHIPPED_SKILLS = sorted(
    p.name for p in (REPO_ROOT / "plugins" / "super-fr" / "skills").iterdir() if p.is_dir()
)
_SKILL_REF = re.compile(
    r"\b(?:superpowers|super-fr):[a-z][a-z-]+\b|`(?:"
    + "|".join(map(re.escape, _SHIPPED_SKILLS))
    + r")`"
)


def _split(path: Path) -> tuple[dict[str, object], str]:
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(front), body


def test_there_are_agents_to_check() -> None:
    assert AGENTS, "no canonical agents found — did plugins/super-fr/agents/ move?"


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.name)
def test_an_agent_told_to_use_a_skill_is_granted_the_skill_tool(agent: Path) -> None:
    front, body = _split(agent)
    refs = sorted(set(_SKILL_REF.findall(body)))
    if not refs:
        pytest.skip(f"{agent.name} names no skill")
    tools = [t.strip() for t in str(front.get("tools", "")).split(",")]
    assert "Skill" in tools, (
        f"{agent.name} tells its reader to use {', '.join(refs)} but its `tools:` "
        f"({', '.join(tools)}) has no `Skill` — the instruction is unexecutable by "
        "construction (debug journal 2026-09-21 C7). Grant `Skill`, or stop naming skills."
    )
