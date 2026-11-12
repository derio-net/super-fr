"""Under quiet, fr's artifacts and `chore(fr):` commits land in the fr worktree, one
feature path per commit, and never on the product branch (spec 2026-11-04 R23
"append-only", "nothing on the product branches"; plan phase 3, task 3).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

FEATURE = "feat__q"


def _fr(cwd: Path, *argv: str) -> str:
    env = {**os.environ, "VK_REPO_ROOT": str(cwd), "FR_ISOLATION_TARGET": "worktree"}
    result = CliRunner().invoke(app, list(argv), env=env)
    assert result.exit_code == 0, result.output
    return result.output


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    # Some commands read the cwd, not VK_REPO_ROOT: never let one reach this checkout.
    monkeypatch.chdir(state.worktree)
    fr_root = Path(os.environ["HOME"]) / ".cache" / "fr" / "worktrees" / "work" / "fr"
    return state.worktree, fr_root


def _fr_commits(fr_root: Path) -> list[tuple[str, list[str]]]:
    out = git(fr_root, "log", "--format=%x00%s", "--name-only", "origin/fr..fr")
    commits = []
    for block in out.split("\x00")[1:]:
        lines = [x for x in block.splitlines() if x.strip()]
        commits.append((lines[0], lines[1:]))
    return commits


def _product_is_clean(worktree: Path) -> None:
    files = git(worktree, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    roots = {KIND_DIRS["superpowers"], KIND_DIRS["acceptance"]}
    assert not [f for f in files if any(f.startswith(r + "/") for r in roots)]
    subjects = git(worktree, "log", "--format=%s", "origin/main..HEAD").splitlines()
    assert not [s for s in subjects if s.startswith("chore(fr)")]


def test_plan_and_journal_land_in_the_feature_path(workspace: tuple[Path, Path]) -> None:
    worktree, fr_root = workspace
    _fr(worktree, "plan", "create", "--slug", "2026-11-12-q", "--target-repo", "derio-net/q")
    _fr(
        worktree,
        "journal", "add", "--scope", "plan", "--slug", "2026-11-12-q", "--kind", "discovery",
        "--title", "t", "--body", "b", "--global",
    )  # fmt: skip
    feature = fr_root / "features" / FEATURE
    assert (feature / KIND_DIRS["plan"] / "2026-11-12-q" / "_meta.yaml").is_file()
    assert (feature / KIND_DIRS["journal-plans"] / "2026-11-12-q.md").is_file()
    commits = _fr_commits(fr_root)
    assert commits, "fr committed nothing on the fr branch"
    for subject, names in commits:
        assert names and all(n.startswith(f"features/{FEATURE}/") for n in names), (subject, names)
    _product_is_clean(worktree)


def test_run_start_writes_its_cursor_in_the_fr_worktree(workspace: tuple[Path, Path]) -> None:
    worktree, fr_root = workspace
    _fr(worktree, "run", "start", "fr-goal", "--branch", "feat/q")
    runs = fr_root / "features" / FEATURE / KIND_DIRS["run"]
    assert list(runs.glob("*.yaml")), "no run cursor under the feature path"
    # every later `fr run` reads the cursor back from there
    (cursor,) = runs.glob("*.yaml")
    assert "brainstorm" in _fr(worktree, "run", "status", cursor.stem)
    for _, names in _fr_commits(fr_root):
        assert all(n.startswith(f"features/{FEATURE}/") for n in names)
    _product_is_clean(worktree)


def test_a_commit_outside_the_feature_path_is_refused(workspace: tuple[Path, Path]) -> None:
    from fr.artifacts.commit import commit_paths

    worktree, fr_root = workspace
    other = fr_root / "features" / "feat__other" / "x.md"
    other.parent.mkdir(parents=True)
    other.write_text("x\n")
    outcome = commit_paths(worktree, [other], "chore(fr): sneak")
    assert not outcome.committed
    assert f"features/{FEATURE}/" in outcome.reason


def test_code_tree_under_quiet_excludes_nothing(workspace: tuple[Path, Path]) -> None:
    from fr.run.code_tree import code_tree, is_code_path

    worktree, _ = workspace
    assert not is_code_path(f"{KIND_DIRS['plan']}/x/_meta.yaml")  # repo's rule unchanged
    (worktree / KIND_DIRS["superpowers"]).mkdir(parents=True)
    (worktree / KIND_DIRS["superpowers"] / "notes.md").write_text("product doc\n")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "feat(q): product docs")
    import hashlib

    entries = [
        e for e in git(worktree, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split("\0") if e
    ]
    assert any(e.endswith(f"{KIND_DIRS['superpowers']}/notes.md") for e in entries)
    whole = hashlib.sha256("\0".join(entries).encode()).hexdigest()
    assert code_tree(worktree) == whole
