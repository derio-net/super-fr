"""Tests for vk.spec_index — read/create/update Implementation Plans table."""

from pathlib import Path

from vk.spec_index import IndexEntry, _build_table, read_index, upsert_entry

SPEC_TABLE = """\
## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo-a` | `docs/superpowers/plans/plan-a.md` | Not Started | — |
| Plan B | `org/repo-b` | `docs/superpowers/plans/plan-b.md` | Not Started | Phase X |
"""

SPEC_TABLE_WITH_PROSE = """\
## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo-a` | `docs/superpowers/plans/plan-a.md` | Not Started | — |

Cross-phase dependency note: Plan A must complete before Plan B.
"""

FIXTURES = Path(__file__).parent.parent / "fixtures" / "specs"


# --- Read ---


def test_read_existing_index() -> None:
    entries = read_index(FIXTURES / "spec-with-index.md")
    assert len(entries) == 2
    assert entries[0].plan == "P0: Scaffold"
    assert entries[0].status == "Complete"
    assert entries[1].plan == "P1: Core"
    assert entries[1].status == "In Progress"


def test_read_no_index() -> None:
    entries = read_index(FIXTURES / "spec-without-index.md")
    assert entries == []


def test_read_missing_file() -> None:
    entries = read_index(Path("/nonexistent/spec.md"))
    assert entries == []


# --- Upsert ---


def test_upsert_creates_section(tmp_path: Path) -> None:
    """Adds ## Implementation Plans section when missing."""
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n## Summary\n\nSome content.\n")
    entry = IndexEntry(
        plan="P0: Scaffold",
        repo="my-repo",
        file="plans/p0.md",
        status="Not Started",
        depends_on="—",
    )
    upsert_entry(spec, entry)
    text = spec.read_text()
    assert "## Implementation Plans" in text
    assert "P0: Scaffold" in text
    assert "Not Started" in text


def test_upsert_adds_row(tmp_path: Path) -> None:
    """Adds a new row to existing table."""
    spec = tmp_path / "spec.md"
    spec.write_text((FIXTURES / "spec-with-index.md").read_text())
    entry = IndexEntry(
        plan="P2: Dispatch",
        repo="superpowers-for-vk",
        file="plans/p2.md",
        status="Not Started",
        depends_on="P1",
    )
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 3
    assert entries[2].plan == "P2: Dispatch"


def test_upsert_updates_existing(tmp_path: Path) -> None:
    """Updates status of an existing plan row."""
    spec = tmp_path / "spec.md"
    spec.write_text((FIXTURES / "spec-with-index.md").read_text())
    entry = IndexEntry(
        plan="P1: Core",
        repo="superpowers-for-vk",
        file="docs/superpowers/plans/2026-04-12-core.md",
        status="Complete",
        depends_on="P0",
    )
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 2
    p1 = [e for e in entries if e.plan == "P1: Core"][0]
    assert p1.status == "Complete"


def test_upsert_idempotent(tmp_path: Path) -> None:
    """Upserting the same entry twice doesn't create duplicates."""
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\n## Summary\n\nContent.\n")
    entry = IndexEntry(
        plan="P0: Init",
        repo="r",
        file="f.md",
        status="Not Started",
        depends_on="—",
    )
    upsert_entry(spec, entry)
    upsert_entry(spec, entry)
    entries = read_index(spec)
    assert len(entries) == 1


class TestUpsertByFilePath:
    def test_section_exists_but_no_table_yet(self, tmp_path: Path) -> None:
        """Table is inserted when section exists but has no rows yet."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "# Title\n\n## Implementation Plans\n\nSome prose.\n\n## Details\n\nContent.\n"
        )
        entry = IndexEntry(
            plan="P0", repo="r", file="plans/p0.md", status="Not Started", depends_on="—"
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "P0" in text
        assert "Some prose." in text
        assert "## Details" in text

    def test_empty_file_matches_dash_placeholder(self, tmp_path: Path) -> None:
        """file='' and file='—' are treated as the same placeholder — no duplicate rows."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "## Implementation Plans\n\n"
            "| Plan | Repo | File | Status | Depends on |\n"
            "|------|------|------|--------|------------|\n"
            "| Operator Row | | — | Not Started | — |\n"
        )
        entry = IndexEntry(
            plan="Operator Row",
            repo="",
            file="",  # empty — should match the '—' placeholder row
            status="In Progress",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        entries = read_index(spec)
        assert len(entries) == 1
        assert entries[0].status == "In Progress"

    def test_same_path_different_title_updates_in_place(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE)
        entry = IndexEntry(
            plan="Plan A (revised title)",
            repo="`org/repo-a`",
            file="docs/superpowers/plans/plan-a.md",
            status="In Progress",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Plan A (revised title)" in text
        assert "In Progress" in text
        assert text.count("docs/superpowers/plans/plan-a.md") == 1

    def test_new_path_appends_row(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE)
        entry = IndexEntry(
            plan="Plan C",
            repo="`org/repo-c`",
            file="docs/superpowers/plans/plan-c.md",
            status="Not Started",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Plan C" in text
        assert "plan-c.md" in text
        assert "plan-a.md" in text
        assert "plan-b.md" in text

    def test_prose_after_table_is_preserved(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE_WITH_PROSE)
        entry = IndexEntry(
            plan="Plan A",
            repo="`org/repo-a`",
            file="docs/superpowers/plans/plan-a.md",
            status="In Progress",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Cross-phase dependency note" in text
        assert "In Progress" in text


class TestBuildTable:
    def test_dash_file_not_backtick_quoted(self) -> None:
        entries = [
            IndexEntry(
                plan="Operator Row",
                repo="",
                file="—",
                status="Not Started",
                depends_on="Phase 3 deployed",
            ),
        ]
        table = _build_table(entries)
        assert "| — |" in table
        assert "| `—` |" not in table

    def test_path_file_is_backtick_quoted(self) -> None:
        entries = [
            IndexEntry(
                plan="Plan A",
                repo="",
                file="docs/plans/plan-a.md",
                status="Not Started",
                depends_on="—",
            ),
        ]
        table = _build_table(entries)
        assert "`docs/plans/plan-a.md`" in table

    def test_empty_file_rendered_as_dash(self) -> None:
        entries = [
            IndexEntry(plan="Plan A", repo="", file="", status="Not Started", depends_on="—"),
        ]
        table = _build_table(entries)
        assert "| — |" in table
