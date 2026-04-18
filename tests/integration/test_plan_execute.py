"""Integration tests for vk plan and vk execute subcommands."""

from __future__ import annotations

import subprocess
import textwrap
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


@pytest.fixture()
def local_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Local-only repo with a flat plan."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "T"],
        check=True,
        capture_output=True,
    )

    config_dir = tmp_path / "docs" / "superpowers"
    config_dir.mkdir(parents=True)
    (config_dir / "plan-config.yaml").write_text(
        textwrap.dedent("""\
        plan:
          filename: "YYYY-MM-DD-{name}.md"
          save_to: docs/superpowers/plans/
        header:
          required: [Spec, Status]
          status_values: [Not Started, In Progress, Complete]
    """)
    )

    plans_dir = config_dir / "plans"
    plans_dir.mkdir()
    (plans_dir / "2026-04-12-test-plan.md").write_text(
        textwrap.dedent("""\
        # Test Plan

        **Spec:** `docs/superpowers/specs/test-spec.md`
        **Status:** Not Started

        **Goal:** Test plan commands.

        ---

        ### Task 1: First [agentic]

        - [x] **Step 1: Done step**

        Body of done step.

        - [ ] **Step 2: Pending step**

        Body of pending step.

        ### Task 2: Second [manual]

        - [ ] **Step 1: Another step**

        Body here.
    """)
    )

    specs_dir = config_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "test-spec.md").write_text(
        "# Test Spec\n\n## Summary\n\nA test spec.\n\n## Design\n\nDesign here.\n"
    )

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    yield tmp_path


class TestPlanFormat:
    def test_format_flat(self, local_repo: Path) -> None:
        result = runner.invoke(app, ["plan", "format", str(local_repo)])
        assert result.exit_code == 0
        assert "flat" in result.stdout


class TestPlanSelfReview:
    def test_self_review_passes(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code == 0
        assert "passed" in result.stdout.lower()


class TestPlanConvert:
    def test_convert_flat_to_phased_single(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(
            app,
            ["plan", "convert", str(plan), "--to", "phased", "--single-phase", "--yes"],
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "## Phase 1:" in content

    def test_convert_dry_run(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        before = plan.read_text()
        result = runner.invoke(
            app,
            ["plan", "convert", str(plan), "--to", "phased", "--single-phase", "--dry-run"],
        )
        assert result.exit_code == 0
        assert plan.read_text() == before
        assert "Would convert" in result.stdout


class TestPlanSpecIndex:
    def test_spec_index_dry_run(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["plan", "spec-index", str(plan), "--dry-run"])
        assert result.exit_code == 0
        assert "Would update" in result.stdout

    def test_spec_index_apply(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        spec = local_repo / "docs/superpowers/specs/test-spec.md"
        result = runner.invoke(app, ["plan", "spec-index", str(plan), "--yes"])
        assert result.exit_code == 0
        assert "Implementation Plans" in spec.read_text()


class TestExecuteCheckDeps:
    def test_deps_satisfied(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        # Task 1 has a checked step, checking deps for Task 2 should pass
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        # Task 1 still has one unchecked step, so deps should fail
        assert result.exit_code == 1

    def test_deps_first_task_always_clear(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "1"])
        assert result.exit_code == 0


class TestExecuteScope:
    def test_scope_prints_task(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "scope", str(plan), "1"])
        assert result.exit_code == 0
        assert "Task 1" in result.stdout
        assert "Step 1" in result.stdout


class TestExecuteCheckStep:
    def test_check_step_marks_done(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "check-step", str(plan), "T1.S2"])
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [x] **Step 2: Pending step**" in content

    def test_check_step_idempotent(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        # Step 1 is already checked
        result = runner.invoke(app, ["execute", "check-step", str(plan), "T1.S1"])
        assert result.exit_code == 0
        assert "already" in result.stdout.lower()

    def test_check_step_skip_requires_note(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "check-step", str(plan), "T1.S2", "--state", "-"])
        assert result.exit_code == 2
        assert "note" in result.stdout.lower() or "note" in (result.stderr or "").lower()


class TestExecutePrBody:
    def test_pr_body_local(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        assert "Task 1" in result.stdout

    def test_pr_body_with_issue(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1", "--issue", "42"])
        assert result.exit_code == 0
        assert "Closes #42" in result.stdout

    def test_pr_body_auto_discovers_issue_from_tracking_comment(self, tmp_path: Path) -> None:
        """Phased plan with a tracking comment should emit Closes #N without --issue."""
        fixtures = Path(__file__).parent.parent / "fixtures" / "plans"
        src = fixtures / "phased-dispatched.md"
        plan = tmp_path / "phased-dispatched.md"
        plan.write_text(src.read_text())

        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        # phased-dispatched.md Phase 1 tracking URL is .../issues/42
        assert "Closes #42" in result.stdout

    def test_pr_body_explicit_issue_overrides_tracking(self, tmp_path: Path) -> None:
        """--issue should override the auto-discovered tracking comment."""
        fixtures = Path(__file__).parent.parent / "fixtures" / "plans"
        src = fixtures / "phased-dispatched.md"
        plan = tmp_path / "phased-dispatched.md"
        plan.write_text(src.read_text())

        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1", "--issue", "99"])
        assert result.exit_code == 0
        assert "Closes #99" in result.stdout
        assert "Closes #42" not in result.stdout
