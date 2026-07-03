"""`fr.archive.completed_unarchived_plans` — the gh-free "merged-but-unarchived"
predicate shared by the `fr status` repo sweep and the CI tripwire (#334)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml as _yaml

from fr.archive import completed_unarchived_plans

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _repo(tmp_path: Path) -> Path:
    sp = tmp_path / "docs" / "superpowers"
    (sp / "plans").mkdir(parents=True)
    (sp / "specs").mkdir()
    (sp / "implemented" / "plans").mkdir(parents=True)
    return tmp_path


def _add_plan(repo: Path, slug: str, *, ticked: bool) -> Path:
    """Copy the minimal fixture as plan <slug>. ticked=True → every step 'x'
    (locally complete); ticked=False → step ' ' (in progress)."""
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    meta = _yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    if ticked:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    return plan_dir


def _add_malformed(repo: Path, slug: str) -> Path:
    """A plan dir with a _meta.yaml that fails schema parse."""
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    plan_dir.mkdir(parents=True)
    (plan_dir / "_meta.yaml").write_text("this: is not a valid plan meta\n")
    return plan_dir


def test_complete_plan_is_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-01-01-done", ticked=True)
    assert completed_unarchived_plans(repo) == ["2026-01-01-done"]


def test_in_progress_plan_is_not_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-01-02-wip", ticked=False)
    assert completed_unarchived_plans(repo) == []


def test_malformed_plan_is_skipped_not_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_malformed(repo, "2026-01-03-broken")
    # A malformed plan is a different problem — it must not wedge the check.
    assert completed_unarchived_plans(repo) == []


def test_mixed_returns_only_complete_sorted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-01-05-done-b", ticked=True)
    _add_plan(repo, "2026-01-04-done-a", ticked=True)
    _add_plan(repo, "2026-01-06-wip", ticked=False)
    _add_malformed(repo, "2026-01-07-broken")
    assert completed_unarchived_plans(repo) == ["2026-01-04-done-a", "2026-01-05-done-b"]


def test_no_plans_dir_returns_empty(tmp_path: Path) -> None:
    # A repo without docs/superpowers/plans/ must not raise.
    assert completed_unarchived_plans(tmp_path) == []
