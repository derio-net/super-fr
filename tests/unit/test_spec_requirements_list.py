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
