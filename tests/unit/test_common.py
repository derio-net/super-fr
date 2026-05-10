"""Tests for vk.commands.common.resolve_repo_root.

The rest of the v1-era `common.py` (tri-state flags, error formatting,
gate refusal) was retired with the v1 commands. Only `resolve_repo_root`
survives — `vk apply`, `vk migrate`, etc. land in the operator's cwd by
default, but the env-var override is preserved for integration tests
that need to point at `tmp_path`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from vk.commands.common import resolve_repo_root


@pytest.fixture
def clear_env(monkeypatch):
    """Ensure VK_REPO_ROOT is unset for the test."""
    monkeypatch.delenv("VK_REPO_ROOT", raising=False)


def test_env_override_wins(monkeypatch, tmp_path):
    """$VK_REPO_ROOT takes precedence over git/cwd."""
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    assert resolve_repo_root() == tmp_path.resolve()


def test_empty_env_falls_through_to_git(monkeypatch, tmp_path):
    """Empty $VK_REPO_ROOT is treated as unset (so users can disable
    the override without unsetting it)."""
    monkeypatch.setenv("VK_REPO_ROOT", "")
    # Real git invocation in a tmp path that's not a repo → falls through to cwd
    monkeypatch.chdir(tmp_path)
    # subprocess will error since tmp_path isn't a git repo; we should land at cwd
    assert resolve_repo_root() == tmp_path.resolve()


def test_git_rev_parse_when_in_repo(clear_env, tmp_path):
    """When in a real git repo, returns the toplevel."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    sub = repo / "deep" / "nested"
    sub.mkdir(parents=True)
    assert resolve_repo_root(cwd=sub) == repo.resolve()


def test_falls_through_to_cwd_when_not_in_repo(clear_env, tmp_path, monkeypatch):
    """No env var, not in a git repo → returns cwd."""
    monkeypatch.chdir(tmp_path)
    assert resolve_repo_root() == tmp_path.resolve()


def test_resolves_symlinks(clear_env, tmp_path, monkeypatch):
    """Returned path is `.resolve()`-d so symlink-traversed paths stay comparable."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    monkeypatch.setenv("VK_REPO_ROOT", str(link))
    result = resolve_repo_root()
    assert result == real.resolve()
    assert os.path.realpath(result) == os.path.realpath(real)


def test_cwd_arg_passed_to_git(clear_env, tmp_path):
    """Explicit cwd is honored (used by integration tests)."""
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo_a)], check=True)
    subprocess.run(["git", "init", "--quiet", str(repo_b)], check=True)
    # Different cwds should resolve to different repo roots.
    assert resolve_repo_root(cwd=repo_a) == repo_a.resolve()
    assert resolve_repo_root(cwd=repo_b) == repo_b.resolve()


def test_returns_path_object(clear_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert isinstance(resolve_repo_root(), Path)
