"""The `spec` kind's 1 -> 2 migration: a live spec's `R<n>.` list becomes the
`| ID | Requirement |` table (spec 2026-11-26-spec-requirements-table R4-R6).

The rewrite keeps every line outside the requirement lines, adds a blank line
around the table only where none is, keeps the file's line endings and
round-trips the parsed requirements. A spec it cannot convert is left
byte-identical and unstamped, and its failure names the file, the line, the
cause and the hand fix, while every other spec still migrates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts.registry import ARTIFACT_KINDS, artifact_kind
from fr.artifacts.runner import MIGRATIONS, run_migrations
from fr.artifacts.validate import validate_artifact
from fr.requirements import parse_requirements

LIST_SPEC = """# X

## Requirements

R1. first line
continued here
R2. a | b

## Design

Prose.
"""

TABLE_OUT = """---
fr_schema: 2
---
# X

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | first line continued here |
| R2 | a \\| b |

## Design

Prose.
"""


def _spec(root: Path, text: str, name: str = "x-design.md", *, archived: bool = False) -> Path:
    d = root / "docs" / "superpowers" / ("implemented/specs" if archived else "specs")
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_bytes(text.encode())
    return path


def _migrate(root: Path):  # noqa: ANN202
    return run_migrations(root, dry_run=False)


def test_the_kind_is_at_two_and_reaches_it_from_one_hop_by_hop() -> None:
    assert ARTIFACT_KINDS["spec"].current_version == 2
    chain = MIGRATIONS.chain("spec", 1)
    assert [(m.from_version, m.to_version) for m in chain] == [(1, 2)]


def test_a_list_spec_is_rewritten_to_the_table_and_stamped(tmp_path: Path) -> None:
    path = _spec(tmp_path, LIST_SPEC)
    before = parse_requirements(LIST_SPEC)
    report = _migrate(tmp_path)
    assert not report.failed, report.failed
    assert path.read_text() == TABLE_OUT
    assert parse_requirements(path.read_text()) == before
    assert validate_artifact(artifact_kind("spec"), path) == ()


def test_blank_lines_are_added_around_the_table_only_where_none_is(tmp_path: Path) -> None:
    path = _spec(tmp_path, "# X\n\n## Requirements\nR1. a\nR2. b\n## Design\n")
    assert not _migrate(tmp_path).failed
    assert path.read_text() == (
        "---\nfr_schema: 2\n---\n# X\n\n## Requirements\n\n"
        "| ID | Requirement |\n|----|-------------|\n| R1 | a |\n| R2 | b |\n\n## Design\n"
    )


def test_intro_prose_is_kept_and_text_after_the_last_requirement_folds_into_it(
    tmp_path: Path,
) -> None:
    text = "# X\n\n## Requirements\n\nIntro prose.\n\nR1. a\n\nR2. b\n\nAfter prose.\n\n## D\n"
    path = _spec(tmp_path, text)
    assert not _migrate(tmp_path).failed
    assert path.read_text() == (
        "---\nfr_schema: 2\n---\n# X\n\n## Requirements\n\nIntro prose.\n\n"
        "| ID | Requirement |\n|----|-------------|\n| R1 | a |\n"
        "| R2 | b<br>After prose. |\n\n## D\n"
    )


def test_a_crlf_spec_keeps_crlf_on_every_line(tmp_path: Path) -> None:
    path = _spec(tmp_path, LIST_SPEC.replace("\n", "\r\n"))
    assert not _migrate(tmp_path).failed
    data = path.read_bytes()
    assert data == TABLE_OUT.replace("\n", "\r\n").encode()
    assert b"\n" not in data.replace(b"\r\n", b"")


@pytest.mark.parametrize(
    "body",
    [
        "| ID | Requirement |\n|----|----|\n| R1 | a \\| b |\n",
        "| id | requirement | source |\n|---|---|---|\n| R1 | a | input |\n",
        "The widget should count.\n",
        "Rationale. see below\n",
    ],
    ids=["two-column", "legacy", "prose-only", "r-word-prose"],
)
def test_a_table_legacy_or_prose_only_section_is_only_stamped(tmp_path: Path, body: str) -> None:
    text = f"# X\n\n## Requirements\n\n{body}\n## Design\n"
    path = _spec(tmp_path, text)
    assert not _migrate(tmp_path).failed
    assert path.read_text() == "---\nfr_schema: 2\n---\n" + text


def test_a_spec_with_no_section_is_only_stamped(tmp_path: Path) -> None:
    text = "# X\n\n## Design\n\nProse.\n"
    path = _spec(tmp_path, text)
    assert not _migrate(tmp_path).failed
    assert path.read_text() == "---\nfr_schema: 2\n---\n" + text


def test_a_body_already_a_table_under_an_old_stamp_is_finished_in_place(tmp_path: Path) -> None:
    """The crash window: the body was written, the stamp was not."""
    path = _spec(tmp_path, TABLE_OUT.replace("fr_schema: 2", "fr_schema: 1"))
    assert not _migrate(tmp_path).failed
    assert path.read_text() == TABLE_OUT


HEADING_BETWEEN = "# X\n\n## Requirements\n\nR1. a\n\n### Notes\n\nnote\n\nR2. b\n"
BAD_IDS = "# X\n\n## Requirements\n\nR1. a\nR09. b\nR9ab. c\n"
BAD_ID = "# X\n\n## Requirements\n\nR1. a\nR9ab. b\n"
OUT_OF_ORDER = "# X\n\n## Requirements\n\nR2. a\nR1. b\n"
HEADER_IN_LIST = "# X\n\n## Requirements\n\nR1. a\n| ID | Requirement |\nR2. b\n"


@pytest.mark.parametrize(
    ("text", "line", "cause", "fix"),
    [
        (
            HEADING_BETWEEN,
            7,
            "a heading inside the requirements list",
            "move the heading and its text out of the requirements list",
        ),
        # l-tests-r2, re-pointed: of two malformed lines, the FIRST is named.
        (BAD_IDS, 6, "malformed requirement id 'R09'", "fix the requirement id"),
        (BAD_ID, 6, "malformed requirement id 'R9ab'", "fix the requirement id"),
        (
            OUT_OF_ORDER,
            6,
            "requirement id R1 is repeated or out of order",
            "renumber the requirements so each id is greater than the one before",
        ),
        (
            HEADER_IN_LIST,
            6,
            "an `| ID | Requirement |` header inside the requirements list",
            "delete the header line, or finish the table by hand",
        ),
    ],
    ids=["heading-between", "first-of-two-bad-ids", "R9ab", "out-of-order", "header-in-list"],
)
def test_an_unconvertible_spec_is_left_byte_identical_and_named(
    tmp_path: Path, text: str, line: int, cause: str, fix: str
) -> None:
    bad = _spec(tmp_path, text, "bad-design.md")
    good = _spec(tmp_path, LIST_SPEC, "good-design.md")
    report = _migrate(tmp_path)
    assert bad.read_bytes() == text.encode(), "byte-identical and unstamped"
    [failure] = report.failed
    assert failure.path == bad
    assert f"{bad}:{line}:" in failure.error
    assert failure.error.count(f"{bad}:") == 1, "only the first offending line is named"
    assert cause in failure.error
    assert fix in failure.error
    assert good.read_text() == TABLE_OUT, "every other spec still migrates"


def test_a_failed_round_trip_refuses_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import spec_requirements_table as mod

    real = mod._row
    monkeypatch.setattr(mod, "_row", lambda rid, text: real(rid, text[:-1]))
    path = _spec(tmp_path, LIST_SPEC)
    report = _migrate(tmp_path)
    assert path.read_bytes() == LIST_SPEC.encode()
    [failure] = report.failed
    assert f"{path}:5:" in failure.error
    assert "round trip" in failure.error
    assert "join the requirement's lines into one line" in failure.error


def test_an_archived_spec_is_never_located(tmp_path: Path) -> None:
    path = _spec(tmp_path, LIST_SPEC, archived=True)
    report = _migrate(tmp_path)
    assert not report.applied and not report.failed
    assert path.read_bytes() == LIST_SPEC.encode()


def test_a_lettered_id_is_converted(tmp_path: Path) -> None:
    text = "# X\n\n## Requirements\n\nR9. nine\nR9a. inserted\nwrapped\nR10. ten\n"
    path = _spec(tmp_path, text)
    before = parse_requirements(text)
    assert not _migrate(tmp_path).failed
    out = path.read_text()
    assert "| R9a | inserted wrapped |\n" in out
    assert parse_requirements(out) == before
    assert validate_artifact(artifact_kind("spec"), path) == ()


def test_the_round_trip_parse_error_branch_refuses_with_the_join_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import spec_requirements_table as mod

    monkeypatch.setattr(mod, "_row", lambda rid, text: f"| {rid} | {text} | extra |")
    path = _spec(tmp_path, LIST_SPEC)
    [failure] = _migrate(tmp_path).failed
    assert path.read_bytes() == LIST_SPEC.encode()
    assert f"{path}:5: round trip failed: line " in failure.error
    assert "3 cells, expected 2" in failure.error
    assert "join the requirement's lines into one line" in failure.error


@pytest.mark.parametrize(
    ("text", "out"),
    [
        (
            "# X\n\n## Requirements\n\nR1. a\nR2. b",
            "---\nfr_schema: 2\n---\n# X\n\n## Requirements\n\n"
            "| ID | Requirement |\n|----|-------------|\n| R1 | a |\n| R2 | b |",
        ),
        (
            "# X\n\n## Requirements\n\nR1. keep a \\| as is\n",
            "---\nfr_schema: 2\n---\n# X\n\n## Requirements\n\n"
            "| ID | Requirement |\n|----|-------------|\n| R1 | keep a \\\\| as is |\n",
        ),
        (
            # Mixed endings: the table takes the FIRST requirement line's ending.
            "# X\r\n\r\n## Requirements\r\n\r\nR1. a\nR2. b\r\n\r\n## D\r\n",
            "---\r\nfr_schema: 2\r\n---\r\n# X\r\n\r\n## Requirements\r\n\r\n"
            "| ID | Requirement |\n|----|-------------|\n| R1 | a |\n| R2 | b |\n\r\n## D\r\n",
        ),
    ],
    ids=["no-final-newline", "literal-escaped-pipe", "mixed-endings"],
)
def test_edge_layouts_convert_exactly(tmp_path: Path, text: str, out: str) -> None:
    path = _spec(tmp_path, text)
    before = parse_requirements(text)
    assert not _migrate(tmp_path).failed
    assert path.read_bytes().decode() == out
    assert parse_requirements(out) == before


@pytest.mark.parametrize(
    "body",
    [
        "| ID | Requirement |\n|----|----|\n| R1 | a | b |\n",
        "| ID | Requirement |\n| R1 | a |\n",
        "| ID | Requirement |\n|----|----|\n| R1 | a |\n| R2 | b\n",
    ],
    ids=["three-cells", "no-delimiter", "broken-row"],
)
def test_a_malformed_table_is_only_stamped_and_the_validator_names_the_row(
    tmp_path: Path, body: str
) -> None:
    """Lens l-errors-r1 (a): a section in table form is only stamped (R4); the
    stamp-2 validator (R7) then names the bad line."""
    text = f"# X\n\n## Requirements\n\n{body}\n## Design\n"
    path = _spec(tmp_path, text)
    report = _migrate(tmp_path)
    assert path.read_text() == "---\nfr_schema: 2\n---\n" + text
    assert all(f.path != path or "requirements table" in f.error for f in report.failed)
    issues = validate_artifact(artifact_kind("spec"), path)
    assert any("requirements table" in str(i) and "line " in str(i) for i in issues), issues


OPS_GATE_SHAPE = """# X

