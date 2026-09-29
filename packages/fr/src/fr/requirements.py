"""A spec's `## Requirements` list, and the matrix rows that cite it (spec
`2026-09-29-spec-is-the-contract-design.md` §B).

The section is a plain numbered list, one requirement per line:

    R1. <text>
    R2. <text>

It carries no quote, no source and no gate on its content: the spec is the
contract, so a requirement says what it says. Specs written before 5.0.0 hold
a three-column `| id | requirement | source |` table instead; the parser reads
its `id` and `requirement` columns and ignores `source`, so both forms give
the same ids and text.

Readers: phase sizing (`fr.phase_sizing`, `fr.plan_ops`, `fr.proportionality`),
visual evidence (`fr.run.visual`) and the PR body's post-merge section
(`fr.record.pr_body`). The one disk read here is `load_spec_matrix`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.acceptance.model import AcceptanceError, Matrix, Row, archive_twin, split_ref

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
_ID_RE = re.compile(r"^R[1-9][0-9]*$")
_LIST_ITEM_RE = re.compile(r"^(R[1-9][0-9]*)\.\s+(\S.*)$")


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
    return legacy if legacy is not None else _list_rows(*section)


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
        raise RequirementsError(f"`{_REQUIREMENTS_HEADING}` holds no `R<n>. <text>` line")
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
    survives `fr archive`."""
    try:
        repo, path, frag = split_ref(origin)
    except AcceptanceError:
        return None
    ref_repo, _, ref_path = spec_ref.partition(":")
    if repo != ref_repo:
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
    from fr.acceptance.model import load_matrix
    from fr.commands.acceptance_cmd import MATRIX_REL

    path = repo_root / MATRIX_REL
    matrix = load_matrix(path) if path.exists() else Matrix()
    _, repo = resolve_identity(matrix, repo_root)
    return matrix, f"{repo}:{spec_rel}"
