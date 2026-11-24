"""`scripts/ci_lane.py`: which lane a CI run takes, and whether `ci-ok` passes it
(spec 2026-11-24-ci-economy R5, R15, R17).

The fixture repos live under `tmp_path`; the forge payloads are captures
(`tests/fixtures/ci_lane/README.md`). Nothing here reads this checkout's git state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import ci_lane  # noqa: E402

# ── Task 1: lane_for and classify (R15) ───────────────────────────────────


@pytest.mark.parametrize(
    "paths",
    [
        ["docs/x.md"],
        [".changes/a.yaml"],
        ["README.md"],
        [".test_durations"],
        ["docs/superpowers/runs/r.yaml", "AGENTS.md", ".changes/b.yaml"],
    ],
)
def test_a_change_with_nothing_installable_tested_or_in_ci_is_light(paths: list[str]) -> None:
    assert ci_lane.lane_for(paths) == "light"


@pytest.mark.parametrize(
    "paths",
    [
        ["packages/fr/src/fr/x.py"],
        ["scripts/x.py"],
        ["plugins/super-fr/skills/a/SKILL.md"],
        ["tests/unit/test_x.py"],
        [".github/workflows/ci.yml"],
        ["docs/x.md", "packages/fr/src/fr/x.py"],
        ["docs/x.md", "tests/conftest.py"],
        [],
    ],
)
def test_an_installable_tested_or_ci_path_or_no_path_is_full(paths: list[str]) -> None:
    assert ci_lane.lane_for(paths) == "full"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _write_commit(repo: Path, rel: str, message: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return tmp_path


def _pr_checkout(tmp: Path, pr_path: str, *, base_moves: str | None = None) -> Path:
    """A clone checked out the way `pull_request` checks out: HEAD is a merge commit
    whose first parent is the base tip and second parent the PR head."""
    origin = tmp / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _write_commit(origin, "packages/fr/src/fr/x.py", "base")
    _git(origin, "checkout", "-q", "-b", "feat/x")
    _write_commit(origin, pr_path, "pr change")
    _git(origin, "checkout", "-q", "main")
    if base_moves:
        _write_commit(origin, base_moves, "base moves")
    clone = tmp / "clone"
    _git(tmp, "clone", "-q", str(origin), str(clone))
    _git(clone, "fetch", "-q", "origin", "feat/x")
    _git(clone, "merge", "-q", "--no-ff", "-m", "merge", "FETCH_HEAD")
    return clone


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if line)


def test_classify_reads_a_docs_only_pull_request_as_light(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    out = isolated_git / "github_output"
    code = ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert code == 0
    assert _outputs(out) == {"lane": "light"}


def test_classify_diffs_against_the_merge_base_not_the_moved_base_tip(isolated_git: Path) -> None:
    # The base moved an installable path after the PR branched: that is not the PR's change.
    clone = _pr_checkout(isolated_git, "docs/guide.md", base_moves="scripts/y.py")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "light"}


def test_classify_reads_an_installable_pull_request_as_full(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "packages/fr/src/fr/y.py")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "full"}


def test_classify_reads_a_single_parent_head_against_the_merge_base(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    _git(clone, "reset", "-q", "--hard", "HEAD^2")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "light"}


def test_classify_is_full_when_git_cannot_read_the_diff(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    out = isolated_git / "github_output"
    code = ci_lane.main(
        ["classify", "--base", "no-such-branch"], cwd=clone, env={"GITHUB_OUTPUT": str(out)}
    )
    assert code == 0
    assert _outputs(out) == {"lane": "full"}


def test_classify_is_full_outside_a_git_repo(isolated_git: Path) -> None:
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=isolated_git, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "full"}
