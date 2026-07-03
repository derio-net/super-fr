"""`archive_plan_dir` must refuse when the destination already exists (#334).

Regression from a real botched archive: a plan copied to implemented/plans/
but never removed from plans/ leaves a duplicate. `git mv plans/X
implemented/plans/X` then nests into the existing dir (implemented/plans/X/X),
silently corrupting the tree. The mover must refuse with a clear message so the
operator removes the stale plans/ copy instead."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fr.archive import ArchiveError, archive_plan_dir

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _seeded_repo_with_duplicate(tmp_path: Path) -> Path:
    slug = "2026-02-02-dup"
    plans = tmp_path / "docs" / "superpowers" / "plans" / slug
    implemented = tmp_path / "docs" / "superpowers" / "implemented" / "plans" / slug
    shutil.copytree(FIXTURE, plans)
    shutil.copytree(FIXTURE, implemented)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return tmp_path


def test_archive_refuses_when_destination_exists(tmp_path: Path) -> None:
    repo = _seeded_repo_with_duplicate(tmp_path)
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-02-02-dup"
    with pytest.raises(ArchiveError, match="already exists"):
        archive_plan_dir(repo, plan_dir)
    # The tree must be untouched — no nested implemented/plans/X/X.
    nested = (
        repo
        / "docs"
        / "superpowers"
        / "implemented"
        / "plans"
        / "2026-02-02-dup"
        / "2026-02-02-dup"
    )
    assert not nested.exists()
