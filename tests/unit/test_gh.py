"""Tests for vk.gh — subprocess wrappers for gh CLI operations.

These are contract tests: they verify the correct gh invocations
are constructed, using mocked subprocess calls.
"""

import subprocess
from unittest.mock import patch

import pytest

from vk.gh import (
    GhError,
    add_to_project,
    auth_status,
    close_issue,
    create_issue,
    edit_issue_body,
    ensure_label,
    ensure_labels,
    set_field,
)


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


class TestEditIssueBody:
    def test_edit_body_calls_gh(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            edit_issue_body(repo="org/repo", number=42, body="New body content.")
            mock.assert_called_once_with(
                ["issue", "edit", "42", "--repo", "org/repo", "--body", "New body content."]
            )

    def test_edit_body_propagates_gh_error(self) -> None:
        with patch("vk.gh._run_gh", side_effect=GhError("rate limited")):
            with pytest.raises(GhError, match="rate limited"):
                edit_issue_body(repo="org/repo", number=42, body="body")


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


class TestEnsureLabel:
    """`ensure_label` creates a label via `gh label create --force`, which
    is idempotent: creates if missing, updates color/description if present.
    Without this, `vk dispatch` fails hard on any repo that doesn't already
    have `vk-ready`, `manual`, `plan:<slug>`, `phase:<n>` — which was the
    silent-partial-dispatch failure mode on content-factory and kid-laptops.
    """

    def test_calls_gh_label_create_with_force(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(repo="org/repo", name="vk-ready")
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert args[:3] == ["label", "create", "vk-ready"]
            assert "--force" in args
            assert "--repo" in args
            assert "org/repo" in args
            assert "--color" in args  # a default color is always supplied

    def test_includes_description_when_given(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(
                repo="org/repo",
                name="vk-ready",
                description="Ready for VK pickup",
            )
            args = mock.call_args[0][0]
            assert "--description" in args
            assert "Ready for VK pickup" in args

    def test_omits_description_by_default(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(repo="org/repo", name="vk-ready")
            args = mock.call_args[0][0]
            assert "--description" not in args

    def test_propagates_gh_error(self) -> None:
        with patch("vk.gh._run_gh", side_effect=GhError("permission denied")):
            with pytest.raises(GhError, match="permission denied"):
                ensure_label(repo="org/repo", name="vk-ready")


class TestEnsureLabels:
    def test_calls_once_per_name(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_labels(repo="org/repo", labels=["a", "b", "c"])
            assert mock.call_count == 3
            names = [call[0][0][2] for call in mock.call_args_list]
            assert names == ["a", "b", "c"]

    def test_empty_list_is_noop(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_labels(repo="org/repo", labels=[])
            mock.assert_not_called()

    def test_error_aborts_remaining(self) -> None:
        """First failure surfaces — caller decides recovery. Don't
        silently swallow failures mid-batch (partial label state is
        worse than no labels at all)."""
        calls: list[str] = []

        def side_effect(args: list[str]) -> str:
            name = args[2]
            calls.append(name)
            if name == "b":
                raise GhError("fail on b")
            return ""

        with patch("vk.gh._run_gh", side_effect=side_effect):
            with pytest.raises(GhError, match="fail on b"):
                ensure_labels(repo="org/repo", labels=["a", "b", "c"])
        # Stopped at b — did not proceed to c
        assert calls == ["a", "b"]
