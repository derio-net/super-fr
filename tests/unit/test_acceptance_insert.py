"""Insert by capability (spec 2026-09-26-version-bump-churn §3.H).

`fr acceptance add` places a new row after the LAST row sharing its
`capability`, and appends at the end only for a capability not yet present.
Two PRs adding rows to different capabilities then touch different places in
`matrix.yaml` instead of both appending at EOF — the shape that made every
concurrent `add` a merge conflict.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.acceptance.edit import insert_row, render_row_block
from fr.acceptance.model import Row, load_matrix, parse_matrix
from fr.acceptance.report import render_committed_set
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import MATRIX_HEADER, make_repo

runner = CliRunner()


def _row_text(id: str, capability: str) -> str:
    return (
        f"  - id: {id}\n"
        f'    capability: "{capability}"\n'
        '    acceptance: "Operator can do X"\n'
        '    origin: ["own:docs/superpowers/specs/s.md"]\n'
        "    levels:\n"
        '      unit: ["own:tests/test_a.py"]\n'
        "    status: ci\n"
        '    notes: "n"  # a trailing comment this row owns\n'
    )


def _new(id: str, capability: str) -> Row:
    return Row(
        id=id,
        capability=capability,
        acceptance="Operator can do Y",
        origin=("own:docs/superpowers/specs/s.md",),
        levels={"unit": ("own:tests/test_a.py",)},
        status="not-implemented",
        notes="new",
    )


# Alpha and Beta interleave, the way the real matrix's capabilities do.
BASE = (
    "# header comment\n"
    + MATRIX_HEADER
    + _row_text("a1", "Alpha")
    + _row_text("b1", "Beta")
    + _row_text("a2", "Alpha")
    + "  # a comment introducing b2\n"
    + _row_text("b2", "Beta")
)


def _ids(text: str) -> list[str]:
    return [r.id for r in parse_matrix(text).rows]


def test_existing_capability_lands_after_its_last_row() -> None:
    out = insert_row(BASE, _new("a3", "Alpha"))
    assert _ids(out) == ["a1", "b1", "a2", "a3", "b2"]


def test_neighbouring_rows_and_comments_are_byte_preserved() -> None:
    out = insert_row(BASE, _new("a3", "Alpha"))
    # Everything up to and including a2 is untouched, and so is everything
    # from the comment that introduces b2 onwards: the insertion is a pure
    # addition of lines between them.
    head, _, tail = BASE.partition("  # a comment introducing b2\n")
    assert out.startswith(head)
    assert out.endswith("  # a comment introducing b2\n" + tail)
    added = out[len(head) : len(out) - len(tail) - len("  # a comment introducing b2\n")]
    parsed = yaml.safe_load(added)
    assert parsed[0]["id"] == "a3"


def test_last_capability_row_at_eof_appends() -> None:
    out = insert_row(BASE, _new("b3", "Beta"))
    assert out.startswith(BASE)
    assert _ids(out) == ["a1", "b1", "a2", "b2", "b3"]


def test_new_capability_appends_at_the_end() -> None:
    out = insert_row(BASE, _new("g1", "Gamma"))
    assert out.startswith(BASE)
    assert _ids(out) == ["a1", "b1", "a2", "b2", "g1"]


def test_capability_quoted_in_notes_does_not_hijack() -> None:
    """The scan parses each row block; a note mentioning `capability: Alpha`
    on a Beta row is not an Alpha row."""
    tricky = BASE.replace(
        '    notes: "n"  # a trailing comment this row owns\n  # a comment introducing b2\n',
        '    notes: "n"\n  # a comment introducing b2\n',
    ) + _row_text("b3", "Beta").replace('"n"', "'capability: Alpha'")
    out = insert_row(tricky, _new("a3", "Alpha"))
    assert _ids(out) == ["a1", "b1", "a2", "a3", "b2", "b3"]


def test_rendered_order_of_existing_rows_is_unchanged(tmp_path: Path) -> None:
    """Capabilities render in first-seen order and rows in matrix order, so an
    insert by capability renders exactly as an append would."""
    root = make_repo(tmp_path, "", header="")
    new = _new("a3", "Alpha")
    inserted = parse_matrix(insert_row(BASE, new))
    appended = parse_matrix(BASE + render_row_block(new))
    assert [r.id for r in appended.rows][-1] == "a3"
    assert render_committed_set(inserted, root) == render_committed_set(appended, root)


def test_add_cli_inserts_by_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, "", header="")
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    matrix_path.write_text(BASE)
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app,
        [
            "acceptance",
            "add",
            "--id",
            "a3",
            "--capability",
            "Alpha",
            "--acceptance",
            "Operator can do Y",
            "--origin",
            "own:docs/superpowers/specs/s.md",
            "--status",
            "not-implemented",
            "--notes",
            "new",
        ],
    )
    assert result.exit_code == 0, result.output
    assert [r.id for r in load_matrix(matrix_path).rows] == ["a1", "b1", "a2", "a3", "b2"]


def test_scalar_continuation_starting_with_hash_stays_in_its_row() -> None:
    """A wrapped quoted scalar can put `#` first on a line (the real matrix has
    `      #352, not automated.'`). That is row content, not a comment between
    rows, so the new row must go after it, not before it."""
    wrapped = (
        "  - id: a9\n"
        '    capability: "Alpha"\n'
        '    acceptance: "Operator can do X"\n'
        '    origin: ["own:docs/superpowers/specs/s.md"]\n'
        "    levels: {}\n"
        "    status: skipped\n"
        "    notes: 'proven live in\n"
        "      #352, not automated.'\n"
    )
    text = MATRIX_HEADER + wrapped + _row_text("b1", "Beta")
    out = insert_row(text, _new("a10", "Alpha"))
    m = parse_matrix(out)
    assert [r.id for r in m.rows] == ["a9", "a10", "b1"]
    assert m.rows[0].notes == "proven live in #352, not automated."
