"""`## Requirements` is a plain `R<n>. <text>` list (spec
`2026-09-29-spec-is-the-contract-design.md` §B, R5/R8).

The parser reads the list, and — for specs written before 5.0.0 — the old
three-column `| id | requirement | source |` table, taking `id` and
`requirement` and ignoring `source`. Both forms give the same ids and text.
"""

from __future__ import annotations

import pytest
from fr.requirements import (
    RequirementsError,
    has_requirements,
    list_layout,
    parse_requirements,
)

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


@pytest.mark.parametrize("bad", ["| R2 | b", "R2 | b |", "R2 | b"])
def test_a_line_inside_the_table_that_is_not_a_whole_row_raises(bad: str) -> None:
    """Review p1-r2 (R2 amended): a broken row no longer ends the table silently."""
    spec = (
        "# spec\n\n## Requirements\n\n| ID | Requirement |\n|----|----|\n"
        f"| R1 | a |\n{bad}\n| R3 | c |\n"
    )
    with pytest.raises(RequirementsError, match=r"line 8: .*not a whole row"):
        parse_requirements(spec)
    assert has_requirements(spec), "requirement-shaped but invalid still counts (p1-r1)"


def test_the_table_ends_at_a_blank_line_or_a_line_with_no_pipe() -> None:
    blank = "## Requirements\n\n| ID | Requirement |\n|----|----|\n| R1 | a |\n\nAfter.\n"
    no_pipe = "## Requirements\n\n| ID | Requirement |\n|----|----|\n| R1 | a |\nAfter.\n"
    assert _pairs(blank) == [("R1", "a")]
    assert _pairs(no_pipe) == [("R1", "a")]


def test_a_header_without_a_delimiter_row_raises_naming_the_line() -> None:
    """Review p1-r3: the line after the header was skipped unchecked, losing R1."""
    spec = "## Requirements\n\n| ID | Requirement |\n| R1 | a |\n| R2 | b |\n"
    with pytest.raises(RequirementsError, match=r"line 4: .*delimiter row"):
        parse_requirements(spec)


@pytest.mark.parametrize("delim", ["|---|---|", "| :-- | --: |", "|:-:|:---:|", "| - | - |"])
def test_any_gfm_delimiter_row_is_accepted(delim: str) -> None:
    spec = f"## Requirements\n\n| ID | Requirement |\n{delim}\n| R1 | a |\n"
    assert _pairs(spec) == [("R1", "a")]


@pytest.mark.parametrize("prose", ["Rationale. see below", "Rather. than this", "- Rationale. x"])
def test_prose_starting_with_an_r_word_is_not_id_like(prose: str) -> None:
    """Review p1-r4 (R3 amended): an id-like prefix needs a digit after `R`."""
    spec = f"## Requirements\n\n{prose}\n"
    assert has_requirements(spec) is False
    layout = list_layout(spec)
    assert layout is not None and layout.items == ()


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


# --- continuation lines, id-like prefixes, the shared layout (R3) -------------


def test_continuation_lines_join_the_requirement_with_single_spaces() -> None:
    spec = "## Requirements\n\nR1. first\n  second line\nthird\nR2. next\n"
    assert _pairs(spec) == [("R1", "first second line third"), ("R2", "next")]


def test_a_blank_line_between_requirements_is_not_prose() -> None:
    spec = "## Requirements\n\nR1. a\n\nR2. b\n"
    assert _pairs(spec) == [("R1", "a"), ("R2", "b")]
    layout = list_layout(spec)
    assert layout is not None and layout.prose == ()


def test_prose_between_requirements_is_ignored_by_the_reader_but_named_by_the_layout() -> None:
    spec = "## Requirements\n\nR1. a\n\nsome prose\n\nR2. b\n\ntrailing prose\n"
    assert _pairs(spec) == [("R1", "a"), ("R2", "b")]
    layout = list_layout(spec)
    assert layout is not None
    assert layout.prose == (5,), "only the prose before a later requirement counts"


