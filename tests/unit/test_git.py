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


def _git(args: list[str], cwd: Path) -> None:
    """Test helper: run git with check=True; raises on failure."""
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo_with_commit(tmp_path: Path) -> Path:
    """Init a git repo at tmp_path and commit a single file. Returns repo path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "tracked.txt").write_text("hi\n")
    _git(["add", "tracked.txt"], repo)
    _git(["commit", "-q", "-m", "init"], repo)
    return repo


def test_file_on_ref_true_for_committed_path(tmp_path):
    from vk.git import file_on_ref

    repo = _init_repo_with_commit(tmp_path)
    assert file_on_ref("HEAD", "tracked.txt", cwd=repo) is True


def test_file_on_ref_false_for_uncommitted_path(tmp_path):
    from vk.git import file_on_ref

    repo = _init_repo_with_commit(tmp_path)
    (repo / "untracked.txt").write_text("not committed\n")
    assert file_on_ref("HEAD", "untracked.txt", cwd=repo) is False


def test_file_on_ref_false_for_nonexistent_path(tmp_path):
    from vk.git import file_on_ref

    repo = _init_repo_with_commit(tmp_path)
    assert file_on_ref("HEAD", "nope/missing.txt", cwd=repo) is False


def test_file_on_ref_raises_on_unknown_ref(tmp_path):
    """Unknown refs surface a GhError-equivalent — caller catches."""
    repo = _init_repo_with_commit(tmp_path)
    from vk.git import file_on_ref

    with pytest.raises(Exception):
        file_on_ref("origin/HEAD", "tracked.txt", cwd=repo)
