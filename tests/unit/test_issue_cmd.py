"""Tests for vk issue create subcommand."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vk.cli import app
from vk.commands.issue_cmd import _build_issue_body, _resolve_repo

runner = CliRunner()


class TestBuildIssueBody:
    def test_contains_all_required_sections(self) -> None:
        body = _build_issue_body(
            topic="Investigate the foo bug",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "## Instruction" in body
        assert "## Workspace" in body
        assert "## Dependencies" in body

    def test_topic_appears_in_body(self) -> None:
        body = _build_issue_body(
            topic="Investigate the foo bug",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "Investigate the foo bug" in body

    def test_skill_appears_in_instruction(self) -> None:
        body = _build_issue_body(
            topic="Topic",
            skill="superpowers:systematic-debugging",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "superpowers:systematic-debugging" in body

    def test_repos_appear_in_workspace(self) -> None:
        body = _build_issue_body(
            topic="Topic",
            skill="superpowers:brainstorming",
            repos="derio-net/frank",
            blockers="None — no blocking phases.",
        )
        assert "derio-net/frank" in body

    def test_body_validates_against_bridge_contract(self) -> None:
        from vk.commands.dispatch_body_validator import validate_issue_body

        body = _build_issue_body(
            topic="Some topic",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        # Should not raise
        validate_issue_body(body, phase_number=0)

    def test_body_validates_with_blocker_lines(self) -> None:
        from vk.commands.dispatch_body_validator import validate_issue_body

        body = _build_issue_body(
            topic="Some topic",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="- Blocked by #42\n- Blocked by #43",
        )
        validate_issue_body(body, phase_number=0)


class TestCreateDryRun:
    def test_dry_run_prints_title_and_body(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "issue",
                "create",
                "Investigate the foo regression",
                "--dry-run",
                "--repo",
                "derio-net/superpowers-for-vk",
            ],
        )
        assert result.exit_code == 0
        assert "Investigate the foo regression" in result.output
        assert "## Instruction" in result.output

    def test_dry_run_does_not_call_gh(self) -> None:
        with patch("subprocess.run") as mock_run:
            result = runner.invoke(
                app,
                [
                    "issue",
                    "create",
                    "Topic",
                    "--dry-run",
                    "--repo",
                    "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        mock_run.assert_not_called()

    def test_stdin_topic(self) -> None:
        result = runner.invoke(
            app,
            ["issue", "create", "-", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            input="Topic from stdin\n",
        )
        assert result.exit_code == 0
        assert "Topic from stdin" in result.output

    def test_custom_skill(self) -> None:
        result = runner.invoke(
            app,
            [
                "issue",
                "create",
                "Topic",
                "--dry-run",
                "--skill",
                "superpowers:systematic-debugging",
                "--repo",
                "derio-net/superpowers-for-vk",
            ],
        )
        assert result.exit_code == 0
        assert "superpowers:systematic-debugging" in result.output
