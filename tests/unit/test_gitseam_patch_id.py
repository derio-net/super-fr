"""`Checkout.patch_id`: the content an approval is pinned to (spec
2026-11-19-wave-merge-queue R12, §E), against a real throwaway repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.triage.gitseam import Checkout


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(cwd: Path, message: str, *, empty: bool = False) -> str:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "--quiet", *(["--allow-empty"] if empty else []), "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """`main` with two files, and `feat` branched from it with one code change."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", k, v)
    (root / "code.py").write_text("def f():\n    return 1\n")
    (root / "other.txt").write_text("other\n")
    _commit(root, "seed")
    _git(root, "checkout", "--quiet", "-b", "feat")
    (root / "code.py").write_text("def f():\n    return 2\n")
    _commit(root, "feat: change f")
    return root


def test_a_conflict_free_merge_of_main_keeps_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    _git(repo, "checkout", "--quiet", "main")
    (repo / "other.txt").write_text("other, moved on main\n")
    _commit(repo, "main moves")
    _git(repo, "checkout", "--quiet", "feat")
    _git(repo, "merge", "--quiet", "--no-edit", "main")

    assert before
    assert checkout.patch_id("feat", "main") == before


def test_an_empty_commit_keeps_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    _commit(repo, "nothing", empty=True)

    assert checkout.patch_id("feat", "main") == before


def test_a_code_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    (repo / "code.py").write_text("def f():\n    return 3\n")
    _commit(repo, "edit")

    assert checkout.patch_id("feat", "main") != before


def test_a_whitespace_only_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    (repo / "code.py").write_text("def f():\n    return 2 \n")
    _commit(repo, "trailing space")

    assert checkout.patch_id("feat", "main") != before


def test_a_binary_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    (repo / "blob.bin").write_bytes(bytes(range(256)))
    _commit(repo, "add a binary")
    before = checkout.patch_id("feat", "main")
    (repo / "blob.bin").write_bytes(bytes(reversed(range(256))))
    _commit(repo, "edit the binary")

    assert checkout.patch_id("feat", "main") != before


def test_an_empty_diff_has_an_empty_patch_id(repo: Path) -> None:
    assert Checkout(repo).patch_id("main", "main") == ""
