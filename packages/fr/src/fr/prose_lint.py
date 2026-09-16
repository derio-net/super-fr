"""Warn-only prose lint for text that fr writes.

Spec: docs/superpowers/specs/2026-09-14-ste-output-tone-design.md §5.C.
Two checks: sentences over MAX_SENTENCE_WORDS words, and filler words.
The 20-word limit for instructions is not checked: code cannot tell an
instruction from a description. Callers print the issues; nothing here
decides an exit code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MAX_SENTENCE_WORDS = 25
FILLER_WORDS: tuple[str, ...] = (
    "just",
    "really",
    "basically",
    "actually",
    "simply",
    "I think",
    "it seems",
)

# Block-level non-prose, removed from the whole text before it is split.
_FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.S)
# Indented, `~~~` and 4+-backtick fences; an unclosed fence runs to the end.
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[ \t]*$|\Z)", re.S | re.M)
# The plan embed convention. It ends at a bare `END` or at `END <same label>`,
# never at a code line that merely starts with END.
_EMBED = re.compile(
    r"^[ \t]*BEGIN[ \t]+([^\n]*?)[ \t]*\n.*?^[ \t]*END(?:[ \t]+\1)?[ \t]*$", re.S | re.M
)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SKIPPED_LINE = re.compile(r"^[ \t]*(?:#{1,6}(?:[ \t]|$)|\|)")

_ITEM_SPLIT = re.compile(r"\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d+[.)])[ \t])")
_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")

# Inline non-prose, removed from one flattened item, so a span that wraps
# across lines is removed whole.
_INLINE_CODE = re.compile(r"(`+).+?\1")
_QUOTED = re.compile(r'"([^"]*)"')
_URL = re.compile(r"https?://\S+")

# A sentence ends at . ! or ?, also when a closer follows (`.**`, `.)`, `."`).
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[*_)\]\"'’”`]*\s+")
_WORD_CHAR = re.compile(r"\w")


@dataclass(frozen=True)
class ProseIssue:
    kind: Literal["long-sentence", "filler"]
    excerpt: str
    words: int | None = None

    def __str__(self) -> str:
        if self.kind == "long-sentence":
            return f"sentence of {self.words} words (max {MAX_SENTENCE_WORDS}): {self.excerpt}"
        return f"filler word {self.excerpt!r}"


def _filler_pattern(word: str) -> re.Pattern[str]:
    """A whole-word match that is not part of a path or a hyphenated word."""
    body = r"\s+".join(re.escape(part) for part in word.split())
    return re.compile(rf"(?<![\w/.-]){body}(?![\w/-])", re.IGNORECASE)


_FILLER_PATTERNS: dict[str, re.Pattern[str]] = {}


def _keep_final_mark(match: re.Match[str]) -> str:
    """A quoted string is removed, but a sentence end inside it is kept."""
    inner = match.group(1)
    return inner[-1] if inner[-1:] in (".", "!", "?") else ""


def _prose_items(text: str) -> list[str]:
    """Flattened prose items with every kind of non-prose removed."""
    text = _FRONT_MATTER.sub("", text.replace("\r\n", "\n"))
    for pattern in (_FENCE, _EMBED, _COMMENT):
        text = pattern.sub("", text)
    text = "\n".join(line for line in text.split("\n") if not _SKIPPED_LINE.match(line))
    items: list[str] = []
    for item in _ITEM_SPLIT.split(text):
        flat = _LIST_MARKER.sub("", " ".join(item.split()), count=1)
        flat = _INLINE_CODE.sub("", flat)
        flat = _QUOTED.sub(_keep_final_mark, flat)
        flat = _URL.sub("", flat)
        if flat.strip():
            items.append(flat)
    return items


def _word_count(sentence: str) -> int:
    return sum(1 for token in sentence.split() if _WORD_CHAR.search(token))


def _excerpt(sentence: str, limit: int = 80) -> str:
    flat = " ".join(sentence.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def lint_prose(text: str) -> list[ProseIssue]:
    """All long sentences in document order, then filler words in FILLER_WORDS order."""
    items = _prose_items(text)
    issues: list[ProseIssue] = []
    for item in items:
        for sentence in _SENTENCE_SPLIT.split(item):
            count = _word_count(sentence)
            if count > MAX_SENTENCE_WORDS:
                issues.append(ProseIssue("long-sentence", _excerpt(sentence), count))
    for word in FILLER_WORDS:
        pattern = _FILLER_PATTERNS.get(word) or _FILLER_PATTERNS.setdefault(
            word, _filler_pattern(word)
        )
        if any(pattern.search(item) for item in items):
            issues.append(ProseIssue("filler", word))
    return issues
