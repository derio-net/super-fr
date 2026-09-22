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

import pytest
from fr.harness import ARGUMENT_VOCABULARY, HARNESSES, TOOL_VOCABULARY
from fr.harness.model import HarnessError
from fr.harness.prose import Violation, require_every_harness, scan_prose

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
    assert TOOL_VOCABULARY["opencode"] == frozenset({"tool.execute.before", "task tool"})


def test_opencodes_dispatch_tool_is_in_the_vocabulary() -> None:
    """fr-goal §5 now names OpenCode's dispatch tool (spec §3.D), so the
    vocabulary has to know it — otherwise the mention rides byte-for-byte into
    all three skill trees with nothing checking it stayed inside a scoped
    clause.

    Registered as the two-word prose form, NOT the bare tool id `task`. Spec
    §3.D asserted "no bare `task` token exists in any of the three skill
    trees today"; that is false and was false on `origin/main` — fr-execute
    §64 and fr-plan §§37/66/68 use `task` as fr's own plan noun (phase / task
    / step). Registering the bare id would fire on the repo's own domain
    vocabulary, in twelve places at once and in every future sentence about a
    plan task, which is a broken tripwire rather than a strict one. The
    trade is stated in `TOOL_VOCABULARY`'s comment: a mention written as a
    bare `task` outside a clause is NOT caught.

    Still lowercase, and `scan_prose` is case-sensitive (`re.escape`, no
    `IGNORECASE`), so this cannot collide with Claude Code's `Agent` nor with
    a capitalised `Task`; the neighbouring
    `test_no_tool_name_is_claimed_by_two_harnesses` guards the
    two-harnesses-one-name case for free."""
    assert "task tool" in TOOL_VOCABULARY["opencode"]
    assert "task" not in TOOL_VOCABULARY["opencode"], (
        "the bare tool id fires on fr's own plan noun — see the docstring"
    )


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


# --- `extra_tools`: a caller-local name, deliberately NOT in the vocabulary. --


def test_an_extra_tool_is_excused_by_a_scoped_clause_like_any_other() -> None:
    text = (
        '**Harness — dispatch isolation:** Claude Code can pass `isolation: "worktree"`;\n'
        "OpenCode and Hermes have no such argument, so the case cannot arise.\n"
    )
    assert scan_prose(text, extra_tools={'isolation: "worktree"': "claude-code"}) == []


def test_extra_tools_does_not_mutate_the_global_vocabulary() -> None:
    """A per-call mapping that leaked into `TOOL_VOCABULARY` would make the
    skill trees start failing on the agent tree's private name."""
    before = {harness: set(tools) for harness, tools in TOOL_VOCABULARY.items()}
    scan_prose("nothing here", extra_tools={"WhateverTool": "claude-code"})
    assert {harness: set(tools) for harness, tools in TOOL_VOCABULARY.items()} == before


def test_an_unsupported_harness_label_does_not_count_toward_the_bar() -> None:
    """`codex`/`copilot-cli` have no reader to serve yet, so naming them cannot
    help a clause clear the bar."""
    assert scan_prose(
        "**Harness — q:** Claude Code calls AskUserQuestion. Codex, Copilot CLI.\n"
    ), "unsupported labels must not substitute for a supported harness"


# --- ARGUMENT_VOCABULARY: harness-specific arguments (spec §3.A) ------------


def test_argument_vocabulary_is_keyed_by_exactly_the_harnesses() -> None:
    """2026-09-22 harness-argument-neutrality spec §3.A. Same closed-world
    rule as `TOOL_VOCABULARY`: every member of `HARNESSES` gets a key, none
    extra — a harness with no arguments of its own maps to an empty dict
    rather than a missing key. Asserts the KEYS only; the populated values
    are pinned by the table test below."""
    assert set(ARGUMENT_VOCABULARY) == set(HARNESSES)


