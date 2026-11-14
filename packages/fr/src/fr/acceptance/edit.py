"""Textual writes into an acceptance fragment (`docs/acceptance/features/<slug>.yaml`,
spec 2026-11-04 R16) — the ONE place that renders a row block. (It wrote the retired
`matrix.yaml` before R19; a fragment keeps the same `rows:` shape.)

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
from typing import TYPE_CHECKING

import yaml

from fr.acceptance.model import LEVELS, AcceptanceError, Row

if TYPE_CHECKING:
    from fr.acceptance.fragment import Amendment

_ROWS_KEY_RE = re.compile(r"^rows:\s*(#.*)?$")
_ITEM_RE = re.compile(r"^(\s*)-\s")


def render_row_block(row: Row, indent: str = "  ") -> str:
    """One row as the YAML list item this file stores, every line prefixed
    with `indent` — the indentation the file's existing items use (gh#470: a
    flush-left `rows:` sequence, PyYAML's own default, is valid YAML, and an
    item indented deeper than its siblings parses as part of the row above).

    Empty levels are dropped (`levels: {}`) rather than written as four empty
    lists — what `add` has always emitted, kept identical here.
    """
    data: dict[str, object] = {
        "id": row.id,
        "capability": row.capability,
        "acceptance": row.acceptance,
        "origin": list(row.origin),
        "levels": {lv: list(refs) for lv, refs in row.levels.items() if refs},
        "status": row.status,
        "notes": row.notes,
    }
    if row.verify is not None:  # absent when unset: older rows stay byte-identical
        data["verify"] = row.verify
    if row.visual is not None:  # absent when unset: older rows stay byte-identical
        visual_data: dict[str, list[str]] = {}
        if row.visual.states:
            visual_data["states"] = list(row.visual.states)
        if row.visual.interactions:
            visual_data["interactions"] = list(row.visual.interactions)
        data["visual"] = visual_data
    # Matrix kind 4 (spec 2026-10-06 §B): each absent when unset, so a row that
    # carries none of them renders exactly as it did at kind 3.
    if row.scenario is not None:
        data["scenario"] = row.scenario
    if row.issues:
        data["issues"] = list(row.issues)
    if row.harnesses:
        data["harnesses"] = list(row.harnesses)
    if row.walks:
        data["walks"] = [w.model_dump() for w in row.walks]
    block = yaml.dump([data], default_flow_style=False, sort_keys=False, allow_unicode=True)
    return "".join(
        (indent + line if line.strip() else line) + "\n" for line in block.rstrip("\n").split("\n")
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
        if not line[:1].isspace() and not line.startswith("#"):
            # a following top-level key ends `rows:`; a comment is not a key
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


def _item_indent(text: str) -> str:
    """The indentation of the existing items under `rows:` — `"  "` when there
    are none yet, which is what `fr acceptance init` has always written."""
    blocks = _row_blocks(text)
    if not blocks:
        return "  "
    first = text.splitlines()[blocks[0][0]]
    return first[: len(first) - len(first.lstrip())]


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
        # A new capability goes at the end of `rows:` — before a later top-level
        # key (a fragment's `amendments:`), else at the end of the file.
        lines = text.splitlines(keepends=True)
        end = _rows_end(lines)
        head = "".join(lines[:end])
        if head and not head.endswith("\n"):
            head += "\n"
        return head + render_row_block(row, _item_indent(text)) + "".join(lines[end:])
    lines = text.splitlines(keepends=True)
    start, end = same[-1]
    item_indent = len(lines[start]) - len(lines[start].lstrip())
    while end - 1 > start and _is_between_rows(lines[end - 1], item_indent):
        end -= 1
    head = "".join(lines[:end])
    if not head.endswith("\n"):
        head += "\n"
    return head + render_row_block(row, lines[start][:item_indent]) + "".join(lines[end:])


def _rows_end(lines: list[str]) -> int:
    """The line index `rows:` ends at: the first later top-level key, else the end."""
    rows_at = next((i for i, ln in enumerate(lines) if _ROWS_KEY_RE.match(ln)), None)
    if rows_at is None:
        raise AcceptanceError("matrix has no top-level `rows:` key")
    for i in range(rows_at + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line[:1].isspace() and not line.startswith(("#", "-")):
            return i
    return len(lines)


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

    The blank and comment lines that end the old block introduce the NEXT row
    (a block's span runs to the next item), so they are kept — the file's
    spacing and its section comments survive a flip.
    """
    lines = text.splitlines(keepends=True)
    start, end = _row_span(text, row_id)
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    tail: list[str] = []
    while end - 1 > start and _is_between_rows(lines[end - 1], len(indent)):
        end -= 1
        tail.insert(0, lines[end])
    return (
        "".join(lines[:start])
        + render_row_block(row, indent)
        + "".join(tail)
        + "".join(lines[end:])
    )


def _refuse_unknown_levels(keys: Iterable[str]) -> None:
    """Refuse any level key outside `LEVELS`, for an addition and a drop alike:
    either way the edit would touch a level no row carries, so it would do
    nothing while reporting success (gh#654)."""
    unknown = set(keys) - set(LEVELS)
    if unknown:
        raise AcceptanceError(
            f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS)}) "
            "— refs under an unknown level are neither added nor removed"
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


