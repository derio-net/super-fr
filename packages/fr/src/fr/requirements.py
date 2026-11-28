"""A spec's `## Requirements` section, and the matrix rows that cite it (spec
`2026-09-29-spec-is-the-contract-design.md` §B; the table form is spec
`2026-11-26-spec-requirements-table-design.md` R1-R3).

Authors write a two-column table, one row per requirement:

    | ID | Requirement |
    |----|-------------|
    | R1 | <text> |
    | R2 | <text, a literal \\| escaped> |

Every row starts and ends with `|`; a `\\|` inside a cell is a literal `|`, and
a row of other than two cells is an error naming its line. The header is read
in any case. An id is `R<n>` (`n` from 1, no leading zero), optionally followed
by one lowercase letter (`R9a`, inserted between `R9` and `R10` without
renumbering); ids increase down the section.

Two older forms still read to the same ids and text, so archived and
unmigrated specs keep their meaning:

- the `R<n>. <text>` list (`R<n>[a-z]`, optionally behind a `-`/`*` bullet), where
  everything up to the next requirement line, a heading or the section's end
  belongs to the requirement: lines directly after it are continuations joined
  with single spaces, and each further paragraph or `- `/`* ` bullet item is
  joined with `<br>`, the bullet kept (a table cell holds the same `<br>`). A
  line that starts like an id but is malformed (`R09. ...`) is an error;
- the pre-5.0 three-column `| id | requirement | source |` table, whose
  `source` column is ignored.

It carries no quote, no source and no gate on its content: the spec is the
contract, so a requirement says what it says.

Readers: phase sizing (`fr.phase_sizing`, `fr.plan_review`, `fr.proportionality`),
visual evidence (`fr.run.visual`), the PR body's post-merge section
(`fr.record.pr_body`), and the spec 1 -> 2 rewrite
(`fr.artifacts.spec_requirements_table`, through `list_layout`). The one disk
read here is `load_spec_matrix`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.acceptance.model import (
    AcceptanceError,
    Matrix,
    Row,
    archive_twin,
    same_repo,
    split_ref,
)

if TYPE_CHECKING:
    from fr.run.model import RunState, StepRecord


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str


@dataclass(frozen=True)
class Requirements:
    items: tuple[Requirement, ...]


class RequirementsError(Exception):
    """The section is absent, holds no requirement, or repeats or reorders an
    id. Every message about a line names it (1-based)."""


_REQUIREMENTS_HEADING = "## Requirements"
_LEGACY_HEADER = ["id", "requirement", "source"]
_TABLE_HEADER = ["id", "requirement"]
_ID_PATTERN = r"R[1-9][0-9]*[a-z]?"
"""A requirement id (R1): `R<n>`, `n` from 1 with no leading zero, optionally followed
by one lowercase letter (`R9a`), which inserts a requirement without renumbering."""
_ID_RE = re.compile(rf"^{_ID_PATTERN}$")
_LIST_ITEM_RE = re.compile(rf"^(?:[-*]\s+)?({_ID_PATTERN})\.\s+(\S.*)$")
"""`R<n>[a-z]. <text>`, optionally behind a Markdown `-`/`*` bullet."""
_ID_EXPECTED = "expected `R` + a positive integer, optionally + one lowercase letter"
_ID_LIKE_RE = re.compile(r"^(?:[-*]\s+)?(R[0-9]\S*)\.\s")
"""A line that starts like a requirement id (R3): an optional bullet, `R` and a
digit, any non-space characters, then `. `. One `_LIST_ITEM_RE` rejects is an
error; prose such as `Rationale. ...` is not id-like."""
_DELIMITER_CELL_RE = re.compile(r"^:?-+:?$")


def _locate_section(text: str) -> tuple[list[str], int] | None:
    """The `## Requirements` body: the lines up to the next `## ` heading (or
    EOF), and the 1-based line number of the first of them. `None` when the
    heading is absent."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == _REQUIREMENTS_HEADING), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start + 1 : end], start + 2


def _split_row(line: str) -> list[str]:
    """One GFM table row -> its stripped cells, `\\|` kept inside a cell."""
    inner = line.strip()[1:-1]
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", inner)]


def _is_row(line: str) -> bool:
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and s.endswith("|")


