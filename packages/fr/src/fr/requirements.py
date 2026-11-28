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
in any case.

Two older forms still read to the same ids and text, so archived and
unmigrated specs keep their meaning:

- the `R<n>. <text>` list (optionally behind a `-`/`*` bullet), where the
  non-blank lines directly after a requirement line are its continuation,
  joined with single spaces, and a line that starts like an id but is
  malformed (`R9a. ...`) is an error;
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
_ID_RE = re.compile(r"^R[1-9][0-9]*$")
_LIST_ITEM_RE = re.compile(r"^(?:[-*]\s+)?(R[1-9][0-9]*)\.\s+(\S.*)$")
"""`R<n>. <text>`, optionally behind a Markdown `-`/`*` bullet."""


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


def _table_rows(lines: list[str], first_line_no: int) -> list[tuple[str, str, int]] | None:
    """A two-column table's `(id, requirement, line)` rows, or `None` when the
    section holds no `| ID | Requirement |` header (any case). The rows run from
    the line after the delimiter row to the first line that is not a row; one of
    other than two cells raises, naming its line."""
    for idx, line in enumerate(lines):
        if _is_row(line) and [c.lower() for c in _split_row(line)] == _TABLE_HEADER:
            break
    else:
        return None
    rows: list[tuple[str, str, int]] = []
    for offset, line in enumerate(lines[idx + 2 :], start=idx + 2):
        if not _is_row(line):
            break
        cells = _split_row(line)
        if len(cells) != 2:
            raise RequirementsError(
                f"line {first_line_no + offset}: requirements table row has {len(cells)} "
                "cells, expected 2 (escape a literal | as \\|)"
            )
        rows.append((cells[0], cells[1], first_line_no + offset))
    return rows


def _list_rows(lines: list[str], first_line_no: int) -> list[tuple[str, str, int]]:
    """The `R<n>. <text>` lines, in order. Any other line is prose and is
    left alone."""
    rows: list[tuple[str, str, int]] = []
    for offset, line in enumerate(lines):
        m = _LIST_ITEM_RE.match(line.strip())
        if m:
            rows.append((m.group(1), m.group(2).strip(), first_line_no + offset))
    return rows


def _rows(spec_text: str) -> list[tuple[str, str, int]]:
    section = _locate_section(spec_text)
    if section is None:
        return []
    legacy = _legacy_rows(*section)
    if legacy is not None:
        return legacy
    table = _table_rows(*section)
    return table if table is not None else _list_rows(*section)


def has_requirements(spec_text: str) -> bool:
    """Does the spec's `## Requirements` section hold a requirement, in either
    form? A section of prose alone does not — it predates both forms, and
    phase sizing skips such a spec silently."""
    return bool(_rows(spec_text))


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
    last = 0
    for rid, text, line_no in rows:
        if not _ID_RE.match(rid):
            raise RequirementsError(
                f"line {line_no}: malformed requirement id {rid!r} "
                "(expected `R` + a positive integer)"
            )
        number = int(rid[1:])
        if number <= last:
            raise RequirementsError(
                f"line {line_no}: requirement id {rid} is repeated or out of order "
                f"(it follows R{last})"
            )
        last = number
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
