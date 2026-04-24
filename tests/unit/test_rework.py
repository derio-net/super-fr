"""Unit tests for src/vk/plan/rework.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from vk.plan.rework import (
    OriginRow,
    append_origin_row,
    next_rework_number,
    parse_origin_table,
    render_scaffold,
)

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# placeholder\n")


class TestNextReworkNumber:
    def test_no_existing_reworks_returns_1(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        assert next_rework_number(parent, repo_root=tmp_path) == 1

    def test_active_rework_1_returns_2(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 2

    def test_archived_rework_1_returns_2(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 2

    def test_gaps_tolerated(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-3.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 4

    def test_collision_across_dirs_raises(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        with pytest.raises(ValueError, match="ambiguous rework state"):
            next_rework_number(parent, repo_root=tmp_path)

    def test_concurrent_active_reworks_allowed(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-2.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 3


class TestRenderScaffold:
    def test_archived_parent_with_spec_and_title(self) -> None:
        out = render_scaffold(
            parent_title="Parental Controls Plan",
            parent_slug_date="2026-04-08-kid-laptops-5-parental-controls",
            spec="docs/superpowers/specs/2026-04-07-kid-laptops-design.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-kid-laptops-5-parental-controls.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert out.startswith("# Parental Controls Plan — Rework 1\n")
        assert "**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`" in out
        assert "(merged + archived)" in out
        assert "**Prior rework:**" not in out
        assert "## Origin" in out
        assert "| # | Item | Source | Track |" in out
        assert "## Definition of Done" in out

    def test_unarchived_parent_annotation(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/plans/2026-04-08-foo.md",
            parent_archived=False,
            n=1,
            prior_rework_rel_path=None,
        )
        assert "(not yet archived)" in out

    def test_prior_rework_rendered(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=2,
            prior_rework_rel_path="docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md",
        )
        assert (
            "**Prior rework:** `docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md`" in out
        )
        assert out.split("# Foo — Rework 2")[0] == ""

    def test_no_spec_line_when_spec_none(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec=None,
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert "**Spec:**" not in out

    def test_fallback_title_when_parent_title_empty(self) -> None:
        out = render_scaffold(
            parent_title="",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert out.startswith("# Rework 1 for 2026-04-08-foo\n")


class TestParseOriginTable:
    def test_empty_table(self) -> None:
        rows = parse_origin_table(FIXTURES / "rework_empty.md")
        assert rows == []

    def test_three_rows_with_pipe_escape_unescaped(self) -> None:
        rows = parse_origin_table(FIXTURES / "rework_with_rows.md")
        assert rows == [
            OriginRow(number=1, item="Wire | pipe in item", source="PR #42", track="development"),
            OriginRow(number=2, item="Smoke test the deploy", source="demo", track="operations"),
            OriginRow(
                number=3, item="Decide on theme palette", source="design review", track="decision"
            ),
        ]

    def test_malformed_header_raises(self) -> None:
        with pytest.raises(ValueError, match="Origin table header malformed"):
            parse_origin_table(FIXTURES / "rework_malformed_origin.md")

    def test_missing_origin_section_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "no_origin.md"
        p.write_text("# T\n\n**Status:** Not Started\n\n**Goal:** g\n")
        with pytest.raises(ValueError, match="no ## Origin section"):
            parse_origin_table(p)


class TestAppendOriginRow:
    def test_append_to_empty_table(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        row = OriginRow(number=1, item="Ship docs", source="PR #42", track="development")
        append_origin_row(p, row)
        rows = parse_origin_table(p)
        assert rows == [row]

    def test_append_preserves_dod(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        append_origin_row(p, OriginRow(1, "x", "y", "development"))
        text = p.read_text()
        assert "## Definition of Done" in text
        assert "- [ ] TODO." in text

    def test_append_escapes_pipes(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        append_origin_row(p, OriginRow(1, "wire | pipe", "src | with pipe", "development"))
        text = p.read_text()
        assert r"wire \| pipe" in text
        assert r"src \| with pipe" in text
        # Round-trip unescapes.
        rows = parse_origin_table(p)
        assert rows[0].item == "wire | pipe"
        assert rows[0].source == "src | with pipe"

    def test_append_after_existing_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_with_rows.md").read_text())
        append_origin_row(p, OriginRow(4, "new item", "PR #99", "operations"))
        rows = parse_origin_table(p)
        assert len(rows) == 4
        assert rows[3] == OriginRow(4, "new item", "PR #99", "operations")