## Requirements

R10. `row_walked(row)` is the one rule for a walked row: its status is
`walked` and its latest walk passed. `gate_items(...)` returns one item for
each thing that gate owns, with a one-line reason:

- each plan op, closed or not (devops only);
- each Test Plan step whose effective gate is `gate`, with or without a `ran`
  outcome;
- each row whose effective gate is `gate`. A row's reason says why: no walk | a failing walk.

A walk named in `exclude_walks` does not count. `devops_blockers` stays.

R11. `fr gate pass` refuses while `gate_blockers` is not empty.

## Design
"""

TWO_PARAGRAPHS = "# X\n\n## Requirements\n\nR1. a\n\nfirst prose\n\nsecond prose\n\nR2. b\n"


@pytest.mark.parametrize(
    ("text", "rows"),
    [
        (
            OPS_GATE_SHAPE,
            [
                "| R10 | `row_walked(row)` is the one rule for a walked row: its status is "
                "`walked` and its latest walk passed. `gate_items(...)` returns one item for "
                "each thing that gate owns, with a one-line reason:"
                "<br>- each plan op, closed or not (devops only);"
                "<br>- each Test Plan step whose effective gate is `gate`, with or without a "
                "`ran` outcome;"
                "<br>- each row whose effective gate is `gate`. A row's reason says why: no "
                "walk \\| a failing walk."
                "<br>A walk named in `exclude_walks` does not count. `devops_blockers` stays. |",
                "| R11 | `fr gate pass` refuses while `gate_blockers` is not empty. |",
            ],
        ),
        (
            TWO_PARAGRAPHS,
            ["| R1 | a<br>first prose<br>second prose |", "| R2 | b |"],
        ),
    ],
    ids=["ops-gate-truth-R10", "two-prose-paragraphs"],
)
def test_multi_paragraph_requirements_fold_into_one_cell(
    tmp_path: Path, text: str, rows: list[str]
) -> None:
    """Decision fold-multi-paragraph (R3, R5 amended): no refusal; each paragraph
    and bullet item joins the cell with `<br>`, and the round trip holds."""
    path = _spec(tmp_path, text)
    before = parse_requirements(text)
    assert not _migrate(tmp_path).failed
    out = path.read_text()
    table = [line for line in out.splitlines() if line.startswith("| R")]
    assert table == rows
    assert parse_requirements(out) == before
    assert validate_artifact(artifact_kind("spec"), path) == ()


FENCE_FIX = "move it out of the list or below the section"


@pytest.mark.parametrize(
    ("text", "line"),
    [
        # p1-r6: a fence inside the last requirement, holding a `# comment`.
        (
            "# X\n\n## Requirements\n\nR1. a\nR2. run:\n\n"
            "```bash\n# install\nmake\n```\n\n## Next\n",
            8,
        ),
        # p1-r6: the same fence between two requirements.
        ("# X\n\n## Requirements\n\nR1. a\n\n```bash\n# install\n```\n\nR2. b\n", 7),
        # p1-r7: a fenced example requirement; `~~~` and an indented fence too.
        ("# X\n\n## Requirements\n\nR1. a\n\n```text\nR2. b\n```\n", 7),
        ("# X\n\n## Requirements\n\nR1. a\n\n~~~\nR2. b\n~~~\n", 7),
        ("# X\n\n## Requirements\n\nR1. a\n\n    ```\n    x\n    ```\n", 7),
    ],
    ids=["fence-in-last", "fence-between", "fenced-requirement", "tilde-fence", "indented-fence"],
)
def test_a_code_block_inside_the_list_refuses(tmp_path: Path, text: str, line: int) -> None:
    path = _spec(tmp_path, text)
    [failure] = _migrate(tmp_path).failed
    assert path.read_bytes() == text.encode()
    assert f"{path}:{line}: a code block inside the requirements list" in failure.error
    assert FENCE_FIX in failure.error


def test_an_indented_hash_line_is_text_not_a_heading(tmp_path: Path) -> None:
    """p1-r6: only a line at column 0 is a heading."""
    path = _spec(tmp_path, "# X\n\n## Requirements\n\nR1. a\n    # not a heading\nR2. b\n")
    assert not _migrate(tmp_path).failed
    rows = [line for line in path.read_text().splitlines() if line.startswith("| R")]
    assert rows == ["| R1 | a # not a heading |", "| R2 | b |"]


def test_a_heading_after_the_last_requirement_keeps_its_text_byte_identical(
    tmp_path: Path,
) -> None:
    """p1-r10: the heading ends the last requirement; it and its text stay as they were."""
    tail = "### Notes\n\nSome *notes* \\| kept.\n  indented\n"
    text = f"# X\n\n## Requirements\n\nR1. a\n\n{tail}\n## D\n"
    path = _spec(tmp_path, text)
    assert not _migrate(tmp_path).failed
    out = path.read_text()
    assert "| R1 | a |\n\n" + tail + "\n## D\n" in out
