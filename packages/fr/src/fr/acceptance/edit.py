"""Textual writes into `matrix.yaml` — the ONE place that renders a row block.

`fr acceptance add` appends and `fr acceptance set-status` replaces; both come
through here, so the two cannot disagree about the file's shape. Every write is
line surgery on the original text rather than a `yaml.safe_dump` round trip: a
dump would reflow the header comments (23 lines of schema documentation), the
key order and the blank lines of EVERY row in the file, turning a one-row flip
into an unreviewable diff.

What that buys, precisely (review r7-m1 measured it, so the claim is not
overstated): every row *other* than the edited one survives byte-identically.
The edited row is fully re-rendered, so a hand-authored folded scalar may come
back single-quoted and re-wrapped — on the real 114-row matrix, 63 rows would
not be byte-identical after a self-replace, the worst producing a 79-line diff
for a status flip. That churn is confined to the row you asked to change, and
is semantically identical (`yaml.safe_load` equal before and after). Narrowing
it further would mean a round-tripping YAML library, which is not worth a
dependency.

Spec: `docs/superpowers/specs/2026-09-18-harness-parity-matrix-design.md` §3.G.2.
"""

from __future__ import annotations

import re

import yaml

from fr.acceptance.model import LEVELS, AcceptanceError, Row

_ROWS_KEY_RE = re.compile(r"^rows:\s*(#.*)?$")
_ITEM_RE = re.compile(r"^(\s*)-\s")


def render_row_block(row: Row) -> str:
    """One row as the indented YAML list item this file stores.

    Empty levels are dropped (`levels: {}`) rather than written as four empty
    lists — what `add` has always emitted, kept identical here.
    """
    data = {
        "id": row.id,
        "capability": row.capability,
        "acceptance": row.acceptance,
        "origin": list(row.origin),
        "levels": {lv: list(refs) for lv, refs in row.levels.items() if refs},
        "status": row.status,
        "notes": row.notes,
    }
    block = yaml.dump([data], default_flow_style=False, sort_keys=False, allow_unicode=True)
    return "".join(
        ("  " + line if line.strip() else line) + "\n" for line in block.rstrip("\n").split("\n")
    )


def append_row(text: str, row: Row) -> str:
    """`text` with `row` appended as the last item of `rows:`."""
    body = text if text.endswith("\n") else text + "\n"
    return body + render_row_block(row)


def _row_span(text: str, row_id: str) -> tuple[int, int]:
    """`(start, end)` line indices of `row_id`'s block, end-exclusive.

    Found by parsing each list item under `rows:`, never by pattern-matching
    `id: <row_id>` — a row whose *notes* quote another row's id would otherwise
    hijack the span, and that is the class of silent mis-edit this module is
    written to avoid.
    """
    lines = text.splitlines(keepends=True)
    rows_at = next((i for i, ln in enumerate(lines) if _ROWS_KEY_RE.match(ln)), None)
    if rows_at is None:
        raise AcceptanceError("matrix has no top-level `rows:` key")

    starts: list[int] = []
    indent: str | None = None
    end_of_rows = len(lines)
    for i in range(rows_at + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        m = _ITEM_RE.match(line)
        if m and (indent is None or m.group(1) == indent):
            indent = m.group(1)
            starts.append(i)
            continue
        if not line[:1].isspace():  # a following top-level key ends `rows:`
            end_of_rows = i
            break

    bounds = [(s, e) for s, e in zip(starts, starts[1:] + [end_of_rows], strict=True)]
    for start, end in bounds:
        block = "".join(lines[start:end])
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as e:
            raise AcceptanceError(f"row block at line {start + 1} is not valid YAML: {e}") from e
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            if parsed[0].get("id") == row_id:
                return start, end
    raise AcceptanceError(f"no row with id {row_id!r}")


def replace_row(text: str, row_id: str, row: Row) -> str:
    """`text` with `row_id`'s block replaced by `row`'s, every other byte kept.

    Trailing blank lines inside the old block are preserved, so the file's
    spacing survives a flip.
    """
    lines = text.splitlines(keepends=True)
    start, end = _row_span(text, row_id)
    tail: list[str] = []
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
        tail.insert(0, lines[end])
    return "".join(lines[:start]) + render_row_block(row) + "".join(tail) + "".join(lines[end:])


def merge_levels(
    existing: dict[str, tuple[str, ...]], additions: dict[str, list[str]]
) -> dict[str, tuple[str, ...]]:
    """Existing level refs plus `additions`, in order, without duplicates.

    Additive because the documented transition is "add the ref to `levels`,
    move `status` up" (`.claude/rules/acceptance-matrix.md`): evidence
    accumulates as more levels come to verify a row. Removing a ref stays a
    deliberate edit, not something a status flip does silently.
    """
    unknown = set(additions) - set(LEVELS)
    if unknown:
        raise AcceptanceError(
            f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS)}) "
            "— a typo would silently drop refs"
        )
    merged: dict[str, tuple[str, ...]] = {}
    for lv in LEVELS:
        seen = list(existing.get(lv, ()))
        for ref in additions.get(lv, []):
            if ref not in seen:
                seen.append(ref)
        merged[lv] = tuple(seen)
    return merged
