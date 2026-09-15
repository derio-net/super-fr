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

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_FENCE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[^\n]*$", re.S | re.M)
_EMBED = re.compile(r"^[ \t]*BEGIN\b[^\n]*\n.*?^[ \t]*END\b[^\n]*$", re.S | re.M)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_QUOTED = re.compile(r'"[^"\n]*"')
_URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"[\w'-]+")
_ITEM_SPLIT = re.compile(r"\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d+\.)[ \t])")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_BULLET = re.compile(r"^(?:[-*+]|\d+\.)\s+")


@dataclass(frozen=True)
class ProseIssue:
    kind: Literal["long-sentence", "filler"]
    excerpt: str
    words: int | None = None

    def __str__(self) -> str:
        if self.kind == "long-sentence":
            return f"sentence of {self.words} words (max {MAX_SENTENCE_WORDS}): {self.excerpt}"
        return f"filler word {self.excerpt!r}"


def _prose_only(text: str) -> str:
    """Drop everything that is not prose: code, embeds, quotes, tables, headings."""
    text = _FRONT_MATTER.sub("", text)
    for pattern in (_FENCE, _EMBED, _COMMENT):
        text = pattern.sub("", text)
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(("#", "|"))]
    text = "\n".join(lines)
    for pattern in (_INLINE_CODE, _QUOTED, _URL):
        text = pattern.sub("", text)
    return text


def _excerpt(sentence: str, limit: int = 80) -> str:
    flat = " ".join(sentence.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def lint_prose(text: str) -> list[ProseIssue]:
    """Long sentences, then filler words, in the order they are found."""
    prose = _prose_only(text)
    issues: list[ProseIssue] = []
    for item in _ITEM_SPLIT.split(prose):
        flat = _BULLET.sub("", " ".join(item.split()))
        for sentence in _SENTENCE_SPLIT.split(flat):
            count = len(_WORD.findall(sentence))
            if count > MAX_SENTENCE_WORDS:
                issues.append(ProseIssue("long-sentence", _excerpt(sentence), count))
    flat_prose = " ".join(prose.split()).lower()
    for word in FILLER_WORDS:
        if re.search(rf"\b{re.escape(word.lower())}\b", flat_prose):
            issues.append(ProseIssue("filler", word))
    return issues
