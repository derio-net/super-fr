"""CI tripwire: the fixed-size question-batch contract must not come back.

Spec `2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.A/§3.A.1
replaces fr-goal's old promise — "one batched Q&A of at most four questions"
— with "one operator gate, sized to the feature, one round or two when the
second is announced up front or the operator asks for it". §3.A.1 lists every
surface that stated the old contract and must be rewritten in this PR: the
canonical `fr-goal` and `fr-brainstorming` skills, their OpenCode and Hermes
mirrors, the OpenCode `/fr-goal` command, the fr-goal explainer (source and
rendered page), the explainers index page, and the top-level README.

This is a prose-only guard (the record-declaration mechanism and the
transcript-verifying gate shipped in phases 1-2) — nothing here exercises
code, only wording, and only wording is what a rewrap or a "helpful"
paraphrase silently regresses. So every match runs on NORMALISED text:
whitespace collapsed and casefolded, so a line break or a capital letter in
the middle of an old phrase cannot hide it (review p3-r2).
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FR_GOAL_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-goal" / "SKILL.md",
)

FR_BRAINSTORMING_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-brainstorming" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-brainstorming" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-brainstorming" / "SKILL.md",
)

EXPLAINER_MD = REPO_ROOT / "docs" / "explainers" / "01-fr-goal.md"
EXPLAINER_HTML = REPO_ROOT / "docs" / "explainers" / "01-fr-goal.html"
INDEX_HTML = REPO_ROOT / "docs" / "explainers" / "index.html"
README = REPO_ROOT / "README.md"
OPENCODE_COMMAND = REPO_ROOT / ".opencode" / "commands" / "fr-goal.md"

# §3.A.1's full list of surfaces stating the old contract, plus the three
# surfaces review p3-r3 found still carrying it (the published pages and the
# OpenCode command).
ALL_SURFACES = (
    *FR_GOAL_COPIES,
    *FR_BRAINSTORMING_COPIES,
    EXPLAINER_MD,
    EXPLAINER_HTML,
    INDEX_HTML,
    README,
    OPENCODE_COMMAND,
)

# The fixed-batch contract's own vocabulary, casefolded. None of it may
# survive anywhere in scope — a stray phrase from the old contract is the
# regression this tripwire exists to catch.
OLD_CONTRACT_PHRASES = tuple(
    p.casefold()
    for p in (
        "max 4",
        "≤4 questions",
        "ONE batch",
        "one batched Q&A",
        "no more than four questions",
        "ask ONCE",
        "one round of questions",
        "yes, once",
        "one consolidated question set",
        "one batched round",
        "the batched Q&A",
        "batched Q&A",
        "one short round",
        "asks its questions once",
        "one organized set of questions",
        "one set of questions",
    )
)

# (surface, phrase) pairs that are a legitimate remaining use, each with the
# reason it is not the old contract. Empty today: every surface was rewritten.
ALLOWED_OLD_PHRASES: frozenset[tuple[Path, str]] = frozenset()

# The new contract, stated so that an agent following it produces what the
# gate accepts — every marker names a behaviour `resolve` checks or a sizing
# rule the spec sets (review p3-r3), not just the word "round".
NEW_CONTRACT_MARKERS = tuple(
    m.casefold()
    for m in (
        "questions: {rounds",  # the record declaration (§3.B)
        "(Round 1 of",  # the up-front announcement the gate looks for
        "(Round 2 of 2)",
        "design-risk",  # the two triggers a second round may carry
        "operator-request",
        "never a round 3",
        "one question per",  # sized per decision, not a fixed batch
        "~10",
        # Rounds are separated by the cross-examination's real tool calls
        # (review p3-r1): `answered_rounds_since` closes a round only on a
        # non-question, non-progress-tracking tool call.
        "that check is what separates the rounds",
        "real tool calls",
        "progress-tracking tools do not separate rounds",
        "a ceiling, not a promise",  # announced round 2 may resolve rounds: 1 (p3-r7)
        "gate-question-rounds",  # the spec-journal entry that reaches the PR (p3-r9)
    )
)

# The instruction review p3-r1 found: cross-examining "in prose" merges round
# 1 and round 2 into ONE transcript round, so a declared `rounds: 2` is refused.
FORBIDDEN_FR_GOAL_PHRASES = tuple(
    p.casefold()
    for p in (
        "in prose, not a tool call",
        "in prose, never a tool call",
        "cross-examination in prose",
    )
)

# Surfaces that only need to say the contract is in rounds at all.
MINIMAL_MARKER_SURFACES = (
    *FR_BRAINSTORMING_COPIES,
    EXPLAINER_MD,
    README,
    INDEX_HTML,
)

_TAG = re.compile(r"<[^>]+>")


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def _surface_text(path: Path) -> str:
    """The normalised prose of `path`. HTML pages are megabytes of embedded
    fonts, so they are streamed line by line: base64 font lines are skipped,
    tags stripped and entities unescaped, so `Q&amp;A` reads as `Q&A` and a
    `<span>` inside a phrase cannot hide it."""
    if path.suffix != ".html":
        return _normalise(path.read_text(encoding="utf-8"))
    parts: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if "base64," in line:
                continue
            parts.append(html.unescape(_TAG.sub(" ", line)))
    return _normalise(" ".join(parts))


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


@pytest.mark.parametrize("surface", ALL_SURFACES, ids=_rel)
@pytest.mark.parametrize("phrase", OLD_CONTRACT_PHRASES)
def test_old_fixed_batch_contract_is_gone(surface: Path, phrase: str) -> None:
    if (surface, phrase) in ALLOWED_OLD_PHRASES:
        pytest.skip("allowlisted legitimate use")
    assert phrase not in _surface_text(surface), (
        f"{_rel(surface)} still states the old fixed-batch contract ({phrase!r}) "
        "— spec §3.A.1 rewrites every surface in this table to the sized-round "
        "contract; see §3.A for the replacement wording."
    )


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=_rel)
@pytest.mark.parametrize("marker", NEW_CONTRACT_MARKERS)
def test_fr_goal_states_the_new_round_contract(skill: Path, marker: str) -> None:
    assert marker in _surface_text(skill), (
        f"{_rel(skill)} is missing {marker!r} — spec §3.A/§3.A.1 requires the "
        "canonical fr-goal skill (and both mirrors) to state the round "
        "announcement, the two triggers, the never-a-round-3 rule, per-decision "
        "sizing, the tool-call round separation and the record's `questions:` "
        "declaration."
    )


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=_rel)
@pytest.mark.parametrize("phrase", FORBIDDEN_FR_GOAL_PHRASES)
def test_fr_goal_never_merges_rounds_by_prose_cross_examination(skill: Path, phrase: str) -> None:
    assert phrase not in _surface_text(skill), (
        f"{_rel(skill)} tells the agent to cross-examine {phrase!r} — the gate "
        "closes a round only on a real non-question tool call, so prose-only "
        "cross-examination merges round 1 and round 2 and a declared `rounds: 2` "
        "is refused (review p3-r1)."
    )


@pytest.mark.parametrize("surface", MINIMAL_MARKER_SURFACES, ids=_rel)
def test_surface_describes_question_rounds(surface: Path) -> None:
    assert "round" in _surface_text(surface), (
        f"{_rel(surface)} no longer describes the question round at all — spec "
        "§3.A.1 rewrites it to the sized-round contract, not away."
    )