def test_argument_vocabulary_is_exactly_the_spec_table() -> None:
    """Spec §3.A's table, verbatim — name and pattern. OpenCode's `timeout`
    is deliberately absent (ordinary English; stated as a limit)."""
    patterns = {
        harness: {name: pattern.pattern for name, pattern in arguments.items()}
        for harness, arguments in ARGUMENT_VOCABULARY.items()
    }
    assert patterns == {
        "claude-code": {
            'isolation: "worktree"': r"""isolation\s*[:=]\s*["']?worktree\b""",
            "run_in_background": r"\brun_in_background\b",
        },
        "hermes": {
            "background=true": r"\bbackground\s*=\s*true\b",
            "notify_on_complete": r"\bnotify_on_complete\b",
        },
        "opencode": {},
        "codex": {},
        "copilot-cli": {},
    }


def test_no_name_is_claimed_by_two_harnesses_across_both_vocabularies() -> None:
    """Review p1r-m2: the uniqueness guard spans tool names AND argument names,
    since `scan_prose` reports both through one `Violation.tool` field — a name
    claimed twice, in either vocabulary or across them, could not say which
    harness a mention serves."""
    names = {
        harness: set(TOOL_VOCABULARY[harness]) | set(ARGUMENT_VOCABULARY[harness])
        for harness in HARNESSES
    }
    for (harness_a, names_a), (harness_b, names_b) in combinations(names.items(), 2):
        overlap = names_a & names_b
        assert not overlap, f"{harness_a!r} and {harness_b!r} both claim {overlap!r}"
    for harness in HARNESSES:
        both = set(TOOL_VOCABULARY[harness]) & set(ARGUMENT_VOCABULARY[harness])
        assert not both, f"{harness!r} claims {both!r} as both a tool and an argument"


@pytest.mark.parametrize(
    "spelling",
    [
        'isolation:"worktree"',
        "isolation: 'worktree'",
        'isolation="worktree"',
        'isolation: "worktree"',
        "isolation=worktree",
    ],
)
def test_every_spelling_of_the_isolation_flag_is_the_claude_code_argument(spelling: str) -> None:
    text = f"Dispatch it with `{spelling}` set.\n"
    assert scan_prose(text) == [
        Violation(harness="claude-code", tool='isolation: "worktree"', line=1)
    ]


@pytest.mark.parametrize(
    ("text", "harness", "name"),
    [
        ("Run the suite with run_in_background, then wait.", "claude-code", "run_in_background"),
        ("Call terminal with background=true and poll.", "hermes", "background=true"),
        ("Call terminal with background = true and poll.", "hermes", "background=true"),
        ("Pass notify_on_complete so you hear back.", "hermes", "notify_on_complete"),
    ],
)
def test_a_bare_argument_is_a_violation_naming_its_harness(
    text: str, harness: str, name: str
) -> None:
    assert scan_prose(text + "\n") == [Violation(harness=harness, tool=name, line=1)]


@pytest.mark.parametrize(
    "argument",
    ['isolation: "worktree"', "run_in_background", "background=true", "notify_on_complete"],
)
def test_an_argument_inside_a_valid_clause_is_excused(argument: str) -> None:
    text = (
        f"**Harness — long commands:** Claude Code, Hermes and OpenCode differ; one of\n"
        f"them takes `{argument}`, and each reader is told what to do.\n"
    )
    assert scan_prose(text) == []


def test_an_argument_inside_a_one_harness_clause_is_still_a_violation() -> None:
    text = "**Harness — long commands:** Claude Code takes run_in_background.\n"
    assert [v.tool for v in scan_prose(text)] == ["run_in_background"]


def test_argument_patterns_are_case_sensitive_and_word_bounded() -> None:
    """`background=True` (Python's spelling in ordinary prose) and a longer
    identifier that merely contains an argument name are not the argument."""
    assert scan_prose("x.background=True\n") == []
    assert scan_prose("my_run_in_background_helper\n") == []


def test_the_import_time_key_check_names_the_mapping_it_rejects() -> None:
    """Review p1r-m2: `prose.py` checks every harness-keyed mapping it consumes
    at import, and the error names THAT mapping — the old message blamed
    `TOOL_VOCABULARY` while checking `_HARNESS_LABELS`."""
    require_every_harness("ARGUMENT_VOCABULARY", ARGUMENT_VOCABULARY)
    broken = {harness: {} for harness in HARNESSES if harness != "hermes"}
    with pytest.raises(
        HarnessError, match=r"^ARGUMENT_VOCABULARY disagrees with HARNESSES: \['hermes'\]$"
    ):
        require_every_harness("ARGUMENT_VOCABULARY", broken)
