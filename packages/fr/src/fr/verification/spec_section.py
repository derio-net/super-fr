"""A spec's `## Verification` section — spec 2026-10-06 §B (R6).

One section in a fixed grammar, read by `fr plan self-review`, the walk and the
PR body (never compared as strings by those consumers — they call
`fr.verification.effective`):

    ## Verification

    strategy: candidate
    gate: <gate>                 (optional, run-level; spec 2026-10-14 R5)
    gate: <row-id>=<gate>        (optional, one row each)
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

from fr.gates import GATES

_HEADING = re.compile(r"^##\s+Verification\s*$")
_ANY_H2 = re.compile(r"^##\s")
_FENCE = re.compile(r"^\s*(```|~~~)")
_NAME = r"[a-z][a-z0-9-]*"
_STRATEGY_LINE = re.compile(rf"^strategy:\s*(?P<name>{_NAME})\s*$")
_ROW_LINE = re.compile(
    rf"^-\s+(?P<row>[A-Za-z0-9][A-Za-z0-9._-]*):\s+(?P<strategy>{_NAME})"
    r"(?:\s+—\s+(?P<reason>\S.*?))?\s*$"
)
_GATE_LINE = re.compile(
    r"^gate:\s*(?:(?P<row>[A-Za-z0-9][A-Za-z0-9._-]*)=)?(?P<gate>[a-z][a-z0-9-]*)\s*$"
)
GATE_NAMES = GATES | {"none"}
"""What a `gate:` line may name: the closed vocabulary, or `none` (no gate)."""


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
    gate: str | None = None
    row_gates: dict[str, str] = field(default_factory=dict)


def _section_span(text: str) -> tuple[int, list[tuple[int, str]]] | None:
    """`(heading line number, [(line number, line)])` of the section, or `None`
    without a section.

    Fenced code is skipped, so a spec that QUOTES the grammar in a code block
    (as the design spec does) is not mistaken for carrying the section.
    """
    heading = 0
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
                heading, body = n, []
        elif _ANY_H2.match(line):
            break
        else:
            body.append((n, line))
    return None if body is None else (heading, body)


def _section_lines(text: str) -> list[tuple[int, str]] | None:
    """`(line number, line)` of the section body, or `None` without a section."""
    span = _section_span(text)
    return None if span is None else span[1]


def _is_grammar(line: str) -> bool:
    """Does `line` belong to the grammar: any `strategy:` line, or a bullet the
    row grammar accepts?"""
    return line.startswith(("strategy:", "gate:")) or _ROW_LINE.match(line) is not None


def parse_section(text: str) -> Section | None:
    """The spec's `## Verification` section, or `None` when it has none (or
    only a pre-grammar prose one)."""
    lines = _section_lines(text)
    if lines is None or not any(_is_grammar(raw.strip()) for _, raw in lines):
        return None

    strategy: str | None = None
    gate: str | None = None
    row_gates: dict[str, str] = {}
    rows: dict[str, RowLine] = {}
    for n, raw in lines:
        line = raw.strip()
        if line.startswith("gate:"):
            m = _GATE_LINE.match(line)
            if m is None or m["gate"] not in GATE_NAMES:
                raise SectionError(
                    f"line {n}: malformed `gate:` line: {raw!r} — expected `gate: <gate>` or "
                    f"`gate: <row-id>=<gate>` with a gate of {sorted(GATE_NAMES)}"
                )
            if m["row"] is None:
                if gate is not None:
                    raise SectionError(f"line {n}: a second `gate:` line (already {gate!r})")
                gate = m["gate"]
            else:
                if m["row"] in row_gates:
                    raise SectionError(f"line {n}: row {m['row']!r} has more than one `gate:` line")
                row_gates[m["row"]] = m["gate"]
        elif line.startswith("strategy:"):
            m = _STRATEGY_LINE.match(line)
            if m is None:
                raise SectionError(
                    f"line {n}: malformed `strategy:` line: {raw!r} — it holds only the name "
                    "(`strategy: <name>`); put reasons on the per-row lines "
                    "(`- <row-id>: <strategy|none> — <reason>`)"
                )
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
    return Section(strategy=strategy, rows=rows, gate=gate, row_gates=row_gates)


_NO_SECTION = (
    "the spec has no `## Verification` section: add one — a `## Verification` heading, "
    "then `strategy: <name>` (and `- <row-id>: <strategy|none> — <reason>` lines, or "
    "`gate: <gate>`) — and run this again"
)


def _eol(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""


def _replace(lines: list[str], n: int, content: str) -> None:
    lines[n - 1] = content + _eol(lines[n - 1])


def _insert(lines: list[str], at: int, content: str, eol: str) -> None:
    """Put `content` as the line at index `at`, giving a last line that lacked a
    line ending one first."""
    if at > 0 and not _eol(lines[at - 1]):
        lines[at - 1] += eol
        lines.insert(at, content)
    else:
        lines.insert(at, content + eol)


def _set_line(text: str, kind: str, row: str | None, content: str) -> str:
    """Rewrite the section's one `kind` line (`strategy` | `gate` | `bullet`, for
    `row` where it has one) to `content`, or insert it beside its kind."""
    span = _section_span(text)
    if span is None:
        raise SectionError(_NO_SECTION)
    heading, body = span
    lines = text.splitlines(keepends=True)
    eol = _eol(lines[heading - 1]) or "\n"
    stripped = [(n, raw.strip()) for n, raw in body]

    def gate_row(line: str) -> str | None:
        m = _GATE_LINE.match(line) if line.startswith("gate:") else None
        return m["row"] if m is not None else None

    def is_gate(line: str) -> bool:
        return line.startswith("gate:") and _GATE_LINE.match(line) is not None

    def bullet_row(line: str) -> str | None:
        m = _ROW_LINE.match(line)
        return m["row"] if m is not None else None

    if kind == "strategy":
        hit = next((n for n, ln in stripped if ln.startswith("strategy:")), None)
    elif kind == "gate":
        hit = next(
            (n for n, ln in stripped if is_gate(ln) and gate_row(ln) == row),
            None,
        )
    else:
        hit = next((n for n, ln in stripped if bullet_row(ln) == row), None)
    if hit is not None:
        if kind == "bullet":
            # An existing bullet keeps its rationale; only a new one carries `reason`.
            old = _ROW_LINE.match(dict(stripped)[hit])
            if old is not None and old["reason"]:
                content = content.split(" — ", 1)[0] + f" — {old['reason']}"
            else:
                content = content.split(" — ", 1)[0]
        _replace(lines, hit, content)
        return "".join(lines)

    def last(pred: object) -> int | None:
        found = [n for n, ln in stripped if pred(ln)]  # type: ignore[operator]
        return found[-1] if found else None

    first_grammar = next((n for n, ln in stripped if _is_grammar(ln)), None)
    after: int | None  # insert after this line number; None = before the first grammar line
    if kind == "strategy":
        after = None
    elif kind == "gate" and row is None:
        after = last(lambda ln: ln.startswith("strategy:"))
    elif kind == "gate":
        after = last(is_gate) or last(lambda ln: ln.startswith("strategy:"))
    else:
        after = last(lambda ln: bullet_row(ln) is not None) or last(_is_grammar)
    if after is not None:
        _insert(lines, after, content, eol)
    elif first_grammar is not None:
        _insert(lines, first_grammar - 1, content, eol)
    else:
        at = heading  # after the heading and the blank lines that follow it
        while at < len(lines) and not lines[at].strip():
            at += 1
        nxt_is_h2 = at < len(lines) and _ANY_H2.match(lines[at]) is not None
        _insert(lines, at, content, eol)
        if at + 1 < len(lines) and lines[at + 1].strip() and not nxt_is_h2:
            lines.insert(at + 1, eol)  # keep the prose a paragraph apart
    return "".join(lines)


def rewrite_section(
    text: str,
    *,
    strategy: str | None = None,
    row: str | None = None,
    gate: str | None = None,
    reason: str | None = None,
) -> str:
    """`text` with the section's matching grammar line inserted or rewritten and
    every other byte kept (`fr verification set`, spec 2026-10-14 R8).

    Without `row`: `strategy` sets the `strategy:` line and `gate` the run-level
    `gate:` line. With `row`: `strategy` sets that row's bullet (`reason` after
    the em dash) and `gate` its `gate: <row>=` line. `SectionError` for no
    section, a name outside the grammar, or a reason that is not one line."""
    if strategy is not None and re.fullmatch(_NAME, strategy) is None:
        raise SectionError(f"strategy {strategy!r} is not a strategy name (lowercase, dashes)")
    if gate is not None and gate not in GATE_NAMES:
        raise SectionError(f"gate {gate!r} is not one of {sorted(GATE_NAMES)}")
    if row is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", row) is None:
        raise SectionError(f"{row!r} is not a row id")
    if reason is not None and (not reason.strip() or "\n" in reason or "\r" in reason):
        raise SectionError("the reason must be one non-empty line")
    out = text
    if strategy is not None:
        if row is None:
            out = _set_line(out, "strategy", None, f"strategy: {strategy}")
        else:
            tail = f" — {reason.strip()}" if reason else ""
            out = _set_line(out, "bullet", row, f"- {row}: {strategy}{tail}")
    if gate is not None:
        content = f"gate: {gate}" if row is None else f"gate: {row}={gate}"
        out = _set_line(out, "gate", row, content)
    if out == text and _section_span(text) is None:
        raise SectionError(_NO_SECTION)
    return out
