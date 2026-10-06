"""A spec's `## Verification` section — spec 2026-10-06 §B (R6).

One section in a fixed grammar, read by `fr plan self-review`, the walk and the
PR body (never compared as strings by those consumers — they call
`fr.verification.effective`):

    ## Verification

    strategy: candidate
    - <row-id>: <strategy|none> — <reason>

The `strategy:` line is optional (the shape's default stands in). The reason
after the em dash is optional HERE: whether one is owed depends on the
strategy's manifest (post-merge or `none`), which is `plan self-review`'s check,
not the grammar's. Any other line — prose, blank lines — is ignored, so the
section can explain itself; a line that LOOKS like the grammar (a bullet or a
`strategy:` line) but breaks it is an error naming the line.

A section with NO grammar line at all — no `strategy:` line, no bullet the row
grammar accepts — is not this section (review p3-r6): specs older than the
grammar used `## Verification` for prose bullets, and an in-flight run whose
spec is one of them must deliver unchanged, not fail closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^##\s+Verification\s*$")
_ANY_H2 = re.compile(r"^##\s")
_FENCE = re.compile(r"^\s*(```|~~~)")
_NAME = r"[a-z][a-z0-9-]*"
_STRATEGY_LINE = re.compile(rf"^strategy:\s*(?P<name>{_NAME})\s*$")
_ROW_LINE = re.compile(
    rf"^-\s+(?P<row>[A-Za-z0-9][A-Za-z0-9._-]*):\s+(?P<strategy>{_NAME})"
    r"(?:\s+—\s+(?P<reason>\S.*?))?\s*$"
)


class SectionError(ValueError):
    """A line of the `## Verification` section that breaks the grammar."""


@dataclass(frozen=True)
class RowLine:
    strategy: str
    reason: str | None


@dataclass(frozen=True)
class Section:
    strategy: str | None = None
    rows: dict[str, RowLine] = field(default_factory=dict)


def _section_lines(text: str) -> list[tuple[int, str]] | None:
    """`(line number, line)` of the section body, or `None` without a section.

    Fenced code is skipped, so a spec that QUOTES the grammar in a code block
    (as the design spec does) is not mistaken for carrying the section.
    """
    body: list[tuple[int, str]] | None = None
    fenced = False
    for n, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if body is None:
            if _HEADING.match(line):
                body = []
        elif _ANY_H2.match(line):
            break
        else:
            body.append((n, line))
    return body


def _is_grammar(line: str) -> bool:
    """Does `line` belong to the grammar: any `strategy:` line, or a bullet the
    row grammar accepts?"""
    return line.startswith("strategy:") or _ROW_LINE.match(line) is not None


def parse_section(text: str) -> Section | None:
    """The spec's `## Verification` section, or `None` when it has none (or
    only a pre-grammar prose one)."""
    lines = _section_lines(text)
    if lines is None or not any(_is_grammar(raw.strip()) for _, raw in lines):
        return None

    strategy: str | None = None
    rows: dict[str, RowLine] = {}
    for n, raw in lines:
        line = raw.strip()
        if line.startswith("strategy:"):
            m = _STRATEGY_LINE.match(line)
            if m is None:
                raise SectionError(f"line {n}: malformed `strategy:` line: {raw!r}")
            if strategy is not None:
                raise SectionError(f"line {n}: a second `strategy:` line (already {strategy!r})")
            strategy = m["name"]
        elif line.startswith("- "):
            m = _ROW_LINE.match(line)
            if m is None:
                raise SectionError(
                    f"line {n}: malformed row line {raw!r} "
                    "(expected `- <row-id>: <strategy|none> — <reason>`)"
                )
            if m["row"] in rows:
                raise SectionError(f"line {n}: row {m['row']!r} appears more than once")
            rows[m["row"]] = RowLine(m["strategy"], m["reason"])
    return Section(strategy=strategy, rows=rows)
