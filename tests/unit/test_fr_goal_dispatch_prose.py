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
