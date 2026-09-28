"""Requirements traceability: §B grammar, §C structural gate, §D coverage
partition (spec `2026-09-28-requirements-traceability-design.md`).

Phase 1 skeleton: this module is pure, no I/O. The CLI wrapper
(`fr spec requirements`, `fr.commands.spec_cmd`) is the only caller that
touches disk; `fr run resolve`'s `requirements`/`coverage` derived-evidence
wiring (spec §C/§D) lands in a later phase and calls the SAME
`check_requirements`/`check_coverage` — never a copy.

Input-entry detection (`is_input_entry`) reads `JournalEntry.input`, the
`input=true` header token (spec §A) the model allows only on a spec-scope
`discovery`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from fr.acceptance.model import AcceptanceError, Matrix, archive_twin, split_ref
from fr.journal.model import JournalEntry

# --- shapes ----------------------------------------------------------------

SourceKind = Literal["input", "decision"]


@dataclass(frozen=True)
class Source:
    """One entry of a requirement's `source` cell (§B)."""

    kind: SourceKind
    value: str
    """The verbatim quote (`kind="input"`) or the spec-journal decision id
    (`kind="decision"`)."""


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class Deferred:
    quote: str
    reason: str


@dataclass(frozen=True)
class Requirements:
    items: tuple[Requirement, ...]
    deferred: tuple[Deferred, ...] = ()


@dataclass(frozen=True)
class CoverageCounts:
    """`<n> spans: R=<a> deferred=<b> context=<c> missing=<d>` (§D)."""

    spans: int
    requirement: int
    deferred: int
    context: int
    missing: int


class RequirementsError(Exception):
    """A §B grammar violation. Every message names the 1-based spec line and
    the rule it broke."""


# --- §A: identifying an input entry -----------------------------------------


def is_input_entry(entry: JournalEntry) -> bool:
    """Whether `entry` is a raw-input spec-journal entry (§A)."""
    return entry.input


# --- §B: the table grammar --------------------------------------------------

_REQUIREMENTS_HEADING = "## Requirements"
_DEFERRED_HEADING = "## Deferred from input"
_REQUIREMENTS_HEADER = ["id", "requirement", "source"]
_DEFERRED_HEADER = ["input", "reason"]

_ID_RE = re.compile(r"^R[1-9][0-9]*$")
_INPUT_SOURCE_RE = re.compile(r'^input\s+"(.*)"$', re.DOTALL)
_DECISION_SOURCE_RE = re.compile(r"^decision\s+(\S+)$")
_DELIMITER_CELL_RE = re.compile(r"^:?-+:?$")


