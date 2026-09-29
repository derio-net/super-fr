"""Spec fidelity and invention: the `requirement-fidelity` clause partition
(§A) and the `design-inventory` of every Design section (§B), spec
`2026-09-29-spec-fidelity-invention-design.md`.

This module CONSUMES the requirements grammar (`fr.requirements`) and is never
imported by it. The checks are pure, no I/O: they verify the reviewer's
account is complete, never that a clause labelled `kept` really is kept or
that a behaviour is really user-visible — both stay reviewer judgement.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fr.requirements import (
    _REDISPATCH,
    _UNESCAPED_PIPE_RE,
    ELLIPSIS,
    RequirementsError,
    _coverage_form,
    _extract_quote,
    _parse_table,
    normalise,
    parse_requirements,
)


@dataclass(frozen=True)
class FidelityCounts:
    """`<c> clauses over <r> requirements (kept=<k> flagged=<f>)` (§C)."""

    clauses: int
    requirements: int
    kept: int
    flagged: int
    finding_ids: tuple[str, ...] = ()
    """The findings the flagged rows name, in row order, deduplicated — what
    §D's fixed|refuted rule holds."""


@dataclass(frozen=True)
class InventoryCounts:
    """`<s> sections, <b> behaviours (invented=<i>)` (§C)."""

    sections: int
    behaviours: int
    invented: int
    finding_ids: tuple[str, ...] = ()
    """The findings the `invented <id>` rows name, in row order, deduplicated."""


class FidelityError(Exception):
    """A spec the Design parser cannot read (no `## Design`)."""


_FIDELITY_BLOCK_RE = re.compile(r"```requirement-fidelity\r?\n(.*?)```", re.DOTALL)
_INVENTORY_BLOCK_RE = re.compile(r"```design-inventory\r?\n(.*?)```", re.DOTALL)
_FIDELITY_HEADER = ["requirement", "clause", "fidelity"]
_INVENTORY_HEADER = ["section", "behaviour", "backing"]


def _one_block(pattern: re.Pattern[str], name: str, body: str) -> tuple[str | None, str | None]:
    blocks = pattern.findall(body)
    if not blocks:
        return None, f"no `{name}` block found in the review body — {_REDISPATCH}"
    if len(blocks) > 1:
        return None, f"expected exactly one `{name}` block, found {len(blocks)} — {_REDISPATCH}"
    return blocks[0], None


def parse_design_sections(spec_text: str) -> list[str]:
    """The `###` subsections of `## Design`, in document order."""
    lines = spec_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "## Design"), None)
    if start is None:
        raise FidelityError("no `## Design` section found in the spec")
    sections: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("### "):
            sections.append(line[4:].strip())
    return sections or ["Design"]


# A data row whose MIDDLE cell is quoted: an unquoted requirement cell, then
# the clause from its first `"` to the last `"` before the label cell, which
# holds neither `|` nor `"` — the three-column variant of
# `fr.requirements._protect_span_pipes` (#777).
_QUOTED_CLAUSE_ROW_RE = re.compile(r'^(\s*\|[^|"]*\|\s*")(.*)("\s*\|[^|"]*\|\s*)$')


def _protect_clause_pipes(line: str) -> str:
    """Escape the raw `|` inside a quoted clause, so the row stays three cells."""
    m = _QUOTED_CLAUSE_ROW_RE.match(line)
    if m is None:
        return line
    return m.group(1) + _UNESCAPED_PIPE_RE.sub(r"\\|", m.group(2)) + m.group(3)


def _quote_fragments(quotes: Sequence[str]) -> list[str]:
    """Each quote split on the elision token, in comparison form. Every
    fragment boundary (an elision, or the end of one quote) is a clause
    boundary: the text an elision skipped is not part of the quote."""
    out: list[str] = []
    for quote in quotes:
        for frag in normalise(quote).split(ELLIPSIS):
            form = _coverage_form([frag])
            if form:
                out.append(form)
    return out


def _partition_problem(
    rid: str, fragments: list[str], clauses: list[tuple[str, int]]
) -> str | None:
    """Why `clauses` (text, line) do not partition `fragments`, or None."""
    fi = pos = 0
    for clause, line_no in clauses:
        form = _coverage_form([clause])
        if not form:
            return f"line {line_no}: requirement {rid} has an empty clause"
        if fi >= len(fragments):
            return (
                f"line {line_no}: requirement {rid}: clause {clause!r} runs past the end of "
                "its quotes (a repeated or extra clause)"
            )
        rest = fragments[fi][pos:]
        if rest.startswith(form):
            pos += len(form)
            if pos == len(fragments[fi]):
                fi, pos = fi + 1, 0
            continue
        if form.startswith(rest):
            return (
                f"line {line_no}: requirement {rid}: clause {clause!r} spans an elision or "
                "quote boundary — split it there (the elided text is not part of the quote)"
            )
        return (
            f"line {line_no}: requirement {rid}: clause {clause!r} is not the next text of "
            "its quotes (a skipped, reordered or altered clause)"
        )
    if fi < len(fragments):
        return (
            f"requirement {rid}: its clauses do not cover its quotes — the text from "
            f"{fragments[fi][pos:][:40]!r} on is unaccounted for"
        )
    return None


