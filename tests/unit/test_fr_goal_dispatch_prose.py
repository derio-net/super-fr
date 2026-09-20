"""fr-goal §5's `**Harness — dispatch:**` clause serves an OpenCode reader —
2026-09-19 opencode-subagent-dispatch spec §3.D, Phase 4.

The prose is the actual gate (spec §1.1). Phases 1-3 shipped the agents, the
tiers and the installer, and none of it changes any behaviour while this one
paragraph still tells an OpenCode reader that the harness has "no dispatch
primitive of its own" and phases run inline. Both sync scripts copy `SKILL.md`
byte-for-byte, so the retracted sentence reached `.opencode/skills/` and
`.hermes/skills/fr/` too: the reader was instructed by the very copy they read
to ignore the feature.

These assertions are deliberately about MEANING THAT SURVIVES REWORDING — a
multiple and a direction, not a sentence — so ordinary editing of the clause
does not fail the test while a silent removal of the policy does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.harness import load_matrix
from fr.harness.prose import scan_prose

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"

_CLAUSE_LEAD = "**Harness — dispatch:**"


@pytest.fixture
def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture
def dispatch_clause(skill_text: str) -> str:
    """The clause only, so "inline" on the neighbouring line (§5's `blocked →
    run inline` fallback, a different statement) cannot satisfy an assertion
    about the OpenCode arm."""
    lines = skill_text.splitlines()
    starts = [i for i, line in enumerate(lines) if _CLAUSE_LEAD in line]
    assert len(starts) == 1, f"expected exactly one {_CLAUSE_LEAD!r} clause, found {len(starts)}"
    start = starts[0]
    end = start
    while end + 1 < len(lines) and lines[end + 1].strip():
        end += 1
    return "\n".join(lines[start : end + 1])


def test_the_retracted_claim_is_gone(skill_text: str) -> None:
    """Spec §1 claim 1: OpenCode has two dispatch primitives, and this repo's
    own recorded experiment already ran 13 child sessions through one."""
    assert "no dispatch primitive" not in skill_text


def test_the_clause_tells_an_opencode_reader_what_to_dispatch(dispatch_clause: str) -> None:
    assert "subagent_type" in dispatch_clause
    assert "fr-phase-executor-<tier>" in dispatch_clause
    # The two-word form the vocabulary actually registers (see
    # `test_harness_vocabulary`): naming the tool in a form the scanner can
    # see is what makes the `scan_prose` assertion below say anything about
    # this mention at all.
    assert "task tool" in dispatch_clause


def test_the_clause_states_the_cost_policy(dispatch_clause: str) -> None:
    """A multiple AND a direction — not an exact sentence. The number may be
    reworded (`~7x`, `7×`, `roughly 7 times`); what must not vanish is that
    dispatching costs a stated multiple of running inline, since that is the
    price the default is knowingly buying (spec §3.D, decision `d1`)."""
    assert re.search(r"(?<![\w.])7\s*(?:[x×]|times)", dispatch_clause), (
        "the cost multiple (~7x an inline run) is not stated in the dispatch clause"
    )
    assert "inline" in dispatch_clause, (
        "the multiple is stated with no direction — 7x WHAT? name the inline baseline"
    )


def test_the_new_tool_mention_stayed_inside_the_scoped_clause(skill_text: str) -> None:
    """The load-bearing one. `task` is now in `TOOL_VOCABULARY["opencode"]`,
    so naming it anywhere outside a clause that serves every supported harness
    is a violation — this is what proves the rewrite did not leak a
    harness-specific tool name into the two byte-identical mirrors."""
    assert scan_prose(skill_text) == []


_MULTIPLE_RE = re.compile(r"(?<![\w.])(\d+)\s*(?:[x×]|times)\b")


def test_the_row_and_the_clause_state_the_same_multiple(dispatch_clause: str) -> None:
    """P4.T2.S3. The cost policy is deliberately in two places — a reader must
    meet the price where they meet the claim, in `parity.yaml`'s row and in
    the clause that tells them to dispatch — and two places is exactly how one
    number drifts. Division of labour: the row is the SHORT form and names the
    clause as the one home for the detail; the clause is the operational one
    and owns the measured figures ($7.59 vs ~$1, 56.2 min vs 77.6/105.2) that
    the row never repeats. The single token they do share is the multiple, so
    pin it: change it in one place and this fails naming both."""
    row = next(s for s in load_matrix().surfaces if s.id == "subagent-dispatch")
    in_clause = {m.group(1) for m in _MULTIPLE_RE.finditer(dispatch_clause)}
    in_row = {m.group(1) for m in _MULTIPLE_RE.finditer(row.summary)}
    assert in_clause and in_row, f"a multiple vanished: clause={in_clause}, row={in_row}"
    assert in_clause == in_row, (
        f"fr-goal §5's dispatch clause says {sorted(in_clause)}x and the "
        f"subagent-dispatch row says {sorted(in_row)}x — one of them drifted"
    )


def test_the_row_does_not_restate_the_clauses_measured_detail() -> None:
    """The other half of the division: if the row starts carrying the dollar
    or wall-clock figures too, there is no longer an obvious single home for
    them and the next change has to find both."""
    summary = next(s for s in load_matrix().surfaces if s.id == "subagent-dispatch").summary
    assert "$" not in summary and "min" not in summary, (
        f"the row summary took on the clause's measured detail: {summary!r}"
    )


# 2026-09-20 opencode-tier-binding-reaches-dispatch spec §3.B, decision `d2`,
# P3.T1. An unresolved tier used to dispatch `fr-phase-executor-<tier>` anyway:
# the agent inherits the session model, so the session row is indistinguishable
# from a working tiered dispatch. Dispatching the UNTIERED name instead makes
# the absence visible in the one artifact anyone checks.
#
# `(?![\w-])` is what separates the two names: `fr-phase-executor-<tier>`
# contains `fr-phase-executor`, so a bare substring test would already pass.
_UNTIERED_AGENT_RE = re.compile(r"fr-phase-executor(?![\w-])")

# Meaning, not a sentence: any of these says "the tier did not resolve".
_UNRESOLVED_RE = re.compile(
    r"unresolv\w*|unbound|no binding|(?:comes? back |returns? |resolves? )?empty"
    r"|(?:cannot|can't|does not|doesn't|won't) resolve",
    re.IGNORECASE,
)
_JOURNAL_RE = re.compile(r"journal\w*", re.IGNORECASE)

# Wide enough that reordering the clause or splitting the fallback across a
# line break cannot fail it, narrow enough that the Claude Code arm's own
# untiered mention at the head of the clause does not reach the tail.
_NEIGHBOURHOOD = 240


def test_the_clause_instructs_the_untiered_fallback_when_a_tier_is_unresolved(
    dispatch_clause: str,
) -> None:
    """The fallback must be stated where the dispatch instruction lives, and
    stated as BOTH halves: dispatch the untiered name, and journal why. Half of
    it is the defect — a silent untiered dispatch is another unexplained row."""
    windows = [
        dispatch_clause[max(0, m.start() - _NEIGHBOURHOOD) : m.end() + _NEIGHBOURHOOD]
        for m in _UNTIERED_AGENT_RE.finditer(dispatch_clause)
    ]
    assert windows, (
        "the untiered `fr-phase-executor` is not named in the dispatch clause "
        "at all, so no reader can be told to fall back to it"
    )
    assert any(_UNRESOLVED_RE.search(w) and _JOURNAL_RE.search(w) for w in windows), (
        "the dispatch clause names the untiered `fr-phase-executor` but never "
        "ties it to an UNRESOLVED tier and a journal entry — an unresolved tier "
        "dispatching `fr-phase-executor-<tier>` silently inherits the session "
        "model (spec §3.B, decision `d2`)"
    )


def test_the_fallback_clause_still_names_no_harness_specific_tool_unscoped(
    skill_text: str,
) -> None:
    """Re-asserted for this edit specifically: the fallback lands in the one
    clause that legitimately names OpenCode's `task` tool, so an edit there is
    exactly where a harness-specific mention could escape its scope.
    `test_the_new_tool_mention_stayed_inside_the_scoped_clause` is the standing
    guard; this pins it to P3.T1's change."""
    assert scan_prose(skill_text) == []
