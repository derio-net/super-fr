"""CLI integration tests for vk dispatch."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestDispatchDryRun:
    def test_dry_run_shows_preview(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--dry-run"])
        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower()
        assert "Phase 0" in result.stdout
        assert "Phase 1" in result.stdout
        assert "Phase 2" in result.stdout
        assert "test-feature" in result.stdout


class TestDispatchGateRefusal:
    def test_no_config_file(self, tmp_repo: Path, phased_plan: Path) -> None:
        # Remove config if it exists
        config = tmp_repo / "docs" / "superpowers" / "plan-config.yaml"
        config.unlink(missing_ok=True)
        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--dry-run"])
        assert result.exit_code == 1

    def test_dispatch_false(self, tmp_repo: Path, phased_plan: Path) -> None:
        config_dir = tmp_repo / "docs" / "superpowers"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "plan-config.yaml"
        config_file.write_text("dispatch: false\n")
        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--dry-run"])
        assert result.exit_code == 1

    def test_flat_plan_refused(self, dispatch_config: Path, tmp_repo: Path) -> None:
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        flat_plan = plans_dir / "2026-04-12-flat-thing.md"
        flat_plan.write_text(
            textwrap.dedent("""\
            # Flat Plan

            **Spec:** `specs/flat.md`
            **Status:** Not Started

            **Goal:** Do flat things.

            ---

            ### Task 1: Do something [agentic]

            - [ ] **Step 1: Thing**
        """)
        )
        result = runner.invoke(app, ["dispatch", "create", str(flat_plan), "--dry-run"])
        assert result.exit_code == 2
        assert "flat" in result.stdout.lower() or "flat" in (result.stderr or "").lower()


class TestDispatchIdempotency:
    def test_all_tracked_exits_zero(self, dispatch_config: Path, tmp_repo: Path) -> None:
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "2026-04-12-all-tracked.md"
        plan_file.write_text(
            textwrap.dedent("""\
            # All Tracked Plan

            **Spec:** `specs/tracked.md`
            **Status:** In Progress

            **Goal:** Fully dispatched.

            ---

            ## Phase 0: Done [agentic]
            <!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->

            ### Task 1: Done

            - [x] **Step 1: Done**
        """)
        )
        result = runner.invoke(app, ["dispatch", "create", str(plan_file), "--dry-run"])
        assert result.exit_code == 0
        assert "already dispatched" in result.stdout.lower() or "noop" in result.stdout.lower()


class TestDispatchMutualExclusion:
    def test_both_flags_error(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--dry-run", "--yes"])
        assert result.exit_code != 0


class TestDispatchApply:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_apply_creates_issues_and_injects_tracking(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        issue_urls = [
            "https://github.com/derio-net/test-repo/issues/100",
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
        ]
        mock_gh.create_issue.side_effect = issue_urls
        mock_gh.extract_issue_number.side_effect = [100, 101, 102]
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0

        assert mock_gh.create_issue.call_count == 3

        # Verify structured body format for each created issue
        for call_obj in mock_gh.create_issue.call_args_list:
            body = call_obj[1]["body"] if "body" in call_obj[1] else call_obj[0][2]
            assert "## Instruction" in body
            assert "superpowers-for-vk:vk-execute" in body
            assert "## Workspace" in body
            assert "Repos: derio-net/test-repo" in body
            assert "## Dependencies" in body
            # Tracking block fields
            assert "📦 Repo:   derio-net/test-repo" in body
            assert "📋 Plan:" in body
            assert "🎯 Phase:" in body
            assert "🔗 Issue:  (assigned on create)" in body
            assert "**Goal (from plan):**" in body

        # Phase 0 (first) should have no blocking issue
        first_body = mock_gh.create_issue.call_args_list[0][1]["body"]
        assert "Blocked by" not in first_body

        # Phase 1 should reference phase 0's issue number
        second_body = mock_gh.create_issue.call_args_list[1][1]["body"]
        assert "- Blocked by #100" in second_body

        # Phase 2 should reference phase 1's issue number
        third_body = mock_gh.create_issue.call_args_list[2][1]["body"]
        assert "- Blocked by #101" in third_body

        updated = phased_plan.read_text()
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/100 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/101 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/102 -->" in updated


class TestDispatchLabels:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_dispatch_adds_plan_and_phase_labels(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """Each created Issue must carry plan:<slug> and phase:<n> labels."""
        captured_labels: list[list[str]] = []

        def fake_create_issue(*, repo: str, title: str, body: str, labels: list[str]) -> str:
            captured_labels.append(list(labels))
            return "https://github.com/org/repo/issues/100"

        mock_gh.create_issue.side_effect = fake_create_issue
        mock_gh.extract_issue_number.return_value = 100
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0

        for i, labs in enumerate(captured_labels):
            assert "plan:test-feature" in labs, f"Missing plan:test-feature in {labs}"
            assert f"phase:{i}" in labs, f"Missing phase:{i} in {labs}"
            assert labs[0] in ("vk-ready", "manual"), f"First label should be tag label: {labs}"


class TestDispatchGitCommit:
    @patch("vk.commands.dispatch_cmd.gh")
    @patch("vk.commands.dispatch_cmd.subprocess")
    def test_git_commit_failure_surfaces(
        self,
        mock_subprocess: MagicMock,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """A failing git commit must surface, not be silently swallowed."""
        import subprocess as real_subprocess

        mock_gh.create_issue.return_value = "https://github.com/org/repo/issues/1"
        mock_gh.extract_issue_number.return_value = 1
        mock_gh.GhError = type("GhError", (Exception,), {})

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            if cmd and cmd[0] == "git" and "commit" in cmd:
                raise real_subprocess.CalledProcessError(
                    1, cmd, stderr="pre-commit hook failed"
                )
            result = MagicMock()
            result.stdout = str(tmp_repo)
            result.returncode = 0
            return result

        mock_subprocess.run.side_effect = fake_run
        mock_subprocess.CalledProcessError = real_subprocess.CalledProcessError

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code != 0


class TestDispatchIssueUrlInjection:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_dispatch_updates_body_with_issue_url(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """After Issue creation, the body's '🔗 Issue:' line gets the real URL."""
        edits: list[tuple[str, str]] = []

        def fake_create(*, repo: str, title: str, body: str, labels: list[str]) -> str:
            assert "(assigned on create)" in body
            return "https://github.com/org/repo/issues/77"

        def fake_edit_body(repo: str, number: int, body: str) -> None:
            edits.append((repo, body))

        mock_gh.create_issue.side_effect = fake_create
        mock_gh.extract_issue_number.return_value = 77
        mock_gh.edit_issue_body.side_effect = fake_edit_body
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0
        assert len(edits) == 3, f"expected one edit per phase, got {len(edits)}"
        for _, body in edits:
            assert "🔗 Issue:  https://github.com/org/repo/issues/77" in body
            assert "(assigned on create)" not in body
