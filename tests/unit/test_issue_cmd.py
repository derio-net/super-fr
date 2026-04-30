"""Tests for vk issue create and convert subcommands."""

from __future__ import annotations

import json
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

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
    def test_explicit_repo_returned_as_is(self) -> None:
        assert _resolve_repo("derio-net/frank") == "derio-net/frank"

    def test_ssh_remote_parsed_correctly(self) -> None:
        fake = CompletedProcess(args=[], returncode=0, stdout="git@github.com:owner/repo.git\n")
        with patch("subprocess.run", return_value=fake):
            assert _resolve_repo(None) == "owner/repo"

    def test_https_remote_parsed_correctly(self) -> None:
        fake = CompletedProcess(args=[], returncode=0, stdout="https://github.com/owner/repo.git\n")
        with patch("subprocess.run", return_value=fake):
            assert _resolve_repo(None) == "owner/repo"

    def test_https_remote_without_dotgit(self) -> None:
        fake = CompletedProcess(args=[], returncode=0, stdout="https://github.com/owner/repo\n")
        with patch("subprocess.run", return_value=fake):
            assert _resolve_repo(None) == "owner/repo"

    def test_git_failure_exits_with_code_2(self) -> None:
        import subprocess

        import typer

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")):
            try:
                _resolve_repo(None)
                assert False, "should have raised"
            except typer.Exit as exc:
                assert exc.exit_code == 2


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


class TestConvertDryRun:
    def test_dry_run_appends_contract_to_plain_body(self) -> None:
        plain_body = "This is a plain bug report without contract sections."
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps({"body": plain_body})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                [
                    "issue",
                    "convert",
                    "42",
                    "--dry-run",
                    "--repo",
                    "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        assert "## Instruction" in result.output
        assert "## Workspace" in result.output
        assert "## Dependencies" in result.output
        assert plain_body in result.output

    def test_dry_run_noop_when_already_has_sections(self) -> None:
        body_with_contract = (
            "Topic\n\n---\n\n## Instruction\n\nUse skill.\n\n"
            "## Workspace\n\nRepos: org/repo\n\n## Dependencies\n\nNone — no blocking phases.\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps({"body": body_with_contract})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                [
                    "issue",
                    "convert",
                    "42",
                    "--dry-run",
                    "--repo",
                    "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        assert "already has contract sections" in result.output

    def test_convert_does_not_mutate_in_dry_run(self) -> None:
        plain_body = "Plain bug report."
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps({"body": plain_body})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                ["issue", "convert", "42", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            )
        assert result.exit_code == 0
        # The only subprocess call is `gh issue view`. Asserting on the call args
        # (rather than just the count) means a future change to _resolve_repo
        # that adds a git subprocess call won't silently flip this test's meaning.
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:3] == ["gh", "issue", "view"]


class TestConvertFailurePaths:
    def test_gh_issue_view_failure_exits_2(self) -> None:
        """If `gh issue view` fails, we should print an error and exit 2 — not crash."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["gh", "issue", "view", "42"],
                stderr="Could not resolve to an Issue with the number of 42.",
            )
            result = runner.invoke(
                app,
                ["issue", "convert", "42", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            )
        assert result.exit_code == 2

    def test_gh_returns_non_json_exits_2(self) -> None:
        """Defensive: if `gh` ever returns non-JSON (HTML proxy page, empty stdout)
        we should exit 2 with a clean error rather than dump a JSONDecodeError stack."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "<html>403 Forbidden</html>"
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                ["issue", "convert", "42", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            )
        assert result.exit_code == 2

    def test_empty_existing_body_does_not_produce_blank_head(self) -> None:
        """Issues with empty bodies should get the contract block as-is — no
        leading `---` separator that would render as a blank-headed Issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps({"body": ""})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                ["issue", "convert", "42", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            )
        assert result.exit_code == 0
        # First line of the body section should be the Instruction header — no
        # stray '---' separator before it.
        body_section = result.output.split("Converted body for Issue #42:", 1)[-1].strip()
        assert body_section.startswith("## Instruction"), (
            f"Empty body should not get a leading separator; got: {body_section[:60]!r}"
        )
