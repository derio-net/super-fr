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
    RequirementsError,
    _extract_quote,
    _parse_table,
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


def check_fidelity(
    review_body: str, spec_text: str, entries: Sequence[Any]
) -> tuple[list[str], FidelityCounts]:
    """The §A clause-partition gate: problems (empty when sound) and counts."""
    empty = FidelityCounts(clauses=0, requirements=0, kept=0, flagged=0)
    block, problem = _one_block(_FIDELITY_BLOCK_RE, "requirement-fidelity", review_body)
    if block is None:
        return [problem or ""], empty
    try:
        rows = _parse_table(block.splitlines(), 1, _FIDELITY_HEADER, "requirement-fidelity")
        parsed = [(c[0], _extract_quote(c[1], n), c[2], n) for c, n in rows]
        parse_requirements(spec_text)
    except RequirementsError as exc:
        return [f"requirement-fidelity table: {exc} — {_REDISPATCH}"], empty
    kept = sum(1 for _, _, label, _ in parsed if label == "kept")
    return [], FidelityCounts(
        clauses=len(parsed),
        requirements=len({rid for rid, _, _, _ in parsed}),
        kept=kept,
        flagged=len(parsed) - kept,
    )


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