def _legacy_rows(lines: list[str], first_line_no: int) -> list[tuple[str, str, int]] | None:
    """A pre-5.0 table's `(id, requirement, line)` rows, or `None` when the
    section holds no `| id | requirement | source |` header."""
    for idx, line in enumerate(lines):
        if _is_row(line) and [c.lower() for c in _split_row(line)] == _LEGACY_HEADER:
            break
    else:
        return None
    rows: list[tuple[str, str, int]] = []
    for offset, line in enumerate(lines[idx + 2 :], start=idx + 2):
        if not _is_row(line):
            break
        cells = _split_row(line)
        if len(cells) >= 2:
            rows.append((cells[0], cells[1], first_line_no + offset))
    return rows


def _is_delimiter(line: str) -> bool:
    return _is_row(line) and all(_DELIMITER_CELL_RE.match(c) for c in _split_row(line))


def _table_body(
    lines: list[str], first_line_no: int
) -> tuple[list[tuple[list[str], int]], list[tuple[int, str]]] | None:
    """A two-column table's rows as `(cells, line)` and its structural problems
    as `(line, message)`, or `None` when the section holds no `| ID | Requirement |`
    header (any case). The header must be followed by a GFM delimiter row; the
    table ends at a blank line or a line holding no `|`, and any other line in it
    that is not a whole row (`|` first and last) is a problem (R2)."""
    for idx, line in enumerate(lines):
        if _is_row(line) and [c.lower() for c in _split_row(line)] == _TABLE_HEADER:
            break
    else:
        return None
    problems: list[tuple[int, str]] = []
    start = idx + 1
    if start < len(lines) and _is_delimiter(lines[start]):
        start += 1
    else:
        n = first_line_no + start
        problems.append(
            (
                n,
                f"line {n}: requirements table header is not followed by a delimiter row "
                "(|----|----|)",
            )
        )
    rows: list[tuple[list[str], int]] = []
    for offset, line in enumerate(lines[start:], start=start):
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            break
        n = first_line_no + offset
        if _is_row(line):
            rows.append((_split_row(line), n))
        else:
            problems.append(
                (
                    n,
                    f"line {n}: requirements table line is not a whole row "
                    "(start and end it with |)",
                )
            )
    return rows, problems


def _cell_count_error(cells: list[str], line_no: int) -> str:
    return (
        f"line {line_no}: requirements table row has {len(cells)} cells, expected 2 "
        "(escape a literal | as \\|)"
    )


def _table_rows(lines: list[str], first_line_no: int) -> list[tuple[str, str, int]] | None:
    """A two-column table's `(id, requirement, line)` rows, or `None` when there
    is no such table. A row of other than two cells raises, naming its line."""
    body = _table_body(lines, first_line_no)
    if body is None:
        return None
    rows, problems = body
    problems = problems + [(n, _cell_count_error(c, n)) for c, n in rows if len(c) != 2]
    if problems:
        raise RequirementsError(min(problems)[1])
    return [(cells[0], cells[1], line_no) for cells, line_no in rows]


@dataclass(frozen=True)
class ListItem:
    """One `R<n>.` requirement: its id; its text, with continuation lines joined by
    single spaces and each further paragraph, list item (`-`, `*`, `+`, `1.`, `1)`,
    nested ones prefixed `&nbsp;&nbsp;` per level) and `>` quote line joined with
    `<br>` (R3); the 0-based indices of its first and last line within the section;
    and the 1-based file line number of its first line (for messages)."""

    id: str
    text: str
    first: int
    last: int
    line_no: int


@dataclass(frozen=True)
class ListLayout:
    """The `R<n>.` list of a `## Requirements` section, as one walk sees it.
    `base` is the 0-based file index of the section's first line, so
    `base + item.first` indexes the file's lines. `prose` holds the 1-based line
    numbers of text between requirements that belongs to none (after a heading).
    The reader and the spec 1 -> 2 rewrite share this walk, so they agree on which
    lines belong to a requirement."""

    items: tuple[ListItem, ...]
    prose: tuple[int, ...]
    base: int
    fences: tuple[int, ...] = ()
    """The 1-based lines of code-fence markers (```` ``` ```` or `~~~`, any indent)
    after the first requirement: a code block inside the list, which the rewrite
    refuses. Lines inside a fence belong to no requirement."""

    @property
    def start(self) -> int:
        """The section index of the first requirement line (-1 when none)."""
        return self.items[0].first if self.items else -1

    @property
    def end(self) -> int:
        """The section index of the last requirement or continuation line (-1 when none)."""
        return self.items[-1].last if self.items else -1


