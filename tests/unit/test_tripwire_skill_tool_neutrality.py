"""CI tripwire: no skill, agent or rule — canonical or generated mirror —
names a harness-specific tool or argument outside an explicitly scoped
`**Harness — <topic>:**` clause. 2026-09-18 harness-parity-matrix spec §3.C
(skills), widened 2026-09-21 (#497: agents) and 2026-09-22
(harness-argument-neutrality: rules, and arguments via ARGUMENT_VOCABULARY).

This is the closer for #436's class B: `fr-goal` §1 and `fr-init` §2 both
specified their operator touchpoint as Claude Code's `AskUserQuestion`,
which both sync scripts copy byte-for-byte into `.opencode/skills/` and
`.hermes/skills/fr/` — six occurrences of a Claude-only tool name shipped
to every harness, not the four #436 estimated. Fixed at the canonical
source (spec §3.C rejects translating at sync time); this test is what
pins the fix and would have failed loudly before it, over the SAME three
trees `test_tripwire_opencode_skills_sync` /
`test_tripwire_hermes_skills_sync` already assert are byte-identical to
canonical.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.harness.prose import scan_prose

REPO_ROOT = Path(__file__).resolve().parents[2]

_SKILL_TREES = {
    "canonical": REPO_ROOT / "plugins" / "super-fr" / "skills",
    "opencode-mirror": REPO_ROOT / ".opencode" / "skills",
    "hermes-mirror": REPO_ROOT / ".hermes" / "skills" / "fr",
}

# 2026-09-21 agent-body-tool-neutrality spec §2.3: an agent body is prose a
# reader on any harness follows, exactly like a skill, and it was outside
# every scan — `.opencode/agent/` is now generated from the canonical and
# `test_opencode_agent_mirror.py` asserts the body stays byte-identical, so
# Claude-only prose is *guaranteed* to reach every OpenCode agent file.
# Hermes has no agent mirror (`delegate_task` takes no agent file), hence two
# trees, not three. Flat `*.md`, not `*/SKILL.md`.
_AGENT_TREES = {
    "canonical-agents": REPO_ROOT / "plugins" / "super-fr" / "agents",
    "opencode-agent-mirror": REPO_ROOT / ".opencode" / "agent",
}

# 2026-09-22 harness-argument-neutrality spec §3.C: rules are the third family
# a reader on any harness follows. The shipped rules are copied into
# `.opencode/instructions/` and `.hermes/SOUL.d/` by the two sync scripts, and
# `.claude/rules/` holds the repo-local rules (sources in their own right, plus
# the hand-maintained `fr-isolation-required` mirror) that OpenCode loads via
# `opencode.json`'s `instructions`. Flat `*.md`, like agents.
_RULE_TREES = {
    "canonical-rules": REPO_ROOT / "plugins" / "super-fr" / "rules",
    "repo-local-rules": REPO_ROOT / ".claude" / "rules",
    "opencode-instructions-mirror": REPO_ROOT / ".opencode" / "instructions",
    "hermes-soul-mirror": REPO_ROOT / ".hermes" / "SOUL.d",
}


def _all_skill_files() -> list[Path]:
    files: list[Path] = []
    for tree in _SKILL_TREES.values():
        files.extend(sorted(tree.glob("*/SKILL.md")))
    return files


def _all_agent_files() -> list[Path]:
    files: list[Path] = []
    for tree in _AGENT_TREES.values():
        files.extend(sorted(tree.glob("*.md")))
    return files


def _all_rule_files() -> list[Path]:
    files: list[Path] = []
    for tree in _RULE_TREES.values():
        files.extend(sorted(tree.glob("*.md")))
    return files


@pytest.mark.parametrize("tree_name", sorted(_SKILL_TREES))
def test_tree_is_not_empty(tree_name: str) -> None:
    assert sorted(_SKILL_TREES[tree_name].glob("*/SKILL.md")), (
        f"no SKILL.md found under {_SKILL_TREES[tree_name]} — did the layout move?"
    )


@pytest.mark.parametrize("tree_name", sorted(_AGENT_TREES))
def test_agent_tree_is_not_empty(tree_name: str) -> None:
    assert sorted(_AGENT_TREES[tree_name].glob("*.md")), (
        f"no agent file found under {_AGENT_TREES[tree_name]} — did the layout move?"
    )


@pytest.mark.parametrize("tree_name", sorted(_RULE_TREES))
def test_rule_tree_is_not_empty(tree_name: str) -> None:
    assert sorted(_RULE_TREES[tree_name].glob("*.md")), (
        f"no rule file found under {_RULE_TREES[tree_name]} — did the layout move?"
    )


def _violations(paths: list[Path]) -> set[str]:
    return {
        f"{path.relative_to(REPO_ROOT)}:{v.line}:{v.tool}"
        for path in paths
        for v in scan_prose(path.read_text(encoding="utf-8"))
    }


def test_no_skill_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    found = sorted(_violations(_all_skill_files()))
    assert found == [], (
        f"{found}\n\n"
        "Name the operator touchpoint neutrally (spec §3.C) — the concrete tool "
        "belongs in a `**Harness — <topic>:**` clause naming every harness it applies to."
    )


def test_no_agent_body_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    found = sorted(_violations(_all_agent_files()))
    assert found == [], (
        f"{found}\n\n"
        "An agent body is read on every harness that can dispatch it — say what "
        "each reader should do inside a `**Harness — <topic>:**` clause, and keep the "
        "frontmatter `description` (which cannot sit in a clause) neutral."
    )


def test_no_rule_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    found = sorted(_violations(_all_rule_files()))
    assert found == [], (
        f"{found}\n\n"
        "A rule is loaded on every harness (`.opencode/instructions/`, "
        "`.hermes/SOUL.d/`) — say what each reader should do inside a "
        "`**Harness — <topic>:**` clause naming Claude Code, OpenCode and Hermes."
    )
