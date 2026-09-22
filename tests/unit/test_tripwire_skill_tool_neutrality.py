"""CI tripwire: no `SKILL.md` — canonical or mirror — names a harness-
specific tool outside an explicitly scoped `**Harness — <topic>:**`
clause. 2026-09-18 harness-parity-matrix spec §3.C, Phase 3.

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

# Claude Code's dispatch-isolation flag, deliberately NOT in TOOL_VOCABULARY
# (spec §2.4/§3): registering it globally would fire on `fr-goal` §2's
# legitimate un-scoped cross-repo mention, a separate sentence out of scope
# here. It IS harness-specific in an agent body, so the agent trees pass it
# to `scan_prose` themselves.
_AGENT_EXTRA_TOOLS = {'isolation: "worktree"': "claude-code"}


def _without_tools_allowlist(text: str) -> str:
    """`text` with the frontmatter `tools:` line blanked (line count kept, so
    reported line numbers stay true).

    That one line is Claude Code's own allowlist syntax, not prose any reader
    follows: `scripts/sync-opencode.py` translates it into OpenCode's
    `permission:` map and the mirrors carry no `tools:` line at all. It also
    cannot sit inside a `**Harness — …:**` clause, so scanning it made any
    agent granted a Claude Code tool (`Skill`, `Agent`) unshippable — found
    when #536 granted `fr-phase-executor` the `Skill` tool its body tells it to
    use (review of #532, M3). Only the frontmatter line is exempt: the same
    name in the description or the body is still prose and still scanned."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                break
            if lines[i].startswith("tools:"):
                lines[i] = ""
    return "\n".join(lines)


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


def test_no_skill_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    messages = []
    for path in _all_skill_files():
        text = path.read_text(encoding="utf-8")
        for violation in scan_prose(text):
            messages.append(
                f"{path.relative_to(REPO_ROOT)}:{violation.line}: "
                f"names {violation.tool!r} ({violation.harness}) outside a scoped clause "
                "naming more than one harness"
            )
    assert not messages, "\n".join(messages) + (
        "\n\nName the operator touchpoint neutrally (spec §3.C) — the concrete tool "
        "belongs in a `**Harness — <topic>:**` clause naming every harness it applies to."
    )


def test_no_agent_body_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    messages = []
    for path in _all_agent_files():
        text = _without_tools_allowlist(path.read_text(encoding="utf-8"))
        for violation in scan_prose(text, extra_tools=_AGENT_EXTRA_TOOLS):
            messages.append(
                f"{path.relative_to(REPO_ROOT)}:{violation.line}: "
                f"names {violation.tool!r} ({violation.harness}) outside a scoped clause "
                "naming more than one harness"
            )
    assert not messages, "\n".join(messages) + (
        "\n\nAn agent body is read on every harness that can dispatch it — say what "
        "each reader should do inside a `**Harness — <topic>:**` clause, and keep the "
        "frontmatter `description` (which cannot sit in a clause) neutral."
    )


def test_only_the_frontmatter_tools_line_is_exempt() -> None:
    """The exemption must not become a hole: `Skill` in the `tools:` allowlist
    passes, the same name in the description or the body is still caught."""
    agent = (
        "---\nname: x\ndescription: >\n  Uses the Skill tool.\n"
        "tools: Read, Skill\n---\n# x\n\nLoad it with the Skill tool.\n"
    )
    flagged = [v.line for v in scan_prose(_without_tools_allowlist(agent))]
    assert flagged == [4, 9], flagged