def _split_row(line: str, line_no: int) -> list[str]:
    """One GFM table row -> its cells: split on unescaped `|`, `\\|`
    unescaped to `|`, each cell stripped (shared by both tables and by
    `check_coverage`'s `input-coverage` block, spec §B refactor note)."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        raise RequirementsError(f"line {line_no}: not a table row: {line.strip()!r}")
    inner = s[1:-1]
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c == "\\" and i + 1 < n and inner[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def _locate_section(text: str, heading: str) -> tuple[list[str], int] | None:
    """`heading`'s body: the lines between it and the next `## ` heading (or
    EOF), plus the 1-based line number of the first of those lines. `None`
    when `heading` is absent."""
    lines = text.splitlines()
    start: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start = idx
            break
    if start is None:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return lines[start + 1 : end], start + 2


def _parse_table(
    lines: list[str], first_line_no: int, expected_header: list[str], section_name: str
) -> list[tuple[list[str], int]]:
    """A section's body -> its one table's data rows (cells, 1-based line
    number). Any content besides blank lines and exactly one well-formed
    table is a `RequirementsError` naming the offending line (§B)."""
    i = 0
    n = len(lines)
    while i < n and lines[i].strip() == "":
        i += 1
    if i >= n:
        raise RequirementsError(f"line {first_line_no}: `{section_name}` has no table")
    header_line_no = first_line_no + i
    header_cells = [c.lower() for c in _split_row(lines[i], header_line_no)]
    if header_cells != expected_header:
        raise RequirementsError(
            f"line {header_line_no}: `{section_name}` table header must be "
            f"`| {' | '.join(expected_header)} |`, got {lines[i].strip()!r}"
        )
    i += 1
    if i >= n:
        raise RequirementsError(f"line {header_line_no}: missing delimiter row after header")
    delim_line_no = first_line_no + i
    delim_cells = _split_row(lines[i], delim_line_no)
    if len(delim_cells) != len(expected_header) or not all(
        _DELIMITER_CELL_RE.match(c) for c in delim_cells
    ):
        raise RequirementsError(f"line {delim_line_no}: malformed table delimiter row")
    i += 1
    rows: list[tuple[list[str], int]] = []
    while i < n and lines[i].strip() != "" and lines[i].strip().startswith("|"):
        row_line_no = first_line_no + i
        cells = _split_row(lines[i], row_line_no)
        if len(cells) != len(expected_header):
            raise RequirementsError(
                f"line {row_line_no}: expected {len(expected_header)} columns, got {len(cells)}"
            )
        rows.append((cells, row_line_no))
        i += 1
    while i < n:
        if lines[i].strip() != "":
            raise RequirementsError(
                f"line {first_line_no + i}: `{section_name}` holds only one table — "
                f"unexpected content: {lines[i].strip()!r}"
            )
        i += 1
    return rows


def _extract_quote(cell: str, line_no: int) -> str:
    """A `"<quote>"` cell's content — first `"` to last `"` (§B: "the quote
    runs from the first `"` to the last `"` of that source")."""
    first = cell.find('"')
    last = cell.rfind('"')
    if first == -1 or last == -1 or first == last:
        raise RequirementsError(f"line {line_no}: expected a quoted string, got {cell!r}")
    return cell[first + 1 : last]


def _parse_sources(cell: str, line_no: int) -> tuple[Source, ...]:
    if not cell.strip():
        raise RequirementsError(f"line {line_no}: empty `source` cell")
    sources: list[Source] = []
    for part in cell.split("<br>"):
        part = part.strip()
        if not part:
            raise RequirementsError(f"line {line_no}: empty source in a `<br>`-separated list")
        m = _INPUT_SOURCE_RE.match(part)
        if m:
            sources.append(Source(kind="input", value=m.group(1)))
            continue
        m = _DECISION_SOURCE_RE.match(part)
        if m:
            sources.append(Source(kind="decision", value=m.group(1)))
            continue
        raise RequirementsError(f"line {line_no}: unknown source form {part!r}")
    return tuple(sources)


def parse_requirements(spec_text: str) -> Requirements:
    """Parse a spec's `## Requirements` (+ optional `## Deferred from
    input`) tables (§B). Pure, no I/O. Raises `RequirementsError` on any
    malformed input; never silently drops a row."""
    section = _locate_section(spec_text, _REQUIREMENTS_HEADING)
    if section is None:
        raise RequirementsError(f"no `{_REQUIREMENTS_HEADING}` section found")
    lines, first_line_no = section
    rows = _parse_table(lines, first_line_no, _REQUIREMENTS_HEADER, _REQUIREMENTS_HEADING)

    items: list[Requirement] = []
    seen_ids: dict[str, int] = {}
    for cells, line_no in rows:
        rid, req_text, source_cell = cells
        if not _ID_RE.match(rid):
            raise RequirementsError(
                f"line {line_no}: malformed requirement id {rid!r} "
                "(expected `R` + a positive integer)"
            )
        if rid in seen_ids:
            raise RequirementsError(
                f"line {line_no}: duplicate requirement id {rid!r} "
                f"(first seen at line {seen_ids[rid]})"
            )
        seen_ids[rid] = line_no
        if not req_text:
            raise RequirementsError(f"line {line_no}: requirement {rid} has an empty cell")
        sources = _parse_sources(source_cell, line_no)
        items.append(Requirement(id=rid, text=req_text, sources=sources))

    deferred: list[Deferred] = []
    deferred_section = _locate_section(spec_text, _DEFERRED_HEADING)
    if deferred_section is not None:
        d_lines, d_first_line_no = deferred_section
        d_rows = _parse_table(d_lines, d_first_line_no, _DEFERRED_HEADER, _DEFERRED_HEADING)
        for cells, line_no in d_rows:
            input_cell, reason = cells
            quote = _extract_quote(input_cell, line_no)
            if not reason:
                raise RequirementsError(f"line {line_no}: Deferred entry has an empty `reason`")
            deferred.append(Deferred(quote=quote, reason=reason))

    return Requirements(items=tuple(items), deferred=tuple(deferred))


