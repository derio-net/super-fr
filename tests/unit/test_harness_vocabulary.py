"""`fr.harness.TOOL_VOCABULARY` and `fr.harness.prose.scan_prose` —
2026-09-18 harness-parity-matrix spec §3.C, Phase 3.

Tool-name neutrality is enforced at the canonical source rather than
translated at sync time (§3.C): the mirrors stay byte-identical, so the
only lever left is a scan over the canonical prose (and its byte-identical
copies) that fails on a harness-specific tool name named OUTSIDE an
explicitly scoped `**Harness — <topic>:**` clause.

A scoped clause is not a free pass for any mention: it is only a pass when
it actually serves more than one harness's reader — the existing,
already-load-bearing shape is `fr-goal` §5's `**Harness — dispatch:**`
paragraph, which names Claude Code's `Agent` AND Hermes's `delegate_task`
and says which is which. A clause that ends up naming only one harness's
tool is "the bug wearing a clause's shape" (spec Phase 3 dispatch prompt)
and must still fail.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

from fr.harness import TOOL_VOCABULARY
from fr.harness.prose import Violation, scan_prose

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- TOOL_VOCABULARY: no ambiguous tool name ---------------------------------


def test_tool_vocabulary_covers_the_three_harnesses_with_tools_of_their_own() -> None:
    assert TOOL_VOCABULARY["claude-code"] == frozenset(
        {
            "AskUserQuestion",
            "Agent",
            "Skill",
            "NotebookEdit",
            "WorktreeCreate",
            "WorktreeRemove",
            "MultiEdit",
        }
    )
    assert TOOL_VOCABULARY["hermes"] == frozenset({"delegate_task"})
    assert TOOL_VOCABULARY["opencode"] == frozenset({"tool.execute.before"})


def test_no_tool_name_is_claimed_by_two_harnesses() -> None:
    for (harness_a, tools_a), (harness_b, tools_b) in combinations(TOOL_VOCABULARY.items(), 2):
        overlap = tools_a & tools_b
        assert not overlap, f"{harness_a!r} and {harness_b!r} both claim {overlap!r}"


# --- scan_prose ---------------------------------------------------------------


def test_a_bare_mention_is_a_violation_naming_the_tool_and_harness() -> None:
    text = "Collect every answer into ONE AskUserQuestion call, then STOP."
    violations = scan_prose(text)
    assert violations == [Violation(harness="claude-code", tool="AskUserQuestion", line=1)]


def test_the_same_mention_inside_a_clause_naming_every_supported_harness_is_excused() -> None:
    """The bar was two harnesses when this test was written, and this fixture
    named exactly two. Review r3-i1 raised it to every SUPPORTED harness,
    because at two a clause could excuse a Claude-only tool by name-dropping
    any second harness while telling its reader nothing — so the fixture now
    names the OpenCode arm it was missing, which is also what the real fr-goal
    §5 dispatch clause had to grow."""
    text = (
        "Some neutral lead-in text.\n"
        "\n"
        "**Harness — dispatch:** Claude Code uses the AskUserQuestion tool for the\n"
        "batched interview. Hermes instead routes the same batch through\n"
        "delegate_task(goal, context), serially. OpenCode has neither — put the\n"
        "batch in your reply and end the turn.\n"
        "\n"
        "### Next section\n"
        "More neutral text.\n"
    )
    assert scan_prose(text) == []


def test_a_clause_naming_only_one_harness_is_still_a_violation() -> None:
    text = (
        "**Harness — questions:** Claude Code uses AskUserQuestion for the\n"
        "operator interview.\n"
        "\n"
        "### Next section\n"
    )
    violations = scan_prose(text)
    assert len(violations) == 1
    assert violations[0].tool == "AskUserQuestion"
    assert violations[0].harness == "claude-code"


def test_prose_naming_no_harness_tool_yields_nothing() -> None:
    text = "Put every question to the operator through your harness's question surface."
    assert scan_prose(text) == []


def test_the_real_fr_goal_dispatch_clause_passes() -> None:
    """The clause this whole rule is derived from — `fr-goal` §5's
    `**Harness — dispatch:**` paragraph — must pass. If it doesn't, the
    clause-recognition rule is wrong, not the prose."""
    text = (REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    violations = [v for v in scan_prose(text) if v.tool in {"Agent", "delegate_task"}]
    assert violations == []


# --- Review r3-c1 / r3-i1: edges the scan must survive and must not excuse. --


def test_two_blank_lines_after_a_clause_do_not_crash_the_scan() -> None:
    """`""[0]` raised IndexError, so an ordinary blank-line PAIR after a clause
    made the neutrality scan unrunnable rather than merely wrong. An empty line
    is non-indented, so it ends the clause — which is what the module docstring
    already promised."""
    text = "**Harness — q:** Claude Code, OpenCode and Hermes.\n\n\nBare: AskUserQuestion.\n"
    violations = scan_prose(text)
    assert [v.tool for v in violations] == ["AskUserQuestion"]


def test_a_clause_naming_only_two_harnesses_no_longer_excuses_a_tool() -> None:
    """The r3-i1 loophole. At the old bar of 2, a clause could excuse a
    Claude-only tool by name-dropping any second harness while telling its
    reader nothing."""
    assert scan_prose("**Harness — q:** Call AskUserQuestion. Hermes, Codex.\n"), (
        "a two-harness clause must no longer excuse a Claude-only tool"
    )


def test_a_clause_naming_every_supported_harness_excuses_its_tools() -> None:
    assert (
        scan_prose(
            "**Harness — q:** Claude Code calls `AskUserQuestion`; Hermes and\n"
            "OpenCode have none — put the batch in your reply and end the turn.\n"
        )
        == []
    )


def test_an_unsupported_harness_label_does_not_count_toward_the_bar() -> None:
    """`codex`/`copilot-cli` have no reader to serve yet, so naming them cannot
    help a clause clear the bar."""
    assert scan_prose(
        "**Harness — q:** Claude Code calls AskUserQuestion. Codex, Copilot CLI.\n"
    ), "unsupported labels must not substitute for a supported harness"
