"""Tests for local audit helpers in vk progress."""

from __future__ import annotations

from pathlib import Path

from vk.commands.progress_cmd import (
    _extract_tracking_urls,
    _parse_issue_url,
)


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