# --- §B: quote matching ------------------------------------------------------

ELLIPSIS = " … "
"""U+2026 with a space on each side elides within a quote (§B)."""


def normalise(text: str) -> str:
    """Collapse whitespace runs (newlines included) to one space; strip
    ends. Case, punctuation and dashes stay literal (§B: "1–20" != "1-20")."""
    return re.sub(r"\s+", " ", text).strip()


def _strip_ws(text: str) -> str:
    """All whitespace removed — the coverage partition's comparison form (§D)."""
    return re.sub(r"\s+", "", text)


def quote_matches(quote: str, body: str) -> bool:
    """Does `quote` (optionally eliding with `ELLIPSIS`) occur, in order, in
    `body`? Both sides whitespace-normalised first (§B)."""
    fragments = [f for f in normalise(quote).split(ELLIPSIS) if f]
    if not fragments:
        return False
    norm_body = normalise(body)
    pos = 0
    for frag in fragments:
        idx = norm_body.find(frag, pos)
        if idx == -1:
            return False
        pos = idx + len(frag)
    return True


# --- §C: check_requirements --------------------------------------------------


def check_requirements(
    spec_text: str,
    entries: Sequence[Any],
    matrix: Matrix,
    spec_ref: str,
) -> list[str]:
    """The §C structural gate: problems with the spec's Requirements capture,
    empty when sound. `spec_ref` is `<repo>:<spec-path>` (no fragment) — a
    requirement `R<n>` is cited when a matrix row's `origin` names
    `spec_ref#R<n>` (its archive twin resolves too)."""
    problems: list[str] = []

    input_entries = [e for e in entries if is_input_entry(e)]
    if not input_entries:
        problems.append(
            "no input entry (a `kind=discovery` entry carrying `input`) found in the spec journal"
        )

    decision_ids = {e.id for e in entries if getattr(e, "kind", None) == "decision"}

    try:
        parsed = parse_requirements(spec_text)
    except RequirementsError as exc:
        problems.append(f"`{_REQUIREMENTS_HEADING}`: {exc}")
        return problems

    if not parsed.items:
        problems.append(f"`{_REQUIREMENTS_HEADING}` has no items")

    ref_repo, _, ref_path = spec_ref.partition(":")

    def _cited(req_id: str) -> bool:
        for row in matrix.rows:
            for origin in row.origin:
                try:
                    r, p, frag = split_ref(origin)
                except AcceptanceError:
                    continue
                if r != ref_repo or frag != req_id:
                    continue
                if p == ref_path or archive_twin(p) == ref_path or p == archive_twin(ref_path):
                    return True
        return False

    def _quote_ok(quote: str) -> bool:
        return any(quote_matches(quote, ie.body) for ie in input_entries)

    for req in parsed.items:
        for src in req.sources:
            if src.kind == "input":
                if not _quote_ok(src.value):
                    problems.append(
                        f"requirement {req.id}: quoted input {src.value!r} does not match "
                        "any input entry in the spec journal"
                    )
            else:
                if src.value not in decision_ids:
                    problems.append(
                        f"requirement {req.id}: source cites decision {src.value!r}, which "
                        "is not a `kind=decision` entry in the spec journal"
                    )
        if not _cited(req.id):
            problems.append(
                f"requirement {req.id}: not cited by any matrix row origin ({spec_ref}#{req.id})"
            )

    for d in parsed.deferred:
        if not _quote_ok(d.quote):
            problems.append(
                f"Deferred entry {d.quote!r}: does not match any input entry in the spec journal"
            )

    return problems