def describe_move(old: Row, new: Row) -> str:
    """What a set-status rewrite of `old` into `new` changed, in one phrase.

    A moved status reads as the transition (`unwired → ci`). An unchanged one
    names what did change instead (gh#769): `unwired → unwired` in the log
    reads as a status move that never happened, the silent-looking change the
    acceptance-matrix rule exists to keep out.
    """
    if old.status != new.status:
        return f"{old.status} → {new.status}"
    before = {(lv, ref) for lv, refs in old.levels.items() for ref in refs}
    after = {(lv, ref) for lv, refs in new.levels.items() for ref in refs}
    parts = [
        f"{sign}{n} level ref{'s' if n != 1 else ''}"
        for sign, n in (("+", len(after - before)), ("-", len(before - after)))
        if n
    ]
    if new.notes != old.notes:
        parts.append("notes")
    if new.verify != old.verify:
        parts.append(f"verify: {new.verify}")
    if new.scenario != old.scenario:
        parts.append("scenario")
    if added := len(new.issues) - len(old.issues):
        parts.append(f"+{added} issue{'s' if added != 1 else ''}")
    if added := len(new.harnesses) - len(old.harnesses):
        parts.append(f"+{added} harness{'es' if added != 1 else ''}")
    for walk in new.walks[len(old.walks) :]:
        parts.append(f"walk {walk.outcome} on {walk.harness}")
    return f"{new.status} ({', '.join(parts) or 'unchanged'})"


FRAGMENT_HEADER = """\
# Acceptance rows owned by one feature (spec 2026-11-04-repo-feature-settings R16).
# The effective matrix is a fold over every fragment in this directory
# (`fr acceptance status`); it is never stored. Write rows with
# `fr acceptance add` / `set-status`, never by hand. Keep `rows:` before
# `amendments:`.
"""


def remove_row(text: str, row_id: str) -> str:
    """`text` without `row_id`'s block, every other byte kept (the lines that end the
    block introduce the next row, as in `replace_row`, so they stay)."""
    lines = text.splitlines(keepends=True)
    start, end = _row_span(text, row_id)
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    while end - 1 > start and _is_between_rows(lines[end - 1], len(indent)):
        end -= 1
    return "".join(lines[:start]) + "".join(lines[end:])


def render_fragment(feature: str, repo: str, rows: Iterable[Row]) -> str:
    """A whole fragment's text: the header, its identity, then every row through
    `render_row_block` — the one renderer, so a fragment re-rendered from its own
    parse is byte-identical (spec 2026-11-04 R19)."""
    body = "".join(render_row_block(row) for row in rows)
    return f"{FRAGMENT_HEADER}schema_version: 1\nfeature: {feature}\nrepo: {repo}\nrows:\n{body}"


_AMENDMENTS_KEY_RE = re.compile(r"^amendments:\s*(#.*)?$")
_AMENDMENT_KEY_ORDER = ("row", "op", "base")


def render_amendment_block(amendment: Amendment, indent: str = "  ") -> str:
    """One amendment as the list item a fragment's `amendments:` stores: `row`, `op`
    and `base` first, `why` last, unset fields absent (spec 2026-11-04 §3.D)."""
    data = amendment.model_dump(mode="json", exclude_none=True)
    if not data.get("issues"):
        data.pop("issues", None)
    why = data.pop("why")
    ordered = {k: data.pop(k) for k in _AMENDMENT_KEY_ORDER}
    block = yaml.dump(
        [{**ordered, **data, "why": why}],
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return "".join(
        (indent + line if line.strip() else line) + "\n" for line in block.rstrip("\n").split("\n")
    )


def _amendment_starts(lines: list[str]) -> tuple[int | None, list[int], int]:
    """(the `amendments:` line, each item's first line, where the list ends)."""
    at = next((i for i, ln in enumerate(lines) if _AMENDMENTS_KEY_RE.match(ln)), None)
    if at is None:
        return None, [], len(lines)
    starts: list[int] = []
    indent: str | None = None
    end = len(lines)
    for i in range(at + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        m = _ITEM_RE.match(line)
        if m and (indent is None or m.group(1) == indent):
            indent = m.group(1)
            starts.append(i)
            continue
        if not line[:1].isspace() and not line.startswith("#"):
            end = i
            break
    return at, starts, end


def append_amendment(text: str, amendment: Amendment) -> str:
    """*text* with *amendment* appended to its `amendments:` list (created at the end
    of the file when absent); every existing byte is kept (R16: append-only)."""
    lines = text.splitlines(keepends=True)
    at, starts, end = _amendment_starts(lines)
    if at is None:
        head = text if not text or text.endswith("\n") else text + "\n"
        return head + "amendments:\n" + render_amendment_block(amendment)
    indent = "  "
    if starts:
        first = lines[starts[0]]
        indent = first[: len(first) - len(first.lstrip())]
    while end - 1 > at and not lines[end - 1].strip():
        end -= 1
    head = "".join(lines[:end])
    if not head.endswith("\n"):
        head += "\n"
    return head + render_amendment_block(amendment, indent) + "".join(lines[end:])


def rebase_amendment(text: str, index: int, base: int) -> str:
    """*text* with the `index`-th amendment's `base` set to *base*, every other line
    kept: how `fr acceptance amend --rebase` answers R17's stale-base refusal."""
    lines = text.splitlines(keepends=True)
    at, starts, end = _amendment_starts(lines)
    if at is None or index >= len(starts):
        raise AcceptanceError(f"no amendment at index {index}")
    stop = starts[index + 1] if index + 1 < len(starts) else end
    for i in range(starts[index], stop):
        m = re.match(r"^(\s*(?:-\s+)?)base:\s*\d+\s*$", lines[i])
        if m:
            lines[i] = f"{m.group(1)}base: {base}\n"
            return "".join(lines)
    raise AcceptanceError(f"amendment {index} carries no `base:` line")
