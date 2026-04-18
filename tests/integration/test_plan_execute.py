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


@pytest.fixture()
def phased_repo(local_repo: Path) -> Path:
    """``local_repo`` with the flat plan migrated to phased.

    Execute sub-commands refuse flat plans (must migrate first), so any test
    exercising ``vk execute *`` uses this fixture instead of ``local_repo``.
    """
    plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
    result = runner.invoke(
        app, ["plan", "convert", str(plan), "--to", "phased", "--single-phase", "--yes"]
    )
    assert result.exit_code == 0, result.stdout
    return local_repo


class TestPlanFormat:
    def test_format_directory_uses_config(self, local_repo: Path) -> None:
        # No dispatch block in config -> profile format defaults to flat.
        result = runner.invoke(app, ["plan", "format", str(local_repo)])
        assert result.exit_code == 0
        assert "flat" in result.stdout

    def test_format_file_parses_plan_shape_flat(self, local_repo: Path) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["plan", "format", str(plan)])
        assert result.exit_code == 0
        assert result.stdout.strip() == "flat"

    def test_format_file_parses_plan_shape_phased(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["plan", "format", str(plan)])
        assert result.exit_code == 0
        assert result.stdout.strip() == "phased"

    def test_format_missing_path_errors(self, tmp_path: Path) -> None:
        """Nonexistent paths must not silently fall through to the flat default."""
        ghost = tmp_path / "does-not-exist"
        result = runner.invoke(app, ["plan", "format", str(ghost)])
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "does not exist" in combined

    def test_format_non_plan_file_errors(self, tmp_path: Path) -> None:
        """A file that isn't a valid plan must error, not traceback."""
        junk = tmp_path / "not-a-plan.md"
        junk.write_text("# Just a random markdown doc\n\nNo phases or tasks here.\n")
        result = runner.invoke(app, ["plan", "format", str(junk)])
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "could not parse" in combined.lower()


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


class TestExecuteRejectsFlat:
    """All execute sub-commands must refuse flat plans with a migration hint."""

    @pytest.mark.parametrize(
        "args",
        [
            ("check-deps", "1"),
            ("scope", "1"),
            ("check-step", "P1.T1.S1"),
            ("pr-body", "1"),
        ],
        ids=["check-deps", "scope", "check-step", "pr-body"],
    )
    def test_flat_plan_rejected(self, local_repo: Path, args: tuple[str, str]) -> None:
        plan = local_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        cmd = ["execute", args[0], str(plan), args[1]]
        result = runner.invoke(app, cmd)
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "flat" in combined.lower()
        assert "vk plan convert" in combined

    @pytest.mark.parametrize(
        "args",
        [
            ("check-deps", "1"),
            ("scope", "1"),
            ("check-step", "P1.T1.S1"),
            ("pr-body", "1"),
        ],
        ids=["check-deps", "scope", "check-step", "pr-body"],
    )
    def test_non_plan_file_errors_cleanly(self, tmp_path: Path, args: tuple[str, str]) -> None:
        """The _reject_flat guard must catch parse errors rather than traceback."""
        junk = tmp_path / "not-a-plan.md"
        junk.write_text("# Not a plan\n\nJust some markdown.\n")
        cmd = ["execute", args[0], str(junk), args[1]]
        result = runner.invoke(app, cmd)
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "could not parse" in combined.lower()


class TestExecuteCheckDeps:
    def test_deps_satisfied(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        # Plan has a single phase after migration; a second phase doesn't exist,
        # but check-deps walks earlier phases looking for unchecked steps. Phase 1
        # has one unchecked step (Task 1 Step 2), so deps for any later phase fail.
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        assert result.exit_code == 1

    def test_deps_first_phase_always_clear(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "1"])
        assert result.exit_code == 0


class TestExecuteScope:
    def test_scope_prints_phase(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "scope", str(plan), "1"])
        assert result.exit_code == 0
        assert "Phase 1" in result.stdout
        assert "Task 1" in result.stdout
        assert "Step 1" in result.stdout


class TestExecuteCheckStep:
    def test_check_step_marks_done(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "check-step", str(plan), "P1.T1.S2"])
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [x] **Step 2: Pending step**" in content

    def test_check_step_idempotent(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        # Step 1 is already checked
        result = runner.invoke(app, ["execute", "check-step", str(plan), "P1.T1.S1"])
        assert result.exit_code == 0
        assert "already" in result.stdout.lower()

    def test_check_step_skip_requires_note(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S2", "--state", "-"]
        )
        assert result.exit_code == 2
        assert "note" in result.stdout.lower() or "note" in (result.stderr or "").lower()

    def test_check_step_phased_scopes_to_phase_and_task(self, tmp_path: Path) -> None:
        """Phased step IDs must scope to the target phase/task — not match any
        step with the same number elsewhere. Regression for a bug where the
        matcher ignored phase_num and task_num and matched on step_num alone."""
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
        plans_dir = tmp_path / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "phased.md"
        plan.write_text(
            textwrap.dedent("""\
            # Phased Test Plan

            **Spec:** `docs/superpowers/specs/x.md`
            **Status:** In Progress

            ---

            ## Phase 1: First phase [agentic]

            ### Task 1: Alpha

            - [x] **Step 1: P1.T1.S1 already done**

            Body.

            ### Task 2: Beta

            - [ ] **Step 1: P1.T2.S1 target — flip me**

            Body.

            ## Phase 2: Second phase [agentic]

            ### Task 1: Gamma

            - [ ] **Step 1: P2.T1.S1 sibling — must stay unchecked**

            Body.
            """)
        )
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["execute", "check-step", str(plan), "P1.T2.S1"])
        assert result.exit_code == 0, result.stdout
        content = plan.read_text()
        assert "- [x] **Step 1: P1.T2.S1 target — flip me**" in content
        assert "- [x] **Step 1: P1.T1.S1 already done**" in content
        assert "- [ ] **Step 1: P2.T1.S1 sibling — must stay unchecked**" in content


class TestExecutePrBody:
    def test_pr_body_local(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        assert "Phase 1" in result.stdout

    def test_pr_body_with_issue(self, phased_repo: Path) -> None:
        plan = phased_repo / "docs/superpowers/plans/2026-04-12-test-plan.md"
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
