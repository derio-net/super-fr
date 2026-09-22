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


# Phase 2 of the 2026-09-22 harness-argument-neutrality plan taught `scan_prose`
# arguments; the prose they flag is phase 3's to scope. Review p2r-1: these were
# `xfail(strict=True)`, which only fails once EVERY violation is gone — a
# canonical fixed but one mirror not re-synced, or a brand-new violation, stayed
# XFAIL, and a bare xfail swallowed exceptions too. Each test now asserts the
# violation set EQUALS what phase 3 still owes, so any change at all goes red;
# phase 3 empties both sets.
_SKILLS_PHASE_3_OWES = {
    'plugins/super-fr/skills/fr-goal/SKILL.md:59:isolation: "worktree"',
    '.opencode/skills/fr-goal/SKILL.md:59:isolation: "worktree"',
    '.hermes/skills/fr/fr-goal/SKILL.md:59:isolation: "worktree"',
}
_AGENTS_PHASE_3_OWES = {
    "plugins/super-fr/agents/fr-phase-executor.md:121:run_in_background",
    ".opencode/agent/fr-phase-executor.md:116:run_in_background",
    ".opencode/agent/fr-phase-executor-mechanical.md:116:run_in_background",
    ".opencode/agent/fr-phase-executor-standard.md:116:run_in_background",
    ".opencode/agent/fr-phase-executor-hard.md:116:run_in_background",
}


def _violations(paths: list[Path]) -> set[str]:
    return {
        f"{path.relative_to(REPO_ROOT)}:{v.line}:{v.tool}"
        for path in paths
        for v in scan_prose(path.read_text(encoding="utf-8"))
    }


def test_no_skill_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    found = _violations(_all_skill_files())
    assert found == _SKILLS_PHASE_3_OWES, (
        f"new: {sorted(found - _SKILLS_PHASE_3_OWES)}\n"
        f"now fixed (shrink _SKILLS_PHASE_3_OWES): {sorted(_SKILLS_PHASE_3_OWES - found)}\n\n"
        "Name the operator touchpoint neutrally (spec §3.C) — the concrete tool "
        "belongs in a `**Harness — <topic>:**` clause naming every harness it applies to."
    )


def test_no_agent_body_names_a_harness_specific_tool_outside_a_scoped_clause() -> None:
    found = _violations(_all_agent_files())
    assert found == _AGENTS_PHASE_3_OWES, (
        f"new: {sorted(found - _AGENTS_PHASE_3_OWES)}\n"
        f"now fixed (shrink _AGENTS_PHASE_3_OWES): {sorted(_AGENTS_PHASE_3_OWES - found)}\n\n"
        "An agent body is read on every harness that can dispatch it — say what "
        "each reader should do inside a `**Harness — <topic>:**` clause, and keep the "
        "frontmatter `description` (which cannot sit in a clause) neutral."
    )