def check_fidelity(
    review_body: str, spec_text: str, entries: Sequence[Any]
) -> tuple[list[str], FidelityCounts]:
    """The §A clause-partition gate: problems (empty when sound) and counts.
    Taken over the Requirements table as it stands (d3): every requirement with
    an `input` source must have rows; a decision-only one must have none."""
    empty = FidelityCounts(clauses=0, requirements=0, kept=0, flagged=0)
    block, problem = _one_block(_FIDELITY_BLOCK_RE, "requirement-fidelity", review_body)
    if block is None:
        return [problem or ""], empty
    lines = [_protect_clause_pipes(line) for line in block.splitlines()]
    try:
        rows = _parse_table(lines, 1, _FIDELITY_HEADER, "requirement-fidelity")
        parsed = [(c[0], _extract_quote(c[1], n), c[2], n) for c, n in rows]
    except RequirementsError as exc:
        return [f"requirement-fidelity table: {exc} — {_REDISPATCH}"], empty
    try:
        requirements = parse_requirements(spec_text)
    except RequirementsError as exc:
        return [f"`## Requirements`: {exc}"], empty

    problems: list[str] = []
    by_id = {r.id: r for r in requirements.items}
    table_order = [r.id for r in requirements.items]
    finding_ids = {e.id for e in entries if getattr(e, "kind", None) == "finding"}
    kinds = {e.id: getattr(e, "kind", None) for e in entries}

    groups: list[str] = []
    clauses: dict[str, list[tuple[str, int]]] = {}
    kept = flagged = 0
    flagged_ids: dict[str, None] = {}
    for rid, clause, label, line_no in parsed:
        if rid not in by_id:
            problems.append(
                f"line {line_no}: requirement-fidelity names unknown requirement id {rid!r}"
            )
            continue
        if not groups or groups[-1] != rid:
            if rid in groups:
                problems.append(f"line {line_no}: the rows of requirement {rid} are not contiguous")
            groups.append(rid)
        clauses.setdefault(rid, []).append((clause, line_no))
        if label == "kept":
            kept += 1
        elif label in finding_ids:
            flagged += 1
            flagged_ids[label] = None
        elif label in kinds:
            problems.append(
                f"line {line_no}: requirement {rid}: fidelity label {label!r} names a "
                f"`{kinds[label]}` entry, not a `kind=finding` entry in the spec journal"
            )
        else:
            problems.append(
                f"line {line_no}: requirement {rid}: fidelity label {label!r} is neither "
                "`kept` nor a `kind=finding` entry in the spec journal"
            )

    seen = list(dict.fromkeys(groups))
    if seen != [rid for rid in table_order if rid in seen]:
        problems.append(
            f"the requirement-fidelity rows are not in `## Requirements` table order (got {seen})"
        )

    for req in requirements.items:
        quotes = [s.value for s in req.sources if s.kind == "input"]
        rows_of = clauses.get(req.id, [])
        if not quotes:
            if rows_of:
                problems.append(
                    f"line {rows_of[0][1]}: requirement {req.id} is decision-only and takes "
                    "no requirement-fidelity rows (it has no quote to be faithful to)"
                )
            continue
        if not rows_of:
            problems.append(
                f"requirement {req.id}: no requirement-fidelity rows — its quoted clauses are "
                f"unaccounted for — {_REDISPATCH}"
            )
            continue
        why = _partition_problem(req.id, _quote_fragments(quotes), rows_of)
        if why is not None:
            problems.append(why)

    counts = FidelityCounts(
        clauses=sum(len(v) for v in clauses.values()),
        requirements=len(clauses),
        kept=kept,
        flagged=flagged,
        finding_ids=tuple(flagged_ids),
    )
    return problems, counts


def check_inventory(
    review_body: str, spec_text: str, entries: Sequence[Any]
) -> tuple[list[str], InventoryCounts]:
    """The §B design-inventory gate: problems (empty when sound) and counts."""
    empty = InventoryCounts(sections=0, behaviours=0, invented=0)
    block, problem = _one_block(_INVENTORY_BLOCK_RE, "design-inventory", review_body)
    if block is None:
        return [problem or ""], empty
    try:
        rows = _parse_table(block.splitlines(), 1, _INVENTORY_HEADER, "design-inventory")
    except RequirementsError as exc:
        return [f"design-inventory table: {exc} — {_REDISPATCH}"], empty
    sections = parse_design_sections(spec_text)
    behaviours = sum(1 for cells, _ in rows if cells[1] != "none")
    return [], InventoryCounts(sections=len(sections), behaviours=behaviours, invented=0)


def fidelity_summary(fc: FidelityCounts, ic: InventoryCounts) -> str:
    """The line the `fidelity` evidence records (§C)."""
    return (
        f"{fc.clauses} clauses over {fc.requirements} requirements "
        f"(kept={fc.kept} flagged={fc.flagged}); "
        f"{ic.sections} sections, {ic.behaviours} behaviours (invented={ic.invented})"
    )
