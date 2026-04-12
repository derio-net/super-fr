"""Tests for vk.git — subprocess wrappers for git operations."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from vk.git import add, commit, repo_root, status


class TestRepoRoot:
    def test_returns_path(self) -> None:
        with patch("vk.git._run_git", return_value="/home/user/repo") as mock:
            result = repo_root()
            assert result == Path("/home/user/repo")
            mock.assert_called_once_with(["rev-parse", "--show-toplevel"], cwd=None)

    def test_strips_trailing_newline(self) -> None:
        with patch("vk.git._run_git", return_value="/home/user/repo\n"):
            result = repo_root()
            assert result == Path("/home/user/repo")


class TestAdd:
    def test_add_single_file(self) -> None:
        with patch("vk.git._run_git") as mock:
            add(["src/main.py"])
            mock.assert_called_once_with(["add", "src/main.py"], cwd=None)

    def test_add_multiple_files(self) -> None:
        with patch("vk.git._run_git") as mock:
            add(["src/a.py", "src/b.py"])
            mock.assert_called_once_with(["add", "src/a.py", "src/b.py"], cwd=None)


class TestCommit:
    def test_commit_with_message(self) -> None:
        with patch("vk.git._run_git") as mock:
            commit("feat: add feature")
            mock.assert_called_once_with(["commit", "-m", "feat: add feature"], cwd=None)


class TestStatus:
    def test_status_returns_output(self) -> None:
        with patch("vk.git._run_git", return_value="M  src/main.py\n") as mock:
            result = status()
            assert "M  src/main.py" in result
            mock.assert_called_once_with(["status", "--porcelain"], cwd=None)


class TestRunGitError:
    def test_subprocess_error_raises(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                repo_root()
