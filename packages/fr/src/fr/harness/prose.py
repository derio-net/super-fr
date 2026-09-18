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
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fr.harness import HARNESSES, TOOL_VOCABULARY
from fr.harness.model import HarnessError

# Every mention needs its owning harness looked up; TOOL_VOCABULARY is
# built the other way around (harness -> tools), so invert it once. The
# module-level `test_no_tool_name_is_claimed_by_two_harnesses` guarantees
# this inversion loses nothing.
_HARNESS_BY_TOOL: dict[str, str] = {
    tool: harness for harness, tools in TOOL_VOCABULARY.items() for tool in tools
}

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
if set(_HARNESS_LABELS) != set(HARNESSES):  # pragma: no cover — import-time invariant
    raise HarnessError(
        "TOOL_VOCABULARY/_HARNESS_LABELS disagree with HARNESSES: "
        f"{sorted(set(_HARNESS_LABELS) ^ set(HARNESSES))}"
    )

# `**Harness — <topic>:**` — the em dash and bold markers are load-bearing:
# they're what makes this shape rare enough to grep for and distinguishable
# from ordinary prose that happens to say the word "harness".
_CLAUSE_LEAD_RE = re.compile(r"\*\*Harness — [^*\n]+:\*\*")

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


def _clause_spans(lines: list[str]) -> list[tuple[int, int]]:
    """Line-index spans (inclusive) covered by a `**Harness — ...:**`
    clause: from the lead-in to the next blank line followed by a
    non-indented line (or end of text), per spec §3.C."""
    spans: list[tuple[int, int]] = []
    n = len(lines)
    i = 0
    while i < n:
        if _CLAUSE_LEAD_RE.search(lines[i]):
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


def _clause_is_valid(lines: list[str], start: int, end: int) -> bool:
    """A scoped clause excuses a mention only when it names more than one
    harness by its display label — see `_MIN_HARNESSES_PER_CLAUSE`."""
    clause_lines = lines[start : end + 1]
    harnesses_named = {
        harness
        for harness, label in _HARNESS_LABELS.items()
        if harness in SUPPORTED_HARNESSES
        and any(_word_pattern(label).search(clause_line) for clause_line in clause_lines)
    }
    return len(harnesses_named) >= _MIN_HARNESSES_PER_CLAUSE


def scan_prose(text: str) -> list[Violation]:
    """Every harness-specific tool mention in `text` that is NOT inside a
    scoped clause naming every supported harness.

    Ordered by (line, tool) so a failure listing several hits reads top to
    bottom the way the file does — the loop below is tool-major for pattern
    reuse (review r3-m6)."""
    lines = text.splitlines()
    spans = _clause_spans(lines)
    valid_span = {span: _clause_is_valid(lines, *span) for span in spans}

    violations: list[Violation] = []
    for tool, harness in _HARNESS_BY_TOOL.items():
        pattern = _word_pattern(tool)
        for line_idx, line in enumerate(lines):
            if not pattern.search(line):
                continue
            clause = next((s for s in spans if s[0] <= line_idx <= s[1]), None)
            if clause is not None and valid_span[clause]:
                continue
            violations.append(Violation(harness=harness, tool=tool, line=line_idx + 1))
    return sorted(violations, key=lambda v: (v.line, v.tool))
