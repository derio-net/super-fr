"""Tool-name neutrality scan — 2026-09-18 harness-parity-matrix spec §3.C,
Phase 3.

#436's class B: skill prose that names a harness-specific tool (Claude
Code's `AskUserQuestion`, say) as *the* way to do something. Both sync
scripts copy `SKILL.md` byte-for-byte (`dest.write_text(src.read_text())`),
so the name rides unchanged into `.opencode/skills/` and
`.hermes/skills/fr/` — translating at sync time was rejected (spec §3.C)
because it would fork one prose into three and break the sync tripwires'
byte-identity assertion. So the fix lives in the canonical prose itself,
and this module is what checks it stayed fixed.

A **scoped clause** is the one escape hatch, and it is not a free pass for
any mention inside it — see `_MIN_HARNESSES_PER_CLAUSE` below. It is
modelled on prose that already exists and already carries this exact
shape: `fr-goal` §5's `**Harness — dispatch:**` paragraph, which names
Claude Code's `Agent` tool AND Hermes's `delegate_task` and says which is
which, so a reader on either harness is correctly served. A clause counts
as scoped by naming (in prose) more than one harness by name — not by
each harness having its own distinct tool to name; a harness with no tool
of its own for the topic ("Hermes has no dedicated question tool, ask via
X instead") still correctly serves that harness's reader.

What is scanned: tool names (`TOOL_VOCABULARY`) and harness-specific
arguments (`ARGUMENT_VOCABULARY`, 2026-09-22 harness-argument-neutrality
spec §3.A), both judged by the same clause rules.

**Headings are not instructions** (spec §3.B, decision d-headings-exempt). A
Markdown ATX heading line (`^#{1,6} `) names a topic; it never tells a reader
to call anything, so it is skipped. Measured 2026-09-22 over the canonical
skills, agents and rules, every heading the scan would otherwise flag was a
false positive — four, all tool names used as English words:
`## Plan Skill Override` and `## fr-* Skill Overview` (fr-plan-override),
`# Worktree Skill Override (fr-enabled repos)` (fr-worktree-override), and
`### 1. Agent sessions, pods and CI always land non-interactive — by design`
(artifact-versioning). Only a real ATX heading OUTSIDE a code fence is
exempt (a fenced `# ...` is a comment a reader may copy, review p2r-4), and a
heading neither leads a clause nor names a harness for one (review p2r-5): `#Skill` (no
space), seven hashes, or an indented hash are body text and still scanned.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from fr.harness import ARGUMENT_VOCABULARY, HARNESSES, TOOL_VOCABULARY
from fr.harness.model import HarnessError

# What a clause names is the HARNESS a reader is on, not necessarily that
# harness's own tool — a clause explaining "Hermes has no dedicated tool
# for this, do X instead" still correctly serves a Hermes reader without
# ever mentioning a Hermes tool name. So clause validity is judged by
# these display labels, independent of TOOL_VOCABULARY.
_HARNESS_LABELS: dict[str, str] = {
    "claude-code": "Claude Code",
    "opencode": "OpenCode",
    "hermes": "Hermes",
    "codex": "Codex",
    "copilot-cli": "Copilot CLI",
}


def require_every_harness(name: str, mapping: Mapping[str, object]) -> None:
    """Closed-world key check for a harness-keyed mapping this module consumes:
    exactly the members of `HARNESSES`, none missing, none extra. The error
    names `name` — the mapping actually checked (review p1r-m2: the previous
    inline check blamed `TOOL_VOCABULARY` while checking `_HARNESS_LABELS`)."""
    if set(mapping) != set(HARNESSES):
        raise HarnessError(
            f"{name} disagrees with HARNESSES: {sorted(set(mapping) ^ set(HARNESSES))}"
        )


# Import-time invariants: a vocabulary missing a harness would silently scan
# nothing for it.
require_every_harness("_HARNESS_LABELS", _HARNESS_LABELS)
require_every_harness("TOOL_VOCABULARY", TOOL_VOCABULARY)
require_every_harness("ARGUMENT_VOCABULARY", ARGUMENT_VOCABULARY)


@dataclass(frozen=True)
class _Lookup:
    """One harness-specific name and how to find it in a line. A tool name is
    one literal token, matched by `_word_pattern`; an argument carries its own
    compiled pattern because it has several spellings. Either way `scan_prose`
    judges a match by the same clause rules — this is the one place both
    vocabularies meet, so the clause logic exists once."""

    harness: str
    name: str
    pattern: re.Pattern[str]


# `**Harness — <topic>:**` — the em dash and bold markers are load-bearing:
# they're what makes this shape rare enough to grep for and distinguishable
# from ordinary prose that happens to say the word "harness".
_CLAUSE_LEAD_RE = re.compile(r"\*\*Harness — [^*\n]+:\*\*")

# An ATX heading (spec §3.B) names a topic, never an instruction.
_HEADING_RE = re.compile(r"^#{1,6} ")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _heading_lines(lines: list[str]) -> frozenset[int]:
    """Indices of real headings — `_HEADING_RE` lines OUTSIDE a code fence.

    Inside a fence a `# ...` line is a shell or YAML comment a reader may copy
    verbatim, so it is scanned like any other line (review p2r-4: the skip
    first applied to fenced comments too, and hid `# pass run_in_background`).
    """
    headings: set[int] = set()
    fenced = False
    for idx, line in enumerate(lines):
        if _FENCE_RE.match(line):
            fenced = not fenced
        elif not fenced and _HEADING_RE.match(line):
            headings.add(idx)
    return frozenset(headings)


# A scoped clause excuses a mention only when it names every SUPPORTED
# harness by display label — not by a tool of its own, because "OpenCode has
# no tool here, do X instead" serves an OpenCode reader perfectly well.
#
# The bar was 2 and is now len(SUPPORTED_HARNESSES) (review r3-i1). At 2, a
# clause could excuse a Claude-only tool by name-dropping any second harness
# while telling its reader nothing: `**Harness — q:** Call AskUserQuestion.
# Hermes, OpenCode.` passed. Requiring all three means a clause cannot be
# written without at least confronting what each reader should do. It also
# forced fr-goal §5's dispatch clause to grow the OpenCode arm it was missing,
# which is a real improvement rather than gate-appeasement — an OpenCode reader
# of that clause previously got nothing.
#
# BE HONEST ABOUT WHAT THIS PROVES: it is a SYNTACTIC bar. It shows a clause
# was written with every reader in view; it cannot show the clause is useful,
# and one valid clause still excuses every tool inside its span. A clause that
# name-drops all three and says nothing passes. Review catches that; the scan
# cannot.
#
# Unsupported harnesses (`codex`, `copilot-cli`) are excluded: there is no
# reader to serve yet, and requiring their labels would make every clause
# recite two names that mean "not yet".
SUPPORTED_HARNESSES = ("claude-code", "opencode", "hermes")
_MIN_HARNESSES_PER_CLAUSE = len(SUPPORTED_HARNESSES)


@dataclass(frozen=True)
class Violation:
    harness: str
    tool: str
    line: int
    """1-based line number of the offending mention."""


def _word_pattern(name: str) -> re.Pattern[str]:
    # Word boundaries alone let "Agent" match inside "Agent-facing skill"
    # (a real, present occurrence — fr-execute's frontmatter) since a
    # hyphen is a non-word character and \b fires either side of it. That
    # is a compound adjective, not a mention of the Agent tool, so the
    # pattern additionally refuses a hyphen directly touching the name.
    # Shared by both tool names (`AskUserQuestion`) and harness display
    # labels (`Claude Code`) — same "is this really a standalone mention"
    # question either way.
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


# Built once at import: tool names (`TOOL_VOCABULARY`, harness -> tools) and
# argument patterns (`ARGUMENT_VOCABULARY`, harness -> name -> regex) flattened
# into one table. `test_no_name_is_claimed_by_two_harnesses_across_both_vocabularies`
# guarantees no name appears twice, so a violation's `tool` names one harness.
_LOOKUPS: tuple[_Lookup, ...] = (
    *(
        _Lookup(harness, tool, _word_pattern(tool))
        for harness, tools in TOOL_VOCABULARY.items()
        for tool in sorted(tools)
    ),
    *(
        _Lookup(harness, name, pattern)
        for harness, arguments in ARGUMENT_VOCABULARY.items()
        for name, pattern in arguments.items()
    ),
)


def _clause_spans(
    lines: list[str], headings: frozenset[int] = frozenset()
) -> list[tuple[int, int]]:
    """Line-index spans (inclusive) covered by a `**Harness — ...:**`
    clause: from the lead-in to the next blank line followed by a
    non-indented line (or end of text), per spec §3.C."""
    spans: list[tuple[int, int]] = []
    n = len(lines)
    i = 0
    while i < n:
        if i not in headings and _CLAUSE_LEAD_RE.search(lines[i]):
            start = i
            end = i
            j = i + 1
            while j < n:
                if lines[j].strip() == "":
                    following = lines[j + 1] if j + 1 < n else None
                    # `following[:1]`, not `following[0]` (review r3-c1): a
                    # SECOND blank line makes `following` empty and `""[0]`
                    # raised IndexError, so an ordinary blank-line pair after a
                    # clause crashed the scan. `""[:1].isspace()` is False,
                    # which breaks the span — exactly what an unindented line
                    # should do.
                    if following is None or not following[:1].isspace():
                        break
                end = j
                j += 1
            spans.append((start, end))
            i = j + 1
        else:
            i += 1
    return spans


def _clause_is_valid(
    lines: list[str], start: int, end: int, headings: frozenset[int] = frozenset()
) -> bool:
    """A scoped clause excuses a mention only when its PROSE names every
    supported harness by display label — see `_MIN_HARNESSES_PER_CLAUSE`. A
    heading line inside the span names a topic, not a reader, so it does not
    count (review p2r-5)."""
    clause_lines = [lines[i] for i in range(start, end + 1) if i not in headings]
    harnesses_named = {
        harness
        for harness, label in _HARNESS_LABELS.items()
        if harness in SUPPORTED_HARNESSES
        and any(_word_pattern(label).search(clause_line) for clause_line in clause_lines)
    }
    return len(harnesses_named) >= _MIN_HARNESSES_PER_CLAUSE


def scan_prose(text: str) -> list[Violation]:
    """Every harness-specific tool or argument mention in `text` that is NOT
    inside a scoped clause naming every supported harness, skipping headings.

    There is no per-call vocabulary: a name worth flagging in one tree is
    worth flagging in every tree a reader on any harness follows, so it
    belongs in `TOOL_VOCABULARY` or `ARGUMENT_VOCABULARY` (2026-09-22
    harness-argument-neutrality spec §3.A removed the `extra_tools` escape
    hatch the agent tree used for Claude Code's `isolation: "worktree"`).

    Ordered by (line, tool) so a failure listing several hits reads top to
    bottom the way the file does — the loop below is tool-major for pattern
    reuse (review r3-m6)."""
    lines = text.splitlines()
    headings = _heading_lines(lines)
    spans = _clause_spans(lines, headings)
    valid_span = {span: _clause_is_valid(lines, *span, headings=headings) for span in spans}

    violations: list[Violation] = []
    for lookup in _LOOKUPS:
        for line_idx, line in enumerate(lines):
            if line_idx in headings or not lookup.pattern.search(line):
                continue
            clause = next((s for s in spans if s[0] <= line_idx <= s[1]), None)
            if clause is not None and valid_span[clause]:
                continue
            violations.append(
                Violation(harness=lookup.harness, tool=lookup.name, line=line_idx + 1)
            )
    return sorted(violations, key=lambda v: (v.line, v.tool))
