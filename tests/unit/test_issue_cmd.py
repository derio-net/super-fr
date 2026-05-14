"""Tests for vk issue create subcommand."""

from __future__ import annotations

from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

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


class TestResolveRepo:
    def test_explicit_repo_returned_unchanged(self) -> None:
        assert _resolve_repo("derio-net/frank") == "derio-net/frank"

    def test_ssh_url_parsed(self) -> None:
        mock = MagicMock()
        mock.stdout = "git@github.com:derio-net/frank.git\n"
        with patch("subprocess.run", return_value=mock):
            assert _resolve_repo(None) == "derio-net/frank"

    def test_https_url_parsed(self) -> None:
        mock = MagicMock()
        mock.stdout = "https://github.com/derio-net/frank.git\n"
        with patch("subprocess.run", return_value=mock):
            assert _resolve_repo(None) == "derio-net/frank"

    def test_https_url_without_dotgit_suffix(self) -> None:
        mock = MagicMock()
        mock.stdout = "https://github.com/derio-net/frank\n"
        with patch("subprocess.run", return_value=mock):
            assert _resolve_repo(None) == "derio-net/frank"

    def test_git_failure_raises_exit(self) -> None:
        import click

        with patch("subprocess.run", side_effect=CalledProcessError(128, "git")):
            with pytest.raises(click.exceptions.Exit):
                _resolve_repo(None)


class TestCreateDryRun:
    def test_dry_run_prints_title_and_body(self) -> None:
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
