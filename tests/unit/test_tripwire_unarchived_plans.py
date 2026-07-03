"""CI tripwire: no merged-but-unarchived plan may linger in plans/ (#334).

The fr lifecycle moves a completed plan from docs/superpowers/plans/ to
implemented/plans/. That archive step kept getting skipped (issue #334). This
guard fails loud when a plan that merged COMPLETE to origin/main is still
sitting in plans/ — so a forgotten post-merge archive turns CI red until it is
done, while in-progress work is deliberately NOT flagged.

Signal = "complete on origin/main" ∩ "still present in the working-tree plans/",
both computed with the one `fr.archive.completed_unarchived_plans` predicate:
- the origin/main arm materializes origin/main's plans/ subtree and runs the
  predicate on it, so it fires only on plans that genuinely merged complete —
  excluding a brand-new plan (not on main) AND the PR that FINISHES a multi-PR
  plan whose dir landed on main incomplete (main is still incomplete there);
- the working-tree arm lets the PR that ARCHIVES/removes a stale plan pass (the
  dir is gone from the tree).
Offline apart from reading the local origin/main ref (CI fetches it via
fetch-depth: 0); skips cleanly when origin/main is unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml as _yaml
from fr.archive import completed_unarchived_plans

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _add_plan(repo: Path, slug: str, *, complete: bool) -> None:
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    meta = _yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    if complete:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))


def test_predicate_flags_completed_plan(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-01-01-done", complete=True)
    assert completed_unarchived_plans(tmp_path) == ["2026-01-01-done"]


def test_predicate_ignores_in_progress_plan(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-01-02-wip", complete=False)
    assert completed_unarchived_plans(tmp_path) == []


def _origin_main_available(repo_root: Path) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", "origin/main"],
            capture_output=True,
        ).returncode
        == 0
    )


def _completed_plans_on_origin_main(repo_root: Path) -> list[str]:
    """Plans that are complete AS THEY EXIST ON origin/main.

    Materialize origin/main's plans/ subtree and run the same predicate on it.
    Completeness-on-main (not mere presence) is what excludes the PR that
    *finishes* a plan whose dir landed on main incomplete in an earlier PR —
    main is still incomplete there, so it is not an offender. Returns [] when
    origin/main has no plans/ tree."""
    ls = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "origin/main", "docs/superpowers/plans"],
        capture_output=True,
        text=True,
    )
    if not ls.stdout.strip():
        return []
    archived = subprocess.run(
        ["git", "-C", str(repo_root), "archive", "origin/main", "docs/superpowers/plans"],
        capture_output=True,
    )
    if archived.returncode != 0:
        return []
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["tar", "-x", "-C", td], input=archived.stdout, check=True)
        return completed_unarchived_plans(Path(td))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def _offenders(repo: Path) -> list[str]:
    plans_dir = repo / "docs" / "superpowers" / "plans"
    return [
        n for n in _completed_plans_on_origin_main(repo) if (plans_dir / n / "_meta.yaml").exists()
    ]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_incomplete_on_main_completed_in_tree_is_not_flagged(tmp_path: Path) -> None:
    """Finding #1: the PR that FINISHES a plan landed incomplete on main must
    not be red-flagged — main is still incomplete there."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-01-multi", complete=False)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan incomplete")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    # Complete it in the working tree (this branch finishes the work).
    phase = tmp_path / "docs" / "superpowers" / "plans" / "2026-03-01-multi" / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    assert completed_unarchived_plans(tmp_path) == ["2026-03-01-multi"]  # complete in tree
    assert _offenders(tmp_path) == []  # but not complete on main → not an offender


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_complete_on_main_still_in_tree_is_flagged(tmp_path: Path) -> None:
    """A plan complete on origin/main and still sitting in plans/ is the
    merged-but-unarchived offender."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-02-done", complete=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan complete, unarchived")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    assert _offenders(tmp_path) == ["2026-03-02-done"]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_complete_on_main_but_archived_in_tree_is_not_flagged(tmp_path: Path) -> None:
    """The PR that ARCHIVES a stale plan passes: the dir is gone from the
    working-tree plans/, so it is not an offender even though main still has
    it complete."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "implemented" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-03-done", complete=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan complete, unarchived")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    # This branch archives it → removed from plans/ in the working tree.
    shutil.rmtree(tmp_path / "docs" / "superpowers" / "plans" / "2026-03-03-done")
    assert _offenders(tmp_path) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_merged_but_unarchived_plans() -> None:
    """The backstop. A plan complete ON origin/main that is still sitting in
    the working tree's plans/ was merged and never archived — run
    `fr archive --all`.

    Signal = complete-on-origin-main ∩ still-present-in-working-tree-plans/.
    The origin/main arm fires only on plans that genuinely merged complete
    (excludes the finishing PR of a multi-PR plan). The working-tree arm lets
    the PR that archives/removes a stale plan pass (the dir is gone from the
    tree)."""
    if not _origin_main_available(REPO_ROOT):
        pytest.skip("origin/main not available (shallow checkout?)")
    plans_dir = REPO_ROOT / "docs" / "superpowers" / "plans"
    offenders = [
        n
        for n in _completed_plans_on_origin_main(REPO_ROOT)
        if (plans_dir / n / "_meta.yaml").exists()
    ]
    assert offenders == [], (
        "merged-but-unarchived plan(s) — complete on origin/main but still in "
        f"docs/superpowers/plans/: {offenders}. Run `fr archive --all` to move "
        "them to implemented/."
    )
