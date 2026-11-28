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


def test_blank_lines_between_requirements_and_text_around_the_list_are_kept(
    tmp_path: Path,
) -> None:
    text = "# X\n\n## Requirements\n\nIntro prose.\n\nR1. a\n\nR2. b\n\nAfter prose.\n"
    path = _spec(tmp_path, text)
    assert not _migrate(tmp_path).failed
    assert path.read_text() == (
        "---\nfr_schema: 2\n---\n# X\n\n## Requirements\n\nIntro prose.\n\n"
        "| ID | Requirement |\n|----|-------------|\n| R1 | a |\n| R2 | b |\n\nAfter prose.\n"
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
    ],
    ids=["two-column", "legacy", "prose-only"],
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


PROSE_BETWEEN = "# X\n\n## Requirements\n\nR1. a\n\nsome prose\n\nR2. b\n"
BAD_ID = "# X\n\n## Requirements\n\nR1. a\nR9ab. b\n"


@pytest.mark.parametrize(
    ("text", "line", "cause", "fix"),
    [
        (PROSE_BETWEEN, 7, "prose between requirements", "move the prose out of"),
        (BAD_ID, 6, "malformed requirement id 'R9ab'", "fix the requirement id"),
    ],
    ids=["prose-between", "R9ab"],
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
