"""Integration tests for vk dispatch migrate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


def _write_plan(path: Path, phases_with_tracking: list[tuple[int, str, str | None]]) -> None:
    body = (
        "# P\n\n"
        "**Spec:** `docs/superpowers/specs/s.md`\n"
        "**Status:** In Progress\n\n"
        "**Goal:** G.\n\n---\n\n"
    )
    for n, title, url in phases_with_tracking:
        body += f"## Phase {n}: {title} [agentic]\n"
        if url:
            body += f"<!-- Tracking: {url} -->\n"
        body += "\n### Task 1: T\n\n- [ ] **Step 1: s**\n\n"
    path.write_text(body)


class TestMigrateAborts:
    def test_migrate_aborts_on_missing_tracking(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plan = tmp_repo / "docs" / "superpowers" / "plans" / "2026-04-14-test-migrate.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        _write_plan(
            plan,
            [
                (0, "A", "https://github.com/org/r/issues/1"),
                (1, "B", None),
            ],
        )
        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
        assert result.exit_code != 0
        assert "[1]" in result.output
        assert "no tracking comment" in result.output.lower()


class TestMigrateDryRun:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_migrate_dry_run_prints_diff(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plan = tmp_repo / "docs" / "superpowers" / "plans" / "2026-04-14-test-migrate.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        _write_plan(
            plan,
            [(0, "A", "https://github.com/org/r/issues/1")],
        )

        mock_gh.view_issue.return_value = {
            "state": "OPEN",
            "title": "old title",
            "body": "OLD BODY",
            "labels": [{"name": "vk-ready"}],
        }
        mock_gh.extract_issue_number.return_value = 1
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--dry-run"])
        assert result.exit_code == 0
        assert "old title" in result.output
        assert "test-migrate" in result.output


class TestMigrateApply:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_migrate_yes_applies_edits(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plan = tmp_repo / "docs" / "superpowers" / "plans" / "2026-04-14-test-migrate.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        _write_plan(
            plan,
            [(0, "A", "https://github.com/org/r/issues/1")],
        )

        mock_gh.view_issue.return_value = {
            "state": "OPEN",
            "title": "old",
            "body": "b",
            "labels": [],
        }
        mock_gh.extract_issue_number.return_value = 1
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
        assert result.exit_code == 0
        assert mock_gh.edit_issue.call_count == 1
        call_kwargs = mock_gh.edit_issue.call_args[1]
        assert "test-migrate" in call_kwargs["title"]
        assert "Migrated" in result.output

    @patch("vk.commands.dispatch_cmd.gh")
    def test_migrate_skips_closed_issues(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plan = tmp_repo / "docs" / "superpowers" / "plans" / "2026-04-14-test-migrate.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        _write_plan(
            plan,
            [(0, "A", "https://github.com/org/r/issues/1")],
        )

        mock_gh.view_issue.return_value = {
            "state": "CLOSED",
            "title": "old",
            "body": "b",
            "labels": [],
        }
        mock_gh.extract_issue_number.return_value = 1
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
        assert result.exit_code == 0
        assert mock_gh.edit_issue.call_count == 0
        assert "Skip #1: CLOSED" in result.output

    @patch("vk.commands.dispatch_cmd.gh")
    def test_migrate_aborts_on_gh_error(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plan = tmp_repo / "docs" / "superpowers" / "plans" / "2026-04-14-test-migrate.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        _write_plan(
            plan,
            [
                (0, "A", "https://github.com/org/r/issues/1"),
                (1, "B", "https://github.com/org/r/issues/2"),
            ],
        )

        mock_gh.view_issue.return_value = {
            "state": "OPEN",
            "title": "old",
            "body": "b",
            "labels": [],
        }
        mock_gh.extract_issue_number.side_effect = [1, 2, 1, 2]
        gh_error_cls = type("GhError", (Exception,), {})
        mock_gh.GhError = gh_error_cls
        mock_gh.edit_issue.side_effect = [None, gh_error_cls("gh boom")]

        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
        assert result.exit_code != 0
        assert "Migrated #1" in result.output