_BULLET_RE = re.compile(r"^(?:[-*+]|[0-9]+[.)])\s+\S")
_QUOTE_RE = re.compile(r"^>")
_HEADING_RE = re.compile(r"^#{1,6}\s")
"""Matched on the raw line: only a heading at column 0 counts."""
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_NEST = "&nbsp;&nbsp;"
"""One nesting level of a nested list item (each 2 leading spaces), after its `<br>`."""
PARAGRAPH_BREAK = "<br>"
"""What joins a requirement's paragraphs and bullet items into one line (R3), in the
list reader and in a table cell alike: the reader keeps it verbatim, so a list and the
table it is rewritten to read to the same text."""


def _part(stripped: str) -> str:
    """One line's text as it joins the fold: one trailing `\\` (a Markdown hard break)
    is dropped, since `\\<br>` would render the `<br>` literally (review p1-r9)."""
    return stripped[:-1].rstrip() if stripped.endswith("\\") else stripped


def _walk_list(lines: list[str], first_line_no: int) -> ListLayout:
    """Classify the section's lines (R3). A requirement line opens an item, and
    everything after it up to the next requirement line, a heading at column 0 or the
    end of the section belongs to it: lines directly after it continue it (joined with
    single spaces), while a blank line, a list item (`-`, `*`, `+`, `1.`, `1)`; nested
    ones prefixed `&nbsp;&nbsp;` per 2 spaces of indent) and a `>` quote line each start
    a new segment; segments are joined with `<br>`, and one trailing `\\` per line is
    dropped. Blank lines before the first requirement and after the last one's text
    belong to none; text before the first requirement is prose and ignored. After a
    heading, the text up to the next requirement belongs to none and is recorded in
    `prose`. A code fence (```` ``` ```` or `~~~`, any indent) after the first
    requirement is recorded in `fences`; lines inside a fence belong to none."""
    items: list[ListItem] = []
    prose: list[int] = []
    pending: list[int] = []
    current: tuple[str, list[list[str]], int] | None = None  # (id, segments, first)
    last_idx = -1
    gap = False  # a blank line since the item's last text line

    def close() -> None:
        nonlocal current
        if current is not None:
            rid, segments, first = current
            text = PARAGRAPH_BREAK.join(" ".join(seg) for seg in segments)
            items.append(ListItem(rid, text, first, last_idx, first_line_no + first))
            current = None

    fences: list[int] = []
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            if items or current is not None:
                fences.append(first_line_no + idx)
            continue
        if in_fence:
            continue
        m = _LIST_ITEM_RE.match(stripped)
        if m:
            close()
            prose.extend(pending)
            pending = []
            current = (m.group(1), [[_part(m.group(2))]], idx)
            last_idx, gap = idx, False
            continue
        like = _ID_LIKE_RE.match(stripped)
        if like:
            raise RequirementsError(
                f"line {first_line_no + idx}: malformed requirement id {like.group(1)!r} "
                f"({_ID_EXPECTED})"
            )
        if not stripped:
            gap = True
            continue
        if _HEADING_RE.match(line):
            close()
        if current is not None:
            if _BULLET_RE.match(stripped):
                indent = len(line) - len(line.lstrip(" "))
                current[1].append([_NEST * (indent // 2) + _part(stripped)])
            elif gap or _QUOTE_RE.match(stripped):
                current[1].append([_part(stripped)])
            else:
                current[1][-1].append(_part(stripped))
            last_idx, gap = idx, False
        elif items:
            pending.append(first_line_no + idx)
    close()
    return ListLayout(
        items=tuple(items), prose=tuple(prose), base=first_line_no - 1, fences=tuple(fences)
    )


def _is_header(line: str) -> bool:
    return _is_row(line) and [c.lower() for c in _split_row(line)] in (
        _TABLE_HEADER,
        _LEGACY_HEADER,
    )


def requirements_form(spec_text: str) -> str | None:
    """Which form the `## Requirements` section is written in, judged by its
    first requirement-shaped line: `"table"` for an `| ID | Requirement |` or
    pre-5.0 `| id | requirement | source |` header, `"list"` for an `R<n>.` (or
    id-like) line, `None` when the section is absent or holds neither. Never
    raises, so a malformed table still reads as a table."""
    section = _locate_section(spec_text)
    if section is None:
        return None
    for line in section[0]:
        if _is_header(line):
            return "table"
        stripped = line.strip()
        if _LIST_ITEM_RE.match(stripped) or _ID_LIKE_RE.match(stripped):
            return "list"
    return None


def table_header_line(spec_text: str) -> int | None:
    """The 1-based line of the first table header in `## Requirements`, if any."""
    section = _locate_section(spec_text)
    if section is None:
        return None
    lines, first_line_no = section
    return next((first_line_no + i for i, line in enumerate(lines) if _is_header(line)), None)


def list_layout(spec_text: str) -> ListLayout | None:
    """The `R<n>.` list layout of the spec's `## Requirements` section, or `None`
    when there is no such section or it is a table (either form). Raises
    `RequirementsError` for a line that starts like an id but is malformed."""
    section = _locate_section(spec_text)
    if section is None or _legacy_rows(*section) is not None:
        return None
    if _table_rows(*section) is not None:
        return None
    return _walk_list(*section)


def table_form_problems(spec_text: str, stamp: int) -> list[str]:
    """What `fr validate artifacts` refuses in a spec stamped `stamp` (2 or
    later, R7): each `R<n>.` list line (or id-like line) in `## Requirements`,
    and each `| ID | Requirement |` row of other than two cells, by line. A
    pre-5.0 three-column table is not refused."""
    section = _locate_section(spec_text)
    if section is None or _legacy_rows(*section) is not None:
        return []
    lines, first_line_no = section
    found: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _LIST_ITEM_RE.match(stripped) or _ID_LIKE_RE.match(stripped):
            n = first_line_no + idx
            found.append(
                (
                    n,
                    f"line {n}: stamped fr_schema {stamp} but the requirement is in the "
                    "R<n>. list form; write it as an | ID | Requirement | table row",
                )
            )
    body = _table_body(lines, first_line_no)
    if body is not None:
        rows, problems = body
        found.extend(problems)
        found.extend((n, _cell_count_error(c, n)) for c, n in rows if len(c) != 2)
    return [message for _, message in sorted(found)]


def _list_rows(lines: list[str], first_line_no: int) -> list[tuple[str, str, int]]:
    """The `R<n>. <text>` requirements, in order, each with its continuation lines,
    paragraphs and bullet items folded in (R3)."""
    return [(i.id, i.text, i.line_no) for i in _walk_list(lines, first_line_no).items]


def _rows(spec_text: str) -> list[tuple[str, str, int]]:
    section = _locate_section(spec_text)
    if section is None:
        return []
    legacy = _legacy_rows(*section)
    if legacy is not None:
        return legacy
    table = _table_rows(*section)
    return table if table is not None else _list_rows(*section)


def requirement_order(rid: str) -> tuple[int, str]:
    """The sort key of a well-formed requirement id: `R9` < `R9a` < `R9b` < `R10`."""
    m = re.match(r"R([0-9]+)([a-z]?)$", rid)
    if m is None:
        raise ValueError(f"not a requirement id: {rid!r}")
    return int(m.group(1)), m.group(2)


def has_requirements(spec_text: str) -> bool:
    """Does the spec's `## Requirements` section hold a requirement, in either
    form? A section of prose alone does not — it predates both forms, and
    phase sizing skips such a spec silently. A section holding something
    requirement-shaped but invalid (a malformed id, a broken table row) does:
    `parse_requirements` then names the defect (review p1-r1)."""
    try:
        return bool(_rows(spec_text))
    except RequirementsError:
        return True


def parse_requirements(spec_text: str) -> Requirements:
    """The spec's requirements, in order. Pure, no I/O. Raises
    `RequirementsError` when there are none, or when an id is malformed,
    repeated or not greater than the one before it."""
    if _locate_section(spec_text) is None:
        raise RequirementsError(f"no `{_REQUIREMENTS_HEADING}` section found")
    rows = _rows(spec_text)
    if not rows:
        raise RequirementsError(
            f"`{_REQUIREMENTS_HEADING}` holds no requirement "
            "(an `| ID | Requirement |` table row or an `R<n>. <text>` line)"
        )
    items: list[Requirement] = []
    last, last_id = (0, ""), "R0"
    for rid, text, line_no in rows:
        if not _ID_RE.match(rid):
            raise RequirementsError(
                f"line {line_no}: malformed requirement id {rid!r} ({_ID_EXPECTED})"
            )
        key = requirement_order(rid)
        if key <= last:
            raise RequirementsError(
                f"line {line_no}: requirement id {rid} is repeated or out of order "
                f"(it follows {last_id})"
            )
        last, last_id = key, rid
        if not text:
            raise RequirementsError(f"line {line_no}: requirement {rid} has no text")
        items.append(Requirement(id=rid, text=text))
    return Requirements(items=tuple(items))


# --- which matrix origins name a spec ------------------------------------------


def origin_fragment(origin: str, spec_ref: str) -> str | None:
    """The fragment (`""` for none) of `origin` when it names the spec
    `spec_ref` (`<repo>:<spec-path>`), else `None`. Twin-aware, so a citation
    survives `fr archive`; a logical `spec:<slug>[#R<n>]` origin (spec 2026-11-04
    R18) names the spec whose slug it carries, live or archived."""
    from fr.acceptance.logical import is_logical, parse_logical, spec_dirs, spec_slug

    if is_logical(origin):
        try:
            logical = parse_logical(origin)
        except AcceptanceError:
            return None
        from fr.acceptance.fragment import fragment_slug_for_spec

        ref_path = spec_ref.partition(":")[2]
        in_specs = any(
            ref_path.startswith(d) and "/" not in ref_path[len(d) :] for d in spec_dirs()
        )
        if (
            logical.kind == "spec"
            and in_specs
            and fragment_slug_for_spec(ref_path) == spec_slug(logical.slug)
        ):
            return logical.anchor
        return None
    try:
        repo, path, frag = split_ref(origin)
    except AcceptanceError:
        return None
    ref_repo, _, ref_path = spec_ref.partition(":")
    if not same_repo(repo, ref_repo):
        return None
    if path == ref_path or archive_twin(path) == ref_path or path == archive_twin(ref_path):
        return frag
    return None


def rows_citing(matrix: Matrix, spec_ref: str) -> list[Row]:
    """Every matrix row with an `origin` naming the spec `spec_ref` (any
    fragment or none) — what visual evidence reads and the PR body's
    post-merge section lists."""
    return [
        r for r in matrix.rows if any(origin_fragment(o, spec_ref) is not None for o in r.origin)
    ]


def is_cited(req_id: str, matrix: Matrix, spec_ref: str) -> bool:
    """True when some matrix row's `origin` names `spec_ref#<req_id>` (its
    archive twin resolves too)."""
    return any(
        origin_fragment(origin, spec_ref) == req_id for row in matrix.rows for origin in row.origin
    )


# --- the run's spec and its matrix ---------------------------------------------


def spec_emitter(state: RunState) -> tuple[str, StepRecord] | None:
    """The step that recorded the run's `emitted.spec`, and its record."""
    return next(
        ((sid, r) for sid, r in state.steps.items() if r.emitted and "spec" in r.emitted), None
    )


def run_spec(state: RunState) -> str | None:
    """The run's spec (repo-relative), as the step that emitted it recorded it."""
    found = spec_emitter(state)
    return found[1].emitted["spec"] if found is not None and found[1].emitted else None


def load_spec_matrix(repo_root: Path, spec_rel: str) -> tuple[Matrix, str]:
    """The acceptance matrix (empty when the repo has none) and `spec_rel`'s
    `<repo>:<spec-path>` ref — or `AcceptanceError`."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.fold import load_effective

    matrix = load_effective(repo_root)
    _, repo = resolve_identity(matrix, repo_root)
    return matrix, f"{repo}:{spec_rel}"
