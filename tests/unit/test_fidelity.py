"""fr.fidelity — the `requirement-fidelity` clause partition (§A) and the
`design-inventory` of every Design section (§B).

Spec `docs/superpowers/specs/2026-09-29-spec-fidelity-invention-design.md`
Test Plan items 1-2. Journal entries are real `JournalEntry` objects.
"""

from __future__ import annotations

from fr.fidelity import (
    FidelityCounts,
    InventoryCounts,
    check_fidelity,
    check_inventory,
    fidelity_summary,
)
from fr.journal.model import JournalEntry

# ── fixtures / helpers ──────────────────────────────────────────────────────


def _spec_entry(**kw: object) -> JournalEntry:
    base: dict[str, object] = dict(scope="spec", created="2026-09-29T00:00:00", title="t")
    return JournalEntry(**{**base, **kw})  # type: ignore[arg-type]


def _input(body: str = "alpha beta") -> JournalEntry:
    return _spec_entry(kind="discovery", id="operator-input", body=body, input=True)


def _spec(requirements_rows: str, design: str) -> str:
    return (
        "# spec\n\n## Requirements\n\n| id | requirement | source |\n|---|---|---|\n"
        f"{requirements_rows}\n{design}"
    )


MINIMAL_SPEC = _spec('| R1 | x | input "alpha beta" |\n', "## Design\n\n### A. One\n\ntext\n")


def _block(fence: str, header: str, rows: str) -> str:
    cols = header.count("|") - 1
    delim = "|" + "---|" * cols
    return f"```{fence}\n{header}\n{delim}\n{rows}```\n"


def _fidelity(rows: str) -> str:
    return _block("requirement-fidelity", "| requirement | clause | fidelity |", rows)


def _inventory(rows: str) -> str:
    return _block("design-inventory", "| section | behaviour | backing |", rows)


COVERAGE = _block("input-coverage", "| span | coverage |", '| "alpha beta" | R1 |\n')

SOUND_REVIEW = (
    "no findings\n\n"
    + COVERAGE
    + "\n"
    + _fidelity('| R1 | "alpha beta" | kept |\n')
    + "\n"
    + _inventory("| A. One | none | none |\n")
)


# ── Task 1: the walking skeleton ────────────────────────────────────────────


def test_a_sound_review_yields_the_fidelity_summary() -> None:
    entries = [_input()]
    fproblems, fc = check_fidelity(SOUND_REVIEW, MINIMAL_SPEC, entries)
    iproblems, ic = check_inventory(SOUND_REVIEW, MINIMAL_SPEC, entries)
    assert fproblems == []
    assert iproblems == []
    assert isinstance(fc, FidelityCounts)
    assert isinstance(ic, InventoryCounts)
    assert fidelity_summary(fc, ic) == (
        "1 clauses over 1 requirements (kept=1 flagged=0); 1 sections, 0 behaviours (invented=0)"
    )
