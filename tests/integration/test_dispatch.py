"""CLI integration tests for vk dispatch."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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
            **Depends on:** —

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


class TestDispatchPlanPath:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_body_uses_relative_plan_path(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """The '📋 Plan:' line must be relative to the repo root, not an absolute path."""
        mock_gh.create_issue.side_effect = [
            "https://github.com/derio-net/test-repo/issues/100",
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
        ]
        mock_gh.extract_issue_number.side_effect = [100, 101, 102]
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0, result.output

        for call_obj in mock_gh.create_issue.call_args_list:
            body = call_obj[1]["body"]
            assert "📋 Plan:   docs/superpowers/plans/2026-04-12-test-feature.md" in body, (
                f"expected relative plan path in body; got:\n{body}"
            )
            assert str(tmp_repo) not in body, "absolute tmp_repo path should not leak into body"


class TestDispatchLabels:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_dispatch_adds_three_tier_labels(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """Each created Issue must carry the three-tier identifier hierarchy:
        spec:<spec-slug>, plan:<plan-name>, and phase:<n>."""
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
            assert "spec:test-feature" in labs, f"Missing spec:test-feature in {labs}"
            assert "plan:test-feature" in labs, f"Missing plan:test-feature in {labs}"
            assert f"phase:{i}" in labs, f"Missing phase:{i} in {labs}"
            assert labs[0] in ("vk-ready", "manual"), f"First label should be tag label: {labs}"

    @patch("vk.commands.dispatch_cmd.gh")
    def test_dispatch_emits_distinct_spec_and_plan_labels(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan_distinct_names: Path,
        tmp_repo: Path,
    ) -> None:
        """When spec slug and plan name differ, both must appear distinctly.
        Guards against a derivation bug where one collapses into the other."""
        captured_labels: list[list[str]] = []

        def fake_create_issue(*, repo: str, title: str, body: str, labels: list[str]) -> str:
            captured_labels.append(list(labels))
            return "https://github.com/org/repo/issues/100"

        mock_gh.create_issue.side_effect = fake_create_issue
        mock_gh.extract_issue_number.return_value = 100
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(
            app, ["dispatch", "create", str(phased_plan_distinct_names), "--yes"]
        )
        assert result.exit_code == 0
        for labs in captured_labels:
            assert "spec:myspec" in labs, f"Missing spec:myspec in {labs}"
            assert "plan:extras" in labs, f"Missing plan:extras in {labs}"
            # No legacy full-slug emission when spec is set:
            assert "plan:myspec-phase-2-extras" not in labs

    @patch("vk.commands.dispatch_cmd.gh")
    def test_spec_less_plan_falls_back_to_legacy_label(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan_no_spec: Path,
        tmp_repo: Path,
    ) -> None:
        """Plans without a `**Spec:**` field must keep the legacy
        `plan:<full-slug>` single-label scheme. No `spec:` label is emitted."""
        captured_labels: list[list[str]] = []

        def fake_create_issue(*, repo: str, title: str, body: str, labels: list[str]) -> str:
            captured_labels.append(list(labels))
            return "https://github.com/org/repo/issues/100"

        mock_gh.create_issue.side_effect = fake_create_issue
        mock_gh.extract_issue_number.return_value = 100
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan_no_spec), "--yes"])
        assert result.exit_code == 0
        for labs in captured_labels:
            assert "plan:spec-less-feature" in labs, f"Legacy plan:<full-slug> missing in {labs}"
            assert not any(lbl.startswith("spec:") for lbl in labs), (
                f"No spec: label expected for spec-less plans, got {labs}"
            )


class TestDispatchEnsuresLabels:
    """vk dispatch must ensure required labels exist on the target repo
    before creating Issues. Without this, `gh issue create --label X` fails
    hard on any repo that hasn't had the labels hand-created, which was the
    silent-partial-dispatch failure mode on content-factory and kid-laptops.
    """

    @patch("vk.commands.dispatch_cmd.gh")
    def test_dispatch_calls_ensure_labels_with_full_set(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        mock_gh.create_issue.side_effect = [
            "https://github.com/derio-net/test-repo/issues/100",
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
        ]
        mock_gh.extract_issue_number.side_effect = [100, 101, 102]
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0, result.output

        mock_gh.ensure_labels.assert_called_once()
        kwargs = mock_gh.ensure_labels.call_args.kwargs
        assert kwargs["repo"] == "derio-net/test-repo"
        labels = set(kwargs["labels"])
        # Full expected label set for a 3-phase plan (agentic, manual, agentic)
        assert "vk-ready" in labels
        assert "manual" in labels
        assert "plan:test-feature" in labels
        assert "phase:0" in labels
        assert "phase:1" in labels
        assert "phase:2" in labels

    @patch("vk.commands.dispatch_cmd.gh")
    def test_ensure_labels_called_before_any_create_issue(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """The label-bootstrap call must run before the first create_issue,
        so a missing label doesn't tear down a partial dispatch."""
        call_order: list[str] = []

        def _ensure(repo: str, labels: list[str]) -> None:
            call_order.append("ensure_labels")

        def _create(*, repo: str, title: str, body: str, labels: list[str]) -> str:
            call_order.append("create_issue")
            return "https://github.com/derio-net/test-repo/issues/100"

        mock_gh.ensure_labels.side_effect = _ensure
        mock_gh.create_issue.side_effect = _create
        mock_gh.extract_issue_number.return_value = 100
        mock_gh.GhError = type("GhError", (Exception,), {})

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0, result.output

        assert call_order[0] == "ensure_labels", call_order
        assert "create_issue" in call_order

    @patch("vk.commands.dispatch_cmd.gh")
    def test_ensure_labels_failure_aborts_before_any_issue(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """If label bootstrap fails hard, dispatch must abort WITHOUT
        creating any Issues. Partial state is the whole bug we're fixing."""
        mock_gh.GhError = type("GhError", (Exception,), {})
        mock_gh.ensure_labels.side_effect = mock_gh.GhError("permission denied")

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code != 0
        mock_gh.create_issue.assert_not_called()


class TestDispatchGitCommit:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_git_commit_failure_surfaces(
        self,
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

        original_run = real_subprocess.run

        def fake_run(cmd: list[str], **kwargs: object) -> real_subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[:2] == ["git", "commit"]:
                raise real_subprocess.CalledProcessError(1, cmd, stderr="pre-commit hook failed")
            return original_run(cmd, **kwargs)  # type: ignore[arg-type]

        with patch("subprocess.run", side_effect=fake_run):
            result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code != 0


class TestDispatchEditBodyBestEffort:
    @patch("vk.commands.dispatch_cmd.gh")
    def test_edit_failure_does_not_block_dispatch(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """edit_issue_body failure is cosmetic — dispatch must still succeed."""
        gh_error_cls = type("GhError", (Exception,), {})
        mock_gh.GhError = gh_error_cls
        mock_gh.create_issue.return_value = "https://github.com/org/repo/issues/50"
        mock_gh.extract_issue_number.return_value = 50
        mock_gh.edit_issue_body.side_effect = gh_error_cls("rate limited")

        result = runner.invoke(app, ["dispatch", "create", str(phased_plan), "--yes"])
        assert result.exit_code == 0, (
            f"dispatch should succeed despite edit failure: {result.output}"
        )

        # Verify issues were still created
        assert mock_gh.create_issue.call_count == 3

        # Tracking comments should still be injected into the plan file
        updated = phased_plan.read_text()
        assert "<!-- Tracking:" in updated


class TestDispatchFanIn:
    """Multi-blocker bodies round-trip via dispatch --yes."""

    @patch("vk.commands.dispatch_cmd.gh")
    def test_fan_in_body_contains_both_blockers(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        import shutil

        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-dag.md"
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-dag.md"
        shutil.copy(src, plan)

        urls = [
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
            "https://github.com/derio-net/test-repo/issues/103",
            "https://github.com/derio-net/test-repo/issues/104",
            "https://github.com/derio-net/test-repo/issues/105",
        ]
        mock_gh.create_issue.side_effect = urls
        mock_gh.extract_issue_number.side_effect = [101, 102, 103, 104, 105]
        mock_gh.edit_issue_body.return_value = None
        mock_gh.GhError = __import__("vk.gh", fromlist=["GhError"]).GhError

        result = runner.invoke(
            app,
            ["dispatch", "create", str(plan), "--yes"],
        )
        assert result.exit_code == 0, result.stdout

        # Phase 5 was the third create call that produced a multi-dep body.
        phase5_body = [c.kwargs["body"] for c in mock_gh.create_issue.call_args_list][4]
        assert "- Blocked by #103" in phase5_body
        assert "- Blocked by #104" in phase5_body
        # Phase 1 (root) should emit the None literal.
        phase1_body = [c.kwargs["body"] for c in mock_gh.create_issue.call_args_list][0]
        assert "None — no blocking phases." in phase1_body


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

        def fake_edit_body(*, repo: str, number: int, body: str) -> None:
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


class TestDispatchMigrateGuard:
    """migrate refuses legacy dispatched plans that lack **Depends on:** lines."""

    def test_migrate_refuses_pre_dag_plan(self, dispatch_config: Path, tmp_repo: Path) -> None:
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-predag.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** In Progress\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n"
            "<!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->\n\n"
            "### Task 1: T\n\n- [ ] **Step 1: s**\n\n"
            "## Phase 2: B [agentic]\n"
            "<!-- Tracking: https://github.com/derio-net/test-repo/issues/11 -->\n\n"
            "### Task 1: T\n\n- [ ] **Step 1: s**\n"
        )
        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--dry-run"])
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "**Depends on:**" in combined
        assert "vk plan convert" in combined
        assert "--add-deps" in combined

    def test_migrate_allows_post_dag_plan(
        self, dispatch_config: Path, tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plan WITH **Depends on:** lines proceeds past the guard.

        We stub gh.view_issue so the migrate loop reports closed+skip, which
        lets us assert the command reaches its natural terminus with exit 0
        instead of being caught by the new guard.
        """
        from vk import gh

        monkeypatch.setattr(gh, "view_issue", lambda repo, number: {"state": "CLOSED"})

        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-postdag.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** In Progress\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n"
            "<!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->\n"
            "**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1: s**\n"
        )
        result = runner.invoke(app, ["dispatch", "migrate", str(plan), "--yes"])
        assert result.exit_code == 0, result.stdout + (result.stderr or "")
