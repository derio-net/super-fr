"""`fr archive --branch` outside `repo` appends `merged: <sha>` and moves nothing (spec
2026-11-04-repo-feature-settings R25; plan 2026-11-12-placement-resolver phase 5,
task 2). Close-out and `fr debt` read merged status through `merged_features`.

Every repo is a local sandbox with bare remotes; no forge is reached.
"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fr.acceptance.fold import clear_fold_cache
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import tracked_files
from tests.unit.test_placement_merged import ROW, Product, _home, _row, quiet, stealthy

__all__ = ["_home", "quiet", "stealthy"]

FIXTURE_PLAN = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
PLAN = "2026-11-13-a"


def _fr(root: Path, *argv: str):
    clear_fold_cache()
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(root)})


def _complete_plan(froot: Path) -> Path:
    plan = froot / KIND_DIRS["plan"] / PLAN
    shutil.copytree(FIXTURE_PLAN, plan)
    meta = yaml.safe_load((plan / "_meta.yaml").read_text())
    meta["plan"] = PLAN
    (plan / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    phase = yaml.safe_load((plan / "01.yaml").read_text())
    phase["state"]["completion"]["at"] = "2026-11-13T00:00:00+00:00"
    (plan / "01.yaml").write_text(yaml.safe_dump(phase, sort_keys=False))
    return plan


def _seed(product: Product, name: str, wt: Path, push: str = "origin fr") -> None:
    """Commit feature *name*'s root in the placement worktree *wt* and push it, so the
    archive's commit is the only one that follows."""
    git(wt, "add", "-A", "--", f"{product.feature_root(name).relative_to(wt)}")
    git(wt, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm",
        f"chore(fr): seed {name}")  # fmt: skip
    remote, branch = push.split()
    git(wt, "push", "-q", remote, f"HEAD:{branch}")


def _files(wt: Path, rev: str) -> list[str]:
    return git(wt, "show", "--format=", "--name-only", rev).split()


# --- quiet -------------------------------------------------------------------------


def test_archive_branch_records_merged_and_moves_nothing(quiet: Product) -> None:
    fr_root = quiet.space.root
    quiet.feature("a", rows=[_row(ROW)])
    _complete_plan(quiet.feature_root("a"))
    _seed(quiet, "a", fr_root)
    sha = quiet.merge("a")
    product_head = git(quiet.root, "rev-parse", "HEAD").strip()
    result = _fr(quiet.root, "archive", "--branch", "feat/a")
    assert result.exit_code == 0, result.output
    assert sha[:12] in result.output
    cache = quiet.feature_root("a") / "merged.yaml"
    assert yaml.safe_load(cache.read_text()) == [
        {"merged": sha, "head": git(quiet.root, "rev-parse", "feat/a").strip()}
    ]
    # one commit on fr, touching only the cache, and pushed
    assert _files(fr_root, "HEAD") == ["features/feat__a/merged.yaml"]
    assert git(fr_root, "rev-parse", "HEAD") == git(quiet.root, "rev-parse", "origin/fr")
    assert git(fr_root, "status", "--porcelain").strip() == ""
    # nothing moved: no implemented/ anywhere below the feature root, the plan in place
    assert not list(quiet.feature_root("a").rglob("implemented"))
    assert (quiet.feature_root("a") / KIND_DIRS["plan"] / PLAN / "_meta.yaml").is_file()
    # nothing on the product branch
    assert git(quiet.root, "rev-parse", "HEAD").strip() == product_head
    assert git(quiet.root, "status", "--porcelain", "--untracked-files=all").strip() == ""


def test_archive_branch_twice_writes_once(quiet: Product) -> None:
    quiet.feature("a")
    _seed(quiet, "a", quiet.space.root)
    quiet.merge("a")
    assert _fr(quiet.root, "archive", "--branch", "feat/a").exit_code == 0
    head = git(quiet.space.root, "rev-parse", "HEAD")
    again = _fr(quiet.root, "archive", "--branch", "feat/a")
    assert again.exit_code == 0, again.output
    assert "already recorded" in again.output
    assert git(quiet.space.root, "rev-parse", "HEAD") == head


def test_archive_branch_refuses_an_unmerged_branch(quiet: Product) -> None:
    quiet.feature("a")
    _seed(quiet, "a", quiet.space.root)
    head = git(quiet.space.root, "rev-parse", "HEAD")
    result = _fr(quiet.root, "archive", "--branch", "feat/a")
    assert result.exit_code == 2, result.output
    assert "not merged" in " ".join(result.output.split())
    assert not (quiet.feature_root("a") / "merged.yaml").exists()
    assert git(quiet.space.root, "rev-parse", "HEAD") == head


