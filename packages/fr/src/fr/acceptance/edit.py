"""Textual writes into `matrix.yaml` — the ONE place that renders a row block.

`fr acceptance add` inserts (by capability) and `fr acceptance set-status`
replaces; both come through here, so the two cannot disagree about the file's
shape. Every write is
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
from collections.abc import Iterable, Mapping, Sequence

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


def _row_blocks(text: str) -> list[tuple[int, int, dict[str, object]]]:
    """`(start, end, parsed)` for every list item under `rows:`, end-exclusive
    line indices, in file order — the ONE scan of the row blocks that
    `insert_row` and `replace_row` both read.

    Each block is found by parsing the list items under `rows:`, never by
    pattern-matching `id:` or `capability:` lines — a row whose *notes* quote
    another row's id or capability would otherwise hijack the result, and that
    is the class of silent mis-edit this module is written to avoid. A block's
    span runs to the next item, so it includes any blank or comment lines that
    precede the next row.
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

    blocks: list[tuple[int, int, dict[str, object]]] = []
    if not starts:  # `rows:` with no items yet (a fresh skeleton)
        return blocks
    for start, end in zip(starts, starts[1:] + [end_of_rows], strict=True):
        block = "".join(lines[start:end])
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as e:
            raise AcceptanceError(f"row block at line {start + 1} is not valid YAML: {e}") from e
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            blocks.append((start, end, parsed[0]))
    return blocks


def insert_row(text: str, row: Row) -> str:
    """`text` with `row` inserted after the last row sharing its `capability`
    (spec 2026-09-26-version-bump-churn §3.H); a capability not yet present
    appends at the end of the file.

    Reports render capabilities in first-seen order and rows in matrix order,
    so this renders exactly as an append would — but two branches adding rows
    to DIFFERENT capabilities now edit different places in the file instead
    of both appending at EOF, which made every concurrent `add` a conflict.

    The new block goes directly after the last content line of that row, so
    the blank or comment lines introducing the next row stay attached to it.
    Every existing byte is kept.
    """
    same = [
        (s, e) for s, e, parsed in _row_blocks(text) if parsed.get("capability") == row.capability
    ]
    if not same:
        body = text if text.endswith("\n") else text + "\n"
        return body + render_row_block(row)
    lines = text.splitlines(keepends=True)
    start, end = same[-1]
    item_indent = len(lines[start]) - len(lines[start].lstrip())
    while end - 1 > start and _is_between_rows(lines[end - 1], item_indent):
        end -= 1
    head = "".join(lines[:end])
    if not head.endswith("\n"):
        head += "\n"
    return head + render_row_block(row) + "".join(lines[end:])


def _is_between_rows(line: str, item_indent: int) -> bool:
    """A blank line, or a comment no deeper than the `- ` of a row item —
    what sits between rows. A deeper line starting with `#` is NOT one: it can
    be the continuation of a multi-line scalar (the real matrix has notes
    whose wrapped line begins `#352, ...`), and moving it would break the row.
    """
    stripped = line.strip()
    if not stripped:
        return True
    return stripped.startswith("#") and len(line) - len(line.lstrip()) <= item_indent


def _row_span(text: str, row_id: str) -> tuple[int, int]:
    """`(start, end)` line indices of `row_id`'s block, end-exclusive."""
    for start, end, parsed in _row_blocks(text):
        if parsed.get("id") == row_id:
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


def _refuse_unknown_levels(keys: Iterable[str]) -> None:
    """Refuse any level key outside `LEVELS` — a typo would silently drop refs."""
    unknown = set(keys) - set(LEVELS)
    if unknown:
        raise AcceptanceError(
            f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS)}) "
            "— a typo would silently drop refs"
        )


def merge_levels(
    existing: dict[str, tuple[str, ...]], additions: dict[str, list[str]]
) -> dict[str, tuple[str, ...]]:
    """Existing level refs plus `additions`, in order, without duplicates.

    Additive because the documented transition is "add the ref to `levels`,
    move `status` up" (`.claude/rules/acceptance-matrix.md`): evidence
    accumulates as more levels come to verify a row. Removing a ref is
    `drop_levels`'s job — explicit, never something a status flip does
    silently.
    """
    _refuse_unknown_levels(additions)
    merged: dict[str, tuple[str, ...]] = {}
    for lv in LEVELS:
        seen = list(existing.get(lv, ()))
        for ref in additions.get(lv, []):
            if ref not in seen:
                seen.append(ref)
        merged[lv] = tuple(seen)
    return merged


def drop_levels(
    existing: Mapping[str, Sequence[str]], drops: Mapping[str, Sequence[str]]
) -> dict[str, tuple[str, ...]]:
    """Existing level refs minus `drops`, the remaining refs in their order.

    The one definition of "this ref is on the row" (gh#624): a drop naming a
    ref the row does not carry is refused, never ignored — a typo'd ref that
    silently removed nothing would leave stale evidence behind while reporting
    success. A ref named twice in `drops` is dropped once; a ref a (hand-edited)
    row carries twice loses every copy — a drop means "this evidence is no
    longer on the row". Typed over `Mapping`/`Sequence` so the CLI's parsed
    lists and the engine's `RecordTarget.acceptance_drops` tuples both pass
    straight through.
    """
    _refuse_unknown_levels(drops)
    for lv, refs in drops.items():
        current = existing.get(lv, ())
        for ref in dict.fromkeys(refs):
            if ref not in current:
                raise AcceptanceError(
                    f"cannot drop {ref!r} from level {lv!r}: the row does not carry it "
                    f"(current {lv} refs: {list(current)})"
                )
    remaining: dict[str, tuple[str, ...]] = {}
    for lv in LEVELS:
        gone = set(drops.get(lv, ()))
        remaining[lv] = tuple(ref for ref in existing.get(lv, ()) if ref not in gone)
    return remaining
