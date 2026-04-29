"""Tests for _reconcile_spec_index column preservation (Thread 2 fix)."""

from __future__ import annotations

import shutil
from pathlib import Path

from vk.commands.progress_cmd import _reconcile_spec_index
from vk.spec_index import read_index

SPEC_WITH_RICH_ROW = """\
# My Spec

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo` | `docs/superpowers/plans/plan-a.md` | Not Started | Phase X of repo-b |

Cross-phase note: important prose.
"""

PLAN_CONTENT = """\
# Plan A

**Spec:** `docs/superpowers/specs/my-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Work [agentic]
**Depends on:** —

### Task 1: Do thing

- [x] **Step 1: Done**
"""


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    plans_dir = tmp_path / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True)
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "my-spec.md"
    spec_path.write_text(SPEC_WITH_RICH_ROW)
    plan_path = plans_dir / "plan-a.md"
    plan_path.write_text(PLAN_CONTENT)
    return tmp_path, spec_path, plan_path


def test_reconcile_preserves_repo_and_depends_on(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A",
        status="In Progress",
        repo_root=repo_root,
    )
    assert updated is True
    entries = read_index(spec_path)
    matching = [e for e in entries if "plan-a.md" in e.file]
    assert len(matching) == 1
    row = matching[0]
    assert row.status == "In Progress"
    assert row.repo == "`org/repo`"
    assert row.depends_on == "Phase X of repo-b"
    # Prose preserved
    assert "Cross-phase note" in spec_path.read_text()


def test_reconcile_noop_when_status_and_title_match(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A",
        status="Not Started",
        repo_root=repo_root,
    )
    assert updated is False


def test_reconcile_updates_title_when_changed(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A (revised)",
        status="Not Started",
        repo_root=repo_root,
    )
    assert updated is True
    text = spec_path.read_text()
    assert "Plan A (revised)" in text
    assert text.count("plan-a.md") == 1  # no duplicate


def test_reconcile_archive_rename_updates_file_path(tmp_path: Path) -> None:
    """prev_plan_path causes the old-path row to be found and rewritten with new path."""
    repo_root, spec_path, plan_path = _setup(tmp_path)

    # Simulate archive: plan moved to archived-plans/
    archive_dir = tmp_path / "docs" / "superpowers" / "archived-plans"
    archive_dir.mkdir(parents=True)
    archived_path = archive_dir / "plan-a.md"
    shutil.copy(plan_path, archived_path)

    # First sync already wrote status=Complete at old path (simulate that state)
    from vk.spec_index import IndexEntry, upsert_entry

    upsert_entry(
        spec_path,
        IndexEntry(
            plan="Plan A",
            repo="`org/repo`",
            file="docs/superpowers/plans/plan-a.md",
            status="Complete",
            depends_on="Phase X of repo-b",
        ),
    )

    # Archive reconcile: plan_path=archived_path, prev_plan_path=original plan_path
    updated = _reconcile_spec_index(
        plan_path=archived_path,
        plan_title="Plan A",
        status="Complete",
        repo_root=repo_root,
        prev_plan_path=plan_path,
    )
    assert updated is True
    entries = read_index(spec_path)
    # New path present, old path gone
    assert any("archived-plans/plan-a.md" in e.file for e in entries)
    assert not any(e.file == "docs/superpowers/plans/plan-a.md" for e in entries)
    # Only one row total
    assert len(entries) == 1
    row = entries[0]
    assert row.status == "Complete"
    assert row.repo == "`org/repo`"
    assert row.depends_on == "Phase X of repo-b"
