"""Container git ownership: fr's record-commit git calls survive a foreign-owned
worktree (spec 2026-09-26-container-git-ownership §3.A/§3.B).

Simulated with git's own test hook GIT_TEST_ASSUME_DIFFERENT_OWNER=1 and an empty
global config, so `safe.directory` can only come from fr's own `-c` override.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from fr import git as fr_git
from fr.artifacts.commit import commit_paths
from fr.git import safe_directory_args
from fr.isolation.scaffold import POST_CREATE
from fr.record import apply as record_apply


def _git_version() -> tuple[int, ...]:
    out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


needs_ownership_hook = pytest.mark.skipif(
    _git_version() < (2, 35, 2),
    reason="GIT_TEST_ASSUME_DIFFERENT_OWNER needs git >= 2.35.2",
)


def _sh(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def linked_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(var, raising=False)
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    base = tmp_path / "base"
    base.mkdir()
    _sh(base, "init", "-q", "-b", "main")
    _sh(base, "config", "user.email", "t@example.com")
    _sh(base, "config", "user.name", "t")
    (base / "seed.txt").write_text("seed\n")
    _sh(base, "add", "seed.txt")
    _sh(base, "commit", "-q", "-m", "seed")
    wt = tmp_path / "wt"
    _sh(base, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    (wt / "sub" / "deep").mkdir(parents=True)
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    return wt.resolve()


@needs_ownership_hook
def test_hook_really_refuses_without_the_override(linked_worktree: Path) -> None:
    done = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=linked_worktree,
        capture_output=True,
        text=True,
    )
    assert done.returncode != 0
    assert "dubious ownership" in done.stderr


@needs_ownership_hook
@pytest.mark.parametrize("sub", [".", "sub/deep"])
def test_commit_paths_commits_in_a_foreign_owned_worktree(linked_worktree: Path, sub: str) -> None:
    f = linked_worktree / "rec.txt"
    f.write_text("x\n")
    out = commit_paths(linked_worktree / sub, [f], "chore(fr): record")
    assert out.committed, out.reason


@needs_ownership_hook
def test_record_apply_git_helpers_answer_correctly(linked_worktree: Path) -> None:
    seed = linked_worktree / "seed.txt"
    assert record_apply._is_tracked(linked_worktree, seed) is True
    assert record_apply._is_tracked(linked_worktree, linked_worktree / "nope.txt") is False
    assert record_apply._short_head(linked_worktree)


def test_safe_directory_for_a_plain_repo_from_a_subdirectory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "a" / "b").mkdir(parents=True)
    want = ["-c", f"safe.directory={tmp_path.resolve()}"]
    assert safe_directory_args(tmp_path) == want
    assert safe_directory_args(tmp_path / "a" / "b") == want


def test_safe_directory_for_a_linked_worktree_git_file(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n")
    (tmp_path / "sub").mkdir()
    want = ["-c", f"safe.directory={tmp_path.resolve()}"]
    assert safe_directory_args(tmp_path) == want
    assert safe_directory_args(tmp_path / "sub") == want


def test_safe_directory_resolves_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / ".git").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    assert safe_directory_args(link) == ["-c", f"safe.directory={real.resolve()}"]


def test_safe_directory_outside_any_repo_is_empty(tmp_path: Path) -> None:
    # tmp_path lives under the system tmp dir, which is not inside a repo
    assert safe_directory_args(tmp_path) == []


def test_git_answer_places_the_override_before_the_subcommand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(fr_git.subprocess, "run", fake_run)
    fr_git.git_answer(tmp_path, "rev-parse", "HEAD")
    assert seen[0] == [
        "git",
        "-c",
        f"safe.directory={tmp_path.resolve()}",
        "rev-parse",
        "HEAD",
    ]


def test_post_create_trusts_the_workspace() -> None:
    assert 'git config --global --add safe.directory "$PWD" || true' in POST_CREATE


def test_committed_profiles_carry_the_scaffold_post_create() -> None:
    root = Path(__file__).resolve().parents[2]
    for profile in ("dev", "admin"):
        cfg = json.loads((root / ".devcontainer" / profile / "devcontainer.json").read_text())
        assert cfg["postCreateCommand"] == POST_CREATE, profile


def test_index_restore_carries_the_override_before_the_subcommand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import commit as commit_mod

    (tmp_path / ".git").mkdir()
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(commit_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        commit_mod, "_git", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", "")
    )
    assert commit_mod._restore_index(tmp_path, ["x"], "100644 abc 0\tx") == ""
    assert seen[0][:4] == ["git", "-c", f"safe.directory={tmp_path.resolve()}", "update-index"]
