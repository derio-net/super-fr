"""Tests for vk.gh — subprocess wrappers for gh CLI operations.

These are contract tests: they verify the correct gh invocations
are constructed, using mocked subprocess calls.
"""

import subprocess
from unittest.mock import patch

import pytest

from vk.gh import GhError, add_to_project, auth_status, close_issue, create_issue, set_field


class TestCreateIssue:
    def test_basic_creation(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/42") as mock:
            url = create_issue(
                repo="org/repo",
                title="Phase 1: Setup",
                body="Implementation plan body.",
                labels=["vk-ready"],
            )
            assert url == "https://github.com/org/repo/issues/42"
            mock.assert_called_once_with(
                [
                    "issue",
                    "create",
                    "--repo",
                    "org/repo",
                    "--title",
                    "Phase 1: Setup",
                    "--body",
                    "Implementation plan body.",
                    "--label",
                    "vk-ready",
                ]
            )

    def test_multiple_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/43") as mock:
            create_issue(
                repo="org/repo",
                title="Task",
                body="Body.",
                labels=["vk-ready", "manual"],
            )
            args = mock.call_args[0][0]
            assert args.count("--label") == 2

    def test_no_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="url") as mock:
            create_issue(repo="org/repo", title="T", body="B", labels=[])
            args = mock.call_args[0][0]
            assert "--label" not in args


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            close_issue(repo="org/repo", number=42)
            mock.assert_called_once_with(
                [
                    "issue",
                    "close",
                    "--repo",
                    "org/repo",
                    "42",
                ]
            )


class TestAddToProject:
    def test_add(self) -> None:
        with patch("vk.gh._run_gh", return_value="item-id-123") as mock:
            item_id = add_to_project(
                url="https://github.com/org/repo/issues/42",
                project_owner="org",
                project_number=5,
            )
            assert item_id == "item-id-123"
            mock.assert_called_once_with(
                [
                    "project",
                    "item-add",
                    "5",
                    "--owner",
                    "org",
                    "--url",
                    "https://github.com/org/repo/issues/42",
                    "--format",
                    "json",
                ]
            )


class TestSetField:
    def test_set_text_field(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            set_field(
                project_owner="org",
                project_number=5,
                item_id="item-123",
                field_name="Status",
                field_value="In Progress",
            )
            mock.assert_called_once_with(
                [
                    "project",
                    "item-edit",
                    "--owner",
                    "org",
                    "--project-id",
                    "5",
                    "--id",
                    "item-123",
                    "--field-name",
                    "Status",
                    "--field-value",
                    "In Progress",
                ]
            )


class TestAuthStatus:
    def test_authenticated(self) -> None:
        with patch("vk.gh._run_gh", return_value="github.com\n  Logged in") as mock:
            result = auth_status()
            assert result is True
            mock.assert_called_once_with(["auth", "status"])

    def test_not_authenticated(self) -> None:
        with patch(
            "vk.gh._run_gh",
            side_effect=GhError("not logged in"),
        ):
            result = auth_status()
            assert result is False


class TestRunGhError:
    def test_subprocess_error_raises_gh_error(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "gh", stderr="fail"),
        ):
            with pytest.raises(GhError):
                create_issue(repo="org/repo", title="T", body="B", labels=[])