def test_archive_branch_with_no_feature_root_has_nothing_to_record(quiet: Product) -> None:
    quiet.feature("a")
    shutil.rmtree(quiet.feature_root("a"))
    quiet.merge("a")
    result = _fr(quiet.root, "archive", "--branch", "feat/a")
    assert result.exit_code == 0, result.output
    assert "nothing to archive" in result.output


def test_archive_without_branch_is_refused_naming_branch(quiet: Product) -> None:
    result = _fr(quiet.root, "archive", "--all")
    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert "not available under placement quiet" in flat and "--branch" in flat


# --- close-out and debt read merged status through merged_features ----------------


def test_plan_sweep_reads_merged_status_through_merged_features(quiet: Product) -> None:
    from fr.archive import merge_evidence
    from fr.closeout import owed_artifacts, plan_sweep

    quiet.feature("a")
    _complete_plan(quiet.feature_root("a"))
    _seed(quiet, "a", quiet.space.root)
    unmerged = plan_sweep(quiet.root, merge_evidence(quiet.root, fetch=False))
    assert unmerged.archivable == [] and unmerged.complete_unmerged == [PLAN]
    quiet.merge("a")
    sweep = plan_sweep(quiet.root, merge_evidence(quiet.root, fetch=False))
    assert sweep.archivable == [PLAN]
    assert sweep.commands[PLAN] == "fr archive --branch feat/a"
    owed = owed_artifacts(quiet.root, sweep.evidence).owed
    assert [o.clear for o in owed] == ["fr archive --branch feat/a"]
    assert _fr(quiet.root, "archive", "--branch", "feat/a").exit_code == 0
    done = plan_sweep(quiet.root, merge_evidence(quiet.root, fetch=False))
    assert done.archivable == [] and PLAN not in done.complete_unmerged  # archived


def test_debt_lists_a_merged_feature_plan_with_its_archive_command(quiet: Product) -> None:
    from fr.debt.engine import compute

    quiet.feature("a")
    _complete_plan(quiet.feature_root("a"))
    _seed(quiet, "a", quiet.space.root)
    quiet.merge("a")
    report = compute(quiet.root, forge=None, now=datetime.now(UTC))
    (plan,) = report.plans.archivable
    assert plan.name == PLAN and plan.command == "fr archive --branch feat/a"
    assert plan.merged_at is not None


# --- stealth -----------------------------------------------------------------------


def test_stealth_archive_records_in_the_tracking_repo_only(stealthy: Product) -> None:
    from fr.placement import stealth

    wt = stealth.tracking_root(stealthy.space)
    target_origin = Path(git(stealthy.ops, "remote", "get-url", "origin").strip())
    stealthy.feature("a")
    _seed(stealthy, "a", wt, push="origin main")
    sha = stealthy.merge("a")
    refs_before = git(target_origin, "for-each-ref", "--format=%(refname) %(objectname)")
    result = _fr(stealthy.root, "archive", "--branch", "feat/a")
    assert result.exit_code == 0, result.output
    track = Path(git(wt, "remote", "get-url", "origin").strip())
    rel = stealthy.feature_root("a").relative_to(wt).as_posix()
    assert f"{rel}/merged.yaml" in tracked_files(track)
    assert sha in git(track, "show", f"main:{rel}/merged.yaml")
    # nothing reached the target: its refs are exactly as before
    assert git(target_origin, "for-each-ref", "--format=%(refname) %(objectname)") == refs_before
    assert not list(stealthy.feature_root("a").rglob("implemented"))


def test_debt_dates_an_unmerged_feature_plan_by_its_branch(quiet: Product) -> None:
    """An unmerged feature's plan is dated by its code branch (named in OWNER), never
    listed with an unknown age because the product's history holds no fr file."""
    from fr.debt.engine import compute

    quiet.feature("a")
    plan = _complete_plan(quiet.feature_root("a"))
    phase = yaml.safe_load((plan / "01.yaml").read_text())
    phase["state"]["completion"]["at"] = None
    (plan / "01.yaml").write_text(yaml.safe_dump(phase, sort_keys=False))
    report = compute(quiet.root, forge=None, now=datetime.now(UTC), stale_days=30)
    assert [p.name for p in report.plans.stale] == []  # active today, by feat/a's commit