# --- §D: check_coverage -------------------------------------------------------

_COVERAGE_BLOCK_RE = re.compile(r"```input-coverage\r?\n(.*?)```", re.DOTALL)
_COVERAGE_HEADER = ["span", "coverage"]
_REQ_LABEL_RE = re.compile(r"^R[1-9][0-9]*(,\s*R[1-9][0-9]*)*$")
_MISSING_LABEL_RE = re.compile(r"^missing\s+(\S+)$")


def check_coverage(
    review_body: str,
    input_entries: Sequence[Any],
    requirements: Requirements,
    entries: Sequence[Any],
) -> tuple[list[str], CoverageCounts]:
    """The §D coverage-partition gate: problems (empty when sound) and the
    counts to record. Verifies the partition is complete, not that any span
    is labelled correctly (that stays reviewer judgement)."""
    problems: list[str] = []
    empty_counts = CoverageCounts(spans=0, requirement=0, deferred=0, context=0, missing=0)

    blocks = _COVERAGE_BLOCK_RE.findall(review_body)
    if len(blocks) == 0:
        problems.append("no `input-coverage` block found in the review body")
        return problems, empty_counts
    if len(blocks) > 1:
        problems.append(f"expected exactly one `input-coverage` block, found {len(blocks)}")
        return problems, empty_counts

    try:
        rows = _parse_table(blocks[0].splitlines(), 1, _COVERAGE_HEADER, "input-coverage")
    except RequirementsError as exc:
        problems.append(f"input-coverage table: {exc}")
        return problems, empty_counts

    req_ids = {r.id for r in requirements.items}
    finding_ids = {e.id for e in entries if getattr(e, "kind", None) == "finding"}

    spans: list[str] = []
    n_req = n_deferred = n_context = n_missing = 0
    for cells, line_no in rows:
        span_cell, label = cells
        spans.append(_extract_quote(span_cell, line_no))
        if label == "deferred":
            n_deferred += 1
        elif label == "context":
            n_context += 1
        elif _REQ_LABEL_RE.match(label):
            n_req += 1
            unknown = [rid for rid in (x.strip() for x in label.split(",")) if rid not in req_ids]
            if unknown:
                problems.append(
                    f"line {line_no}: coverage cites unknown requirement id(s) {unknown}"
                )
        else:
            m = _MISSING_LABEL_RE.match(label)
            if m:
                n_missing += 1
                fid = m.group(1)
                if fid not in finding_ids:
                    problems.append(
                        f"line {line_no}: `missing {fid}` names no `kind=finding` entry in "
                        "the spec journal"
                    )
            else:
                problems.append(f"line {line_no}: unknown coverage label {label!r}")

    counts = CoverageCounts(
        spans=len(spans),
        requirement=n_req,
        deferred=n_deferred,
        context=n_context,
        missing=n_missing,
    )

    # §D check 2, whitespace-INSENSITIVE (review c1). A span boundary may fall
    # on whitespace (table cells are trimmed, so it is lost) or on none (a cut
    # right after `)`), so neither a space-join nor a bare join rebuilds the
    # input in both cases. Dropping all whitespace on both sides does, and the
    # partition still refuses any skipped, repeated or reordered text.
    expected = _strip_ws("".join(e.body for e in input_entries))
    actual = _strip_ws("".join(spans))
    if actual != expected:
        problems.append(
            "the input-coverage spans do not partition the input entries exactly "
            "(a gap, an overlap, or a reordered span)"
        )

    return problems, counts
