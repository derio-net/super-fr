"""`## Requirements` is a plain `R<n>. <text>` list (spec
`2026-09-29-spec-is-the-contract-design.md` §B, R5/R8).

The parser reads the list, and — for specs written before 5.0.0 — the old
three-column `| id | requirement | source |` table, taking `id` and
`requirement` and ignoring `source`. Both forms give the same ids and text.
"""

from __future__ import annotations

import pytest
from fr.requirements import RequirementsError, has_requirements, parse_requirements

LIST_SPEC = """# spec

## Requirements

R1. First thing.
R2. Second thing.

## Design

Prose.
"""

TABLE_SPEC = """# spec

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | First thing. | input "first" |
| R2 | Second thing. | decision q1<br>input "a \\| b" |

## Deferred from input

| input | reason |
|---|---|
| "later" | not now |
"""


def _pairs(spec: str) -> list[tuple[str, str]]:
    return [(r.id, r.text) for r in parse_requirements(spec).items]


def test_a_plain_list_parses_to_its_ids_and_text() -> None:
    assert _pairs(LIST_SPEC) == [("R1", "First thing."), ("R2", "Second thing.")]


def test_a_legacy_table_parses_to_the_same_ids_and_text() -> None:
    assert _pairs(TABLE_SPEC) == _pairs(LIST_SPEC)


def test_both_forms_count_as_having_requirements() -> None:
    assert has_requirements(LIST_SPEC)
    assert has_requirements(TABLE_SPEC)


def test_a_spec_without_the_section_has_no_requirements() -> None:
    spec = "# spec\n\n## Design\n\nProse.\n"
    assert has_requirements(spec) is False
    with pytest.raises(RequirementsError):
        parse_requirements(spec)


def test_a_section_with_only_prose_has_no_requirements() -> None:
    spec = "# spec\n\n## Requirements\n\nThe widget should count.\n"
    assert has_requirements(spec) is False


def test_a_duplicate_id_names_its_line() -> None:
    spec = "## Requirements\n\nR1. One.\nR1. Again.\n"
    with pytest.raises(RequirementsError, match=r"line 4.*R1"):
        parse_requirements(spec)


def test_a_non_increasing_id_names_its_line() -> None:
    spec = "## Requirements\n\nR2. Two.\nR1. One.\n"
    with pytest.raises(RequirementsError, match=r"line 4.*R1"):
        parse_requirements(spec)


def test_gaps_in_the_numbering_are_allowed() -> None:
    spec = "## Requirements\n\nR1. One.\nR3. Three.\n"
    assert [r.id for r in parse_requirements(spec).items] == ["R1", "R3"]


@pytest.mark.parametrize("bullet", ["- ", "* "])
def test_a_bulleted_list_reads_the_same(bullet: str) -> None:
    """Review c1: a Markdown bullet before `R<n>.` is the commonest near-miss;
    reading it as absent would skip phase sizing silently."""
    spec = LIST_SPEC.replace("R1.", f"{bullet}R1.").replace("R2.", f"{bullet}R2.")
    assert has_requirements(spec)
    assert _pairs(spec) == _pairs(LIST_SPEC)


# --- the two-column table (spec 2026-11-26-spec-requirements-table R1, R2) ----

TWO_COL_SPEC = """# spec

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | text a |
| R2 | b `x \\| y` |

## Design

Prose.
"""

TWO_COL_LIST = "# spec\n\n## Requirements\n\nR1. text a\nR2. b `x | y`\n\n## Design\n"

TWO_COL_LEGACY = """# spec

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | text a | input |
| R2 | b `x \\| y` | input |
"""


def test_a_two_column_table_parses_like_the_list_and_the_legacy_table() -> None:
    assert _pairs(TWO_COL_SPEC) == [("R1", "text a"), ("R2", "b `x | y`")]
    assert parse_requirements(TWO_COL_SPEC) == parse_requirements(TWO_COL_LIST)
    assert parse_requirements(TWO_COL_SPEC) == parse_requirements(TWO_COL_LEGACY)


@pytest.mark.parametrize("header", ["| id | requirement |", "| Id | REQUIREMENT |"])
def test_the_table_header_is_case_insensitive(header: str) -> None:
    spec = TWO_COL_SPEC.replace("| ID | Requirement |", header)
    assert _pairs(spec) == _pairs(TWO_COL_SPEC)


def test_a_two_column_table_counts_as_having_requirements() -> None:
    assert has_requirements(TWO_COL_SPEC)


def test_a_three_cell_row_names_its_line() -> None:
    spec = TWO_COL_SPEC.replace("| R2 | b `x \\| y` |", "| R2 | a | b |")
    line = spec.splitlines().index("| R2 | a | b |") + 1
    with pytest.raises(RequirementsError, match=rf"line {line}: .*3 cells, expected 2"):
        parse_requirements(spec)


def test_a_row_without_outer_pipes_ends_the_table() -> None:
    spec = TWO_COL_SPEC.replace("| R1 | text a |", "R1 | text a").replace(
        "| R2 | b `x \\| y` |", "R2 | b"
    )
    assert has_requirements(spec) is False
    with pytest.raises(RequirementsError, match=r"holds no") as e:
        parse_requirements(spec)
    assert "| ID | Requirement |" in str(e.value)
    assert "R<n>. <text>" in str(e.value)


@pytest.mark.parametrize(
    ("rows", "match"),
    [
        ("| R1 | a |\n| Rx | b |", r"line 8: malformed requirement id 'Rx'"),
        ("| R1 | a |\n| R1 | b |", r"line 8: requirement id R1 is repeated"),
        ("| R2 | a |\n| R1 | b |", r"line 8: requirement id R1 is repeated or out of order"),
    ],
)
def test_the_id_errors_fire_for_table_rows(rows: str, match: str) -> None:
    spec = "# spec\n\n## Requirements\n\n| ID | Requirement |\n|----|----|\n" + rows + "\n"
    with pytest.raises(RequirementsError, match=match):
        parse_requirements(spec)