@pytest.mark.parametrize(
    ("line", "rid"),
    [
        ("R9ab. text", "R9ab"),
        ("- R9ab. text", "R9ab"),
        ("R0. x", "R0"),
        ("R09. x", "R09"),
        ("R9A. x", "R9A"),
        ("R9-a. x", "R9-a"),
    ],
)
def test_an_id_like_line_with_a_malformed_id_names_the_line(line: str, rid: str) -> None:
    spec = f"## Requirements\n\nR1. a\n{line}\n"
    with pytest.raises(RequirementsError, match=rf"line 4: malformed requirement id '{rid}'"):
        parse_requirements(spec)
    with pytest.raises(RequirementsError, match=r"line 4"):
        list_layout(spec)


def test_the_layout_spans_each_requirement() -> None:
    spec = "# s\n\n## Requirements\n\nintro\n\nR1. one\ntwo\n\nR2. three\n\n## Design\n"
    layout = list_layout(spec)
    assert layout is not None
    a, b = layout.items
    assert (a.id, a.text, a.first, a.last, a.line_no) == ("R1", "one two", 3, 4, 7)
    assert (b.id, b.text, b.first, b.last, b.line_no) == ("R2", "three", 6, 6, 10)
    assert (layout.start, layout.end) == (3, 6)
    assert spec.splitlines()[layout.base + a.first] == "R1. one"


def test_the_layout_is_none_for_a_table_or_no_section() -> None:
    assert list_layout(TWO_COL_SPEC) is None
    assert list_layout(TWO_COL_LEGACY) is None
    assert list_layout(TABLE_SPEC) is None
    assert list_layout("# spec\n\n## Design\n") is None


# --- lettered ids (spec 2026-11-26-spec-requirements-table R1, decision
# lettered-requirement-ids): `R<n>` plus one optional lowercase letter --------


def test_a_lettered_id_is_read_in_the_list() -> None:
    spec = "## Requirements\n\nR9. nine\nR9a. inserted\n- R9b. bulleted\nR10. ten\n"
    assert _pairs(spec) == [
        ("R9", "nine"),
        ("R9a", "inserted"),
        ("R9b", "bulleted"),
        ("R10", "ten"),
    ]


def test_a_lettered_id_is_read_in_the_table() -> None:
    spec = (
        "## Requirements\n\n| ID | Requirement |\n|----|----|\n"
        "| R9 | nine |\n| R9a | inserted |\n| R10 | ten |\n"
    )
    assert _pairs(spec) == [("R9", "nine"), ("R9a", "inserted"), ("R10", "ten")]


@pytest.mark.parametrize("rid", ["R9ab", "R09", "R9A", "R9-a"])
def test_a_table_row_with_a_non_r1_id_raises(rid: str) -> None:
    spec = f"## Requirements\n\n| ID | Requirement |\n|----|----|\n| R1 | a |\n| {rid} | b |\n"
    with pytest.raises(RequirementsError, match=rf"line 6: malformed requirement id '{rid}'"):
        parse_requirements(spec)


@pytest.mark.parametrize("ids", [("R9a", "R9"), ("R9a", "R9a"), ("R9b", "R9a"), ("R10", "R9a")])
def test_lettered_ids_must_increase(ids: tuple[str, str]) -> None:
    a, b = ids
    spec = f"## Requirements\n\n{a}. one\n{b}. two\n"
    if (a, b) == ("R10", "R9a"):
        match = r"line 4: requirement id R9a is repeated or out of order \(it follows R10\)"
    else:
        match = rf"line 4: requirement id {b} is repeated or out of order \(it follows {a}\)"
    with pytest.raises(RequirementsError, match=match):
        parse_requirements(spec)


def test_requirement_order_puts_a_lettered_id_between_its_neighbours() -> None:
    from fr.requirements import requirement_order

    assert sorted(["R10", "R9b", "R9", "R9a", "R2"], key=requirement_order) == [
        "R2",
        "R9",
        "R9a",
        "R9b",
        "R10",
    ]
