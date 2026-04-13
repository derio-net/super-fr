"""Tests for dispatch-mode audit in vk progress."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vk.commands.progress_cmd import (
    _extract_tracking_urls,
    _parse_issue_url,
    _run_dispatch_audit,
)
from vk.config import DispatchConfig, HeaderConfig, PlanConfig, Profile
from vk.gh import BoardItem


class TestExtractTrackingUrls:
    def test_extracts_urls(self, tmp_path: Path):
        plan = tmp_path / "plan.md"
        plan.write_text(
            "## Phase 0\n"
            "<!-- Tracking: https://github.com/org/repo/issues/1 -->\n"
            "Some content\n"
            "## Phase 1\n"
            "<!-- Tracking: https://github.com/org/repo/issues/2 -->\n"
        )
        urls = _extract_tracking_urls(plan)
        assert urls == [
            "https://github.com/org/repo/issues/1",
            "https://github.com/org/repo/issues/2",
        ]

    def test_no_tracking(self, tmp_path: Path):
        plan = tmp_path / "plan.md"
        plan.write_text("## Phase 0\nNo tracking here\n")
        assert _extract_tracking_urls(plan) == []


class TestParseIssueUrl:
    def test_valid_url(self):
        repo, num = _parse_issue_url("https://github.com/derio-net/willikins/issues/14")
        assert repo == "derio-net/willikins"
        assert num == 14

    def test_invalid_url(self):
        repo, num = _parse_issue_url("not-a-url")
        assert repo == ""
        assert num == 0


class TestRunDispatchAudit:
    @pytest.fixture
    def dispatch_profile(self) -> Profile:
        return Profile(
            plan=PlanConfig(),
            header=HeaderConfig(),
            dispatch=DispatchConfig(
                owner="test-org",
                project_board="Test Board",
                default_repo="test-org/test-repo",
            ),
        )

    @pytest.fixture
    def plans_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "docs" / "superpowers" / "plans"
        d.mkdir(parents=True)
        return d

    def test_flags_missing_lifecycle(self, dispatch_profile: Profile, plans_dir: Path):
        items = [
            BoardItem(
                title="Some item",
                url="https://github.com/test-org/repo/issues/1",
                repo="test-org/repo",
                number=1,
                closed=False,
                lifecycle="unset",
                status="Todo",
                labels=[],
            ),
        ]
        with (
            patch("vk.gh.get_project_number", return_value=1),
            patch("vk.gh.list_project_items", return_value=items),
        ):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert any("Missing lifecycle" in i for i in issues)

    def test_flags_deployed_closed_phases(
        self, dispatch_profile: Profile, plans_dir: Path
    ):
        items = [
            BoardItem(
                title="my-plan-0-agentic",
                url="https://github.com/test-org/repo/issues/10",
                repo="test-org/repo",
                number=10,
                closed=False,
                lifecycle="deployed",
                status="Done",
                labels=[],
            ),
        ]
        with (
            patch("vk.gh.get_project_number", return_value=1),
            patch("vk.gh.list_project_items", return_value=items),
            patch("vk.gh.is_issue_closed", return_value=True),
        ):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert any("should be 'retired'" in i for i in issues)

    def test_flags_tracked_issue_not_on_board(
        self, dispatch_profile: Profile, plans_dir: Path
    ):
        plan = plans_dir / "2026-01-01-test.md"
        plan.write_text(
            "# Test Plan\n"
            "**Spec:** `none`\n"
            "**Status:** In Progress\n"
            "## Phase 0\n"
            "<!-- Tracking: https://github.com/test-org/repo/issues/99 -->\n"
        )
        with (
            patch("vk.gh.get_project_number", return_value=1),
            patch("vk.gh.list_project_items", return_value=[]),
        ):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert any("not on board" in i and "issues/99" in i for i in issues)

    def test_no_issues_when_clean(
        self, dispatch_profile: Profile, plans_dir: Path
    ):
        items = [
            BoardItem(
                title="healthy-service",
                url="https://github.com/test-org/repo/issues/1",
                repo="test-org/repo",
                number=1,
                closed=False,
                lifecycle="healthy",
                status="Done",
                labels=[],
            ),
        ]
        with (
            patch("vk.gh.get_project_number", return_value=1),
            patch("vk.gh.list_project_items", return_value=items),
        ):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert issues == []

    def test_handles_board_query_failure(
        self, dispatch_profile: Profile, plans_dir: Path
    ):
        from vk.gh import GhError

        with patch("vk.gh.get_project_number", side_effect=GhError("auth failed")):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert len(issues) == 1
        assert "Board query failed" in issues[0]

    def test_flags_cross_repo_duplicates(
        self, dispatch_profile: Profile, plans_dir: Path
    ):
        items = [
            BoardItem(
                title="Content pipeline foundation",
                url="https://github.com/test-org/repo-a/issues/1",
                repo="test-org/repo-a",
                number=1,
                closed=False,
                lifecycle="plan",
                status="Todo",
                labels=[],
            ),
            BoardItem(
                title="Content pipeline foundation",
                url="https://github.com/test-org/repo-b/issues/2",
                repo="test-org/repo-b",
                number=2,
                closed=False,
                lifecycle="plan",
                status="Todo",
                labels=[],
            ),
        ]
        with (
            patch("vk.gh.get_project_number", return_value=1),
            patch("vk.gh.list_project_items", return_value=items),
        ):
            issues = _run_dispatch_audit(dispatch_profile, plans_dir)

        assert any("Possible duplicate" in i for i in issues)
