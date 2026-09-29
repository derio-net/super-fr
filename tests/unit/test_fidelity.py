"""fr.fidelity — the `requirement-fidelity` clause partition (§A) and the
`design-inventory` of every Design section (§B).

Spec `docs/superpowers/specs/2026-09-29-spec-fidelity-invention-design.md`
Test Plan items 1-2. Journal entries are real `JournalEntry` objects.
"""

from __future__ import annotations

import pytest
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


# ── Task 2: the requirement-fidelity clause partition (§A, Test Plan 1) ─────

T2_SPEC = _spec(
    '| R1 | x | input "alpha beta" |\n'
    '| R2 | y | input "gamma … delta"<br>input "epsilon" |\n'
    "| R3 | z | decision d1 |\n",
    "## Design\n\n### A. One\n",
)
T2_ENTRIES = [
    _input("alpha beta gamma x delta epsilon"),
    _spec_entry(kind="decision", id="d1"),
    _spec_entry(kind="decision", id="d9"),
    _spec_entry(kind="finding", id="s4", state="open"),
]
T2_SOUND = (
    '| R1 | "alpha" | kept |\n'
    '| R1 | "beta" | kept |\n'
    '| R2 | "gamma" | s4 |\n'
    '| R2 | "delta" | kept |\n'
    '| R2 | "epsilon" | kept |\n'
)


def test_a_sound_clause_partition_passes_and_counts() -> None:
    problems, fc = check_fidelity(_fidelity(T2_SOUND), T2_SPEC, T2_ENTRIES)
    assert problems == []
    assert (fc.clauses, fc.requirements, fc.kept, fc.flagged) == (5, 2, 4, 1)
    assert fc.finding_ids == ("s4",)


def test_whitespace_inside_a_clause_is_insensitive() -> None:
    rows = '| R1 | "alpha  beta" | kept |\n' + T2_SOUND.split("\n", 2)[2]
    problems, _ = check_fidelity(_fidelity(rows), T2_SPEC, T2_ENTRIES)
    assert problems == []


@pytest.mark.parametrize(
    ("rows", "needle"),
    [
        pytest.param(
            T2_SOUND.replace('| R1 | "alpha" | kept |\n| R1 | "beta" | kept |\n', ""),
            "R1",
            id="requirement-with-no-rows",
        ),
        pytest.param(T2_SOUND.replace('| R1 | "alpha" | kept |\n', ""), "R1", id="skipped-clause"),
        pytest.param(
            T2_SOUND.replace(
                '| R1 | "alpha" | kept |\n| R1 | "beta" | kept |\n',
                '| R1 | "beta" | kept |\n| R1 | "alpha" | kept |\n',
            ),
            "R1",
            id="reordered-clauses",
        ),
        pytest.param(
            '| R2 | "gamma" | s4 |\n| R2 | "delta" | kept |\n| R2 | "epsilon" | kept |\n'
            '| R1 | "alpha beta" | kept |\n',
            "order",
            id="requirements-out-of-order",
        ),
        pytest.param(
            '| R1 | "alpha" | kept |\n| R2 | "gamma" | s4 |\n| R1 | "beta" | kept |\n'
            '| R2 | "delta" | kept |\n| R2 | "epsilon" | kept |\n',
            "contiguous",
            id="non-contiguous",
        ),
        pytest.param(
            T2_SOUND.replace(
                '| R2 | "gamma" | s4 |\n| R2 | "delta" | kept |\n',
                '| R2 | "gamma delta" | kept |\n',
            ),
            "R2",
            id="clause-spans-an-elision",
        ),
        pytest.param(T2_SOUND.replace("| s4 |", "| s77 |"), "s77", id="unknown-finding-id"),
        pytest.param(T2_SOUND.replace("| s4 |", "| d9 |"), "d9", id="label-names-a-decision"),
        pytest.param(
            T2_SOUND + '| R3 | "whatever" | kept |\n', "R3", id="decision-only-given-rows"
        ),
        pytest.param(T2_SOUND + '| R9 | "alpha" | kept |\n', "R9", id="unknown-requirement"),
        pytest.param(
            T2_SOUND.replace('"epsilon" | kept', '"epsilon" | '), "line", id="empty-label"
        ),
    ],
)
def test_an_unsound_clause_partition_is_refused_naming_it(rows: str, needle: str) -> None:
    problems, _ = check_fidelity(_fidelity(rows), T2_SPEC, T2_ENTRIES)
    assert problems, rows
    assert any(needle in p for p in problems), problems


def test_a_requirement_added_after_the_review_is_refused() -> None:
    spec = T2_SPEC.replace("| R3 | z |", '| R4 | w | input "epsilon" |\n| R3 | z |')
    problems, _ = check_fidelity(_fidelity(T2_SOUND), spec, T2_ENTRIES)
    assert any("R4" in p for p in problems), problems


def test_a_clause_holding_a_raw_pipe_parses() -> None:
    spec = _spec('| R1 | x | input "a \\| b" |\n', "## Design\n")
    entries = [_input("a | b")]
    problems, fc = check_fidelity(_fidelity('| R1 | "a | b" | kept |\n'), spec, entries)
    assert problems == []
    assert fc.clauses == 1


@pytest.mark.parametrize("body", ["no block here", _fidelity(T2_SOUND) * 2])
def test_a_missing_or_duplicated_block_is_refused(body: str) -> None:
    problems, _ = check_fidelity(body, T2_SPEC, T2_ENTRIES)
    assert problems and "requirement-fidelity" in problems[0]


def test_the_requirements_grammar_never_imports_fidelity() -> None:
    """§C: fr.fidelity consumes fr.requirements and is not imported by it."""
    import fr.requirements

    source = open(fr.requirements.__file__).read()
    assert "fr.fidelity" not in source
    assert "from fr import fidelity" not in source
