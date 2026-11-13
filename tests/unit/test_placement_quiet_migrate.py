"""Under quiet, `fr migrate artifacts`, `fr validate artifacts` and the CLI-entry trigger
see the artifacts in the fr worktree's `features/*/`, and a migration commits there, one
commit per feature path (spec 2026-11-04 R23; review p3-r4).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.commit import commit_migration
from fr.artifacts.paths import KIND_DIRS
from fr.artifacts.registry import iter_artifact_paths
from fr.artifacts.runner import run_migrations
from fr.isolation.hostworktree import HostWorktreeTarget

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

STALE = "schema_version: 2\nplan: {slug}\ntarget_repo: derio-net/q\nfr_version: '>=3.0.0,<4.0.0'\n"


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    fr_root = Path(os.environ["HOME"]) / ".cache" / "fr" / "worktrees" / "work" / "fr"
    return state.worktree, fr_root


def _stale_plan(fr_root: Path, feature: str, slug: str) -> Path:
    meta = fr_root / "features" / feature / KIND_DIRS["plan"] / slug / "_meta.yaml"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(STALE.format(slug=slug))
    git(fr_root, "add", "-A")
    git(fr_root, "commit", "-qm", f"chore(fr): plan {slug}")
    return meta


def test_iter_paths_finds_every_feature_roots_artifacts(ws: tuple[Path, Path]) -> None:
    wt, fr_root = ws
    mine = _stale_plan(fr_root, "feat__q", "2026-11-12-a")
    theirs = _stale_plan(fr_root, "feat__other", "2026-11-12-b")
    found = list(iter_artifact_paths(wt, "plan"))
    assert mine in found and theirs in found


def test_repo_output_is_unchanged(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    meta = repo / KIND_DIRS["plan"] / "p" / "_meta.yaml"
    meta.parent.mkdir(parents=True)
    meta.write_text(STALE.format(slug="p"))
    assert list(iter_artifact_paths(repo, "plan")) == [meta]


def test_a_migration_commits_only_the_callers_feature_and_reports_the_other(
    ws: tuple[Path, Path],
) -> None:
    """Another branch's feature root may be live in its own workspace: it is reported,
    never rewritten or committed from here (R23, security review of p3-r4)."""
    wt, fr_root = ws
    mine = _stale_plan(fr_root, "feat__q", "2026-11-12-a")
    theirs = _stale_plan(fr_root, "feat__other", "2026-11-12-b")
    theirs_before = theirs.read_text()
    before = git(fr_root, "rev-parse", "HEAD").strip()
    report = run_migrations(wt, dry_run=False)
    assert report.changed_paths == (mine,)
    assert report.elsewhere == (theirs,)
    assert theirs.read_text() == theirs_before
    outcome = commit_migration(wt, report, fr_version="9.9.9")
    assert outcome.committed, outcome.reason
    log = git(fr_root, "log", "--format=%x00%s", "--name-only", f"{before}..HEAD")
    commits = [[n for n in b.split("\n")[1:] if n.strip()] for b in log.split("\x00")[1:]]
    assert commits == [["features/feat__q/docs/superpowers/plans/2026-11-12-a/_meta.yaml"]]
    assert not git(fr_root, "status", "--porcelain", "--untracked-files=no").strip()


def test_migrate_artifacts_reports_another_features_stale_artifact(
    ws: tuple[Path, Path],
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    wt, fr_root = ws
    _stale_plan(fr_root, "feat__other", "2026-11-12-b")
    env = {**os.environ, "FR_REPO_ROOT": str(wt)}
    result = CliRunner().invoke(app, ["migrate", "artifacts", "--yes"], env=env)
    flat = " ".join(result.output.split())
    assert "another feature's, not migrated here" in flat and "2026-11-12-b" in flat, flat


def test_validate_artifacts_sees_a_stale_plan_in_the_fr_worktree(ws: tuple[Path, Path]) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    wt, fr_root = ws
    _stale_plan(fr_root, "feat__other", "2026-11-12-b")
    env = {**os.environ, "FR_REPO_ROOT": str(wt)}
    result = CliRunner().invoke(app, ["validate", "artifacts"], env=env)
    assert result.exit_code != 0, result.output
    assert "2026-11-12-b" in result.output
