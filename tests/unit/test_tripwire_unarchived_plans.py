"""CI tripwire: no merged-but-unarchived plan may linger in plans/ (#334).

The fr lifecycle moves a completed plan from docs/superpowers/plans/ to
implemented/plans/. That archive step kept getting skipped (issue #334). This
guard fails loud when a plan that has ALREADY MERGED to origin/main is still
sitting complete in plans/ — so a forgotten post-merge archive turns CI red
until it is done, while an in-progress plan (new in the current branch, not yet
on main) is deliberately NOT flagged.

Signal = `fr.archive.completed_unarchived_plans` (completeness in the working
tree, i.e. the post-merge state) ∩ "already present on origin/main". The
working-tree read is what lets the PR that REMOVES a stale plan pass: the plan
is gone from the tree, so it is not a candidate. The origin/main intersection
is what keeps the PR that INTRODUCES a plan green: a brand-new plan is not on
main yet. Offline apart from reading the local origin/main ref (CI fetches it
via fetch-depth: 0); skips cleanly when origin/main is unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
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


def _plan_on_origin_main(repo_root: Path, name: str) -> bool:
    return (
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "cat-file",
                "-e",
                f"origin/main:docs/superpowers/plans/{name}/_meta.yaml",
            ],
            capture_output=True,
        ).returncode
        == 0
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_merged_but_unarchived_plans() -> None:
    """The backstop. A plan that is complete in the tree AND already on
    origin/main was merged and never archived — run `fr archive --all`."""
    if not _origin_main_available(REPO_ROOT):
        pytest.skip("origin/main not available (shallow checkout?)")
    complete = completed_unarchived_plans(REPO_ROOT)
    offenders = [n for n in complete if _plan_on_origin_main(REPO_ROOT, n)]
    assert offenders == [], (
        "merged-but-unarchived plan(s) in docs/superpowers/plans/ (complete and "
        f"already on origin/main): {offenders}. Run `fr archive --all` to move "
        "them to implemented/."
    )
