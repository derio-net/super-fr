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
assert set(_HARNESS_LABELS) == set(HARNESSES)

# `**Harness — <topic>:**` — the em dash and bold markers are load-bearing:
# they're what makes this shape rare enough to grep for and distinguishable
# from ordinary prose that happens to say the word "harness".
_CLAUSE_LEAD_RE = re.compile(r"\*\*Harness — [^*\n]+:\*\*")

# A scoped clause is only a pass when it actually serves more than one
# harness's reader. A clause wrapper around a single harness's tool still
# leaves every other harness's reader with nothing — "the bug wearing a
# clause's shape" — so the bar is DISTINCT harnesses named (by their
# `_HARNESS_LABELS` display label, not necessarily by a tool of their
# own — "Hermes has no dedicated tool here, do X instead" still correctly
# serves a Hermes reader). Two, not "every HARNESSES member":
# the real fr-goal §5 clause this rule is derived from names exactly two
# (claude-code, hermes) because OpenCode has no dispatch mechanism of its
# own to name; requiring all five would make the shipping clause its own
# violation.
_MIN_HARNESSES_PER_CLAUSE = 2


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
                    if following is None or not following[0].isspace():
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
        if any(_word_pattern(label).search(clause_line) for clause_line in clause_lines)
    }
    return len(harnesses_named) >= _MIN_HARNESSES_PER_CLAUSE


def scan_prose(text: str) -> list[Violation]:
    """Every harness-specific tool mention in `text` that is NOT inside a
    scoped clause serving more than one harness."""
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
    return violations
