"""Checkout tests use disposable git repos, never the repo under test."""

import subprocess

import pytest
from fr_herdr.runner import HerdrError, stable_checkout


def test_linked_worktree_uses_primary_checkout(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "init", str(base)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(base),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(base), "worktree", "add", "-b", "branch", str(linked)],
        check=True,
        capture_output=True,
    )
    assert stable_checkout(str(linked)) == str(base.resolve())


def test_missing_checkout_never_falls_back(tmp_path):
    with pytest.raises(HerdrError):
        stable_checkout(str(tmp_path / "missing"))
