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
        assert "Phase 1" in result.stdout
        assert "Phase 2" in result.stdout
        assert "Phase 3" in result.stdout
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

            ## Phase 1: Done [agentic]
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

        # Phase 1 (first) should have no blocking issue
        first_body = mock_gh.create_issue.call_args_list[0][1]["body"]
        assert "Blocked by" not in first_body

        # Phase 2 should reference phase 1's issue number
        second_body = mock_gh.create_issue.call_args_list[1][1]["body"]
        assert "Blocked by #100" in second_body

        # Phase 3 should reference phase 2's issue number
        third_body = mock_gh.create_issue.call_args_list[2][1]["body"]
        assert "Blocked by #101" in third_body

        updated = phased_plan.read_text()
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/100 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/101 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/102 -->" in updated
