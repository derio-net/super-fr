"""Tests for vk.spec_index — read/create/update Implementation Plans table."""

from pathlib import Path

from vk.spec_index import IndexEntry, read_index, upsert_entry

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
        file="plans/core.md",
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
