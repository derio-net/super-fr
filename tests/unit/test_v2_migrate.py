"""Tests for vk.v2.migrate — v1-to-v2 mechanical sweep."""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "archived-plans").mkdir()
    (tmp_path / "docs" / "superpowers" / "specs").mkdir()
    return tmp_path


def _write_v1_plan(repo: Path, *, slug: str, status: str = "Complete") -> Path:
    """Write a minimal v1 phased plan markdown file."""
    p = repo / "docs" / "superpowers" / "plans" / f"{slug}.md"
    p.write_text(
        f"# {slug.replace('-', ' ').title()}\n\n"
        f"**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        f"**Status:** {status}\n\n"
        f"## Phase 1: Setup [agentic]\n"
        f"**Depends on:** —\n\n"
        f"### Task 1: Initial setup\n\n"
        f"- [x] **Step 1: Do the first thing** Some details here.\n"
        f"- [ ] **Step 2: Do the second thing** More details.\n"
    )
    return p


def test_migrate_dry_run_lists_outcomes_without_writing(tmp_path):
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-fixture-v1")

    outcomes = migrate_repo(repo, dry_run=True)
    assert len(outcomes) == 1
    assert outcomes[0].reason == "migrated (dry run)"
    # Original .md still in place; no folder created
    assert md.exists()
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-v1").exists()


def test_migrate_apply_creates_v2_folder_and_archives_md(tmp_path):
    from vk.v2 import parse
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-fixture-v1")

    outcomes = migrate_repo(repo, dry_run=False)
    assert len(outcomes) == 1
    assert outcomes[0].reason == "migrated"

    # New folder exists
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-v1"
    assert new.is_dir()
    assert (new / "_meta.yaml").exists()
    assert (new / "_prose.md").exists()
    assert (new / "01.yaml").exists()

    # Original .md moved to .v1-archive
    assert not md.exists()
    assert md.with_suffix(".md.v1-archive").exists()

    # New plan parses cleanly
    plan = parse(new)
    assert plan.meta.plan == "2026-05-10-fixture-v1"
    # First step was [x] in v1 → state == "x" in v2
    assert plan.phases[0].state.steps["P1.T1.S1"].state == "x"
    assert plan.phases[0].state.steps["P1.T1.S2"].state == " "


def test_migrate_skips_in_progress_by_default(tmp_path):
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-complete", status="Complete")
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(repo, dry_run=False)
    by_name = {o.plan_path.stem: o.reason for o in outcomes}
    assert by_name["2026-05-10-complete"] == "migrated"
    assert by_name["2026-05-10-in-progress"].startswith("skipped (in-progress")


def test_migrate_include_in_progress_flag(tmp_path):
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(repo, dry_run=False, include_in_progress=True)
    assert outcomes[0].reason == "migrated"


def test_migrate_rewrites_spec_table_drops_status_column(tmp_path):
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-test.md"
    spec_path.write_text(
        "# test\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Status | Depends on |\n"
        "|------|------|------|--------|------------|\n"
        "| Some plan | `derio-net/x` | `docs/superpowers/plans/x/` | Complete | — |\n"
    )

    migrate_repo(repo, dry_run=False)
    new_text = spec_path.read_text()
    assert "Status" not in new_text.splitlines()[2]  # header line no longer has Status
    # The data row should have 4 cells now, no Status
    rows = [line for line in new_text.splitlines() if line.startswith("| Some plan")]
    assert len(rows) == 1
    assert rows[0].count("|") == 5  # 4 cells = 5 pipes


def test_migrate_rework_extracts_origin_table(tmp_path):
    from vk.v2 import parse
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-1.md"
    p.write_text(
        "# Base — Rework 1\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "**Parent plan:** "
        "`docs/superpowers/archived-plans/2026-05-08-base.md` (merged + archived)\n\n"
        "---\n\n"
        "## Origin\n\n"
        "| # | Item | Source | Track |\n"
        "|---|------|--------|-------|\n"
        "| 1 | first item | PR #50 review | development |\n"
        "| 2 | second item | demo | operations |\n\n"
        "---\n\n"
        "## Phase 1: Apply rework [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: Apply\n\n"
        "- [ ] **Step 1: Do the work** Details.\n"
    )

    migrate_repo(repo, dry_run=False)
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-1"
    plan = parse(new)
    assert plan.meta.parent_plan is not None
    assert "2026-05-08-base" in plan.meta.parent_plan
    assert len(plan.meta.origin_items) == 2
    assert plan.meta.origin_items[0].track == "development"
    assert plan.meta.origin_items[1].track == "operations"


def test_migrate_skips_already_migrated(tmp_path):
    from vk.v2.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-already")
    # Pre-create the v2 folder to simulate prior migration
    (repo / "docs" / "superpowers" / "plans" / "2026-05-10-already").mkdir()

    outcomes = migrate_repo(repo, dry_run=False)
    assert outcomes[0].reason.startswith("skipped (folder already exists)")


def test_migrate_rejects_per_phase_target_repo_conflict(tmp_path):
    """v1 plan with conflicting target_repo across phases → MigrationError."""
    from vk.v2.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-multi-target.md"
    p.write_text(
        "# Multi target\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: First [agentic]\n"
        "**Target repo:** derio-net/repo-a\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n"
        "- [x] **Step 1: x** d.\n\n"
        "## Phase 2: Second [agentic]\n"
        "**Target repo:** derio-net/repo-b\n"
        "**Depends on:** Phase 1\n\n"
        "### Task 1: t\n\n"
        "- [x] **Step 1: x** d.\n"
    )

    with pytest.raises(MigrationError, match="different target repos"):
        migrate_repo(repo, dry_run=False)


def test_migrate_cli_dry_run_and_yes_mutual_exclusion(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from vk.cli import app

    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["v2", "migrate", "v1-to-v2"])
    assert result.exit_code == 2  # neither --dry-run nor --yes
    result = runner.invoke(app, ["v2", "migrate", "v1-to-v2", "--dry-run", "--yes"])
    assert result.exit_code == 2  # both


def test_migrate_cli_apply_yes(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from vk.cli import app

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-cli-test")
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["v2", "migrate", "v1-to-v2", "--yes"])
    assert result.exit_code == 0, result.output
    assert "1 migrated" in result.output
