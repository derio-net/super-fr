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


def _all_skill_files() -> list[Path]:
    files: list[Path] = []
    for tree in _SKILL_TREES.values():
        files.extend(sorted(tree.glob("*/SKILL.md")))
    return files


@pytest.mark.parametrize("tree_name", sorted(_SKILL_TREES))
def test_tree_is_not_empty(tree_name: str) -> None:
    assert sorted(_SKILL_TREES[tree_name].glob("*/SKILL.md")), (
        f"no SKILL.md found under {_SKILL_TREES[tree_name]} — did the layout move?"
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
