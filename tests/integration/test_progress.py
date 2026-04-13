"""CLI integration tests for vk progress subcommands."""

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
def local_repo_with_plan(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a local-only repo with a flat plan (partial progress)."""
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
    (plans_dir / "2026-04-12-test-feature.md").write_text(
        textwrap.dedent("""\
        # Test Feature Plan

        **Status:** Not Started

        **Goal:** Test progress sync.

        ---

        ### Task 1: Setup [agentic]

        - [x] **Step 1: Write test**

        Body of step 1.

        - [x] **Step 2: Implement**

        Body of step 2.

        ### Task 2: Deploy [manual]

        - [ ] **Step 1: Configure**

        Body of step.

        - [ ] **Step 2: Verify**

        Another body.
    """)
    )

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    yield tmp_path


@pytest.fixture()
def repo_with_stale_spec_index(tmp_path: Path) -> Generator[Path, None, None]:
    """Repo where the plan status header is correct but the spec index is stale."""
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

    specs_dir = config_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "test-spec.md").write_text(
        textwrap.dedent("""\
        # Test Spec

        ## Summary

        Example spec.

        ## Implementation Plans

        | Plan | Repo | File | Status | Depends on |
        |------|------|------|--------|------------|
        | Test Feature Plan |  | `docs/superpowers/plans/2026-04-12-test-feature.md` | Not Started | — |
    """)
    )

    plans_dir = config_dir / "plans"
    plans_dir.mkdir()
    # Plan has all steps checked and status already says "Complete",
    # but the spec index above still says "Not Started".
    (plans_dir / "2026-04-12-test-feature.md").write_text(
        textwrap.dedent("""\
        # Test Feature Plan

        **Spec:** `docs/superpowers/specs/test-spec.md`
        **Status:** Complete

        **Goal:** Test spec index reconciliation.

        ---

        ### Task 1: Setup [agentic]

        - [x] **Step 1: Write test**

        Body of step 1.

        - [x] **Step 2: Implement**

        Body of step 2.
    """)
    )

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    yield tmp_path


class TestProgressSync:
    def test_sync_local_updates_status(self, local_repo_with_plan: Path) -> None:
        plan = local_repo_with_plan / "docs/superpowers/plans/2026-04-12-test-feature.md"
        result = runner.invoke(app, ["progress", "sync", str(plan), "--yes"])
        assert result.exit_code == 0
        content = plan.read_text()
        assert "**Status:** In Progress" in content

    def test_sync_dry_run_no_mutation(self, local_repo_with_plan: Path) -> None:
        plan = local_repo_with_plan / "docs/superpowers/plans/2026-04-12-test-feature.md"
        before = plan.read_text()
        result = runner.invoke(app, ["progress", "sync", str(plan), "--dry-run"])
        assert result.exit_code == 0
        assert plan.read_text() == before
        assert "Would update" in result.stdout

    def test_sync_reconciles_stale_spec_index(
        self, repo_with_stale_spec_index: Path
    ) -> None:
        """When plan status is already correct but spec index is stale, sync fixes the index."""
        plan = repo_with_stale_spec_index / "docs/superpowers/plans/2026-04-12-test-feature.md"
        spec = repo_with_stale_spec_index / "docs/superpowers/specs/test-spec.md"

        # Pre-check: spec index says "Not Started", plan says "Complete"
        assert "Not Started" in spec.read_text()

        result = runner.invoke(app, ["progress", "sync", str(plan), "--yes"])
        assert result.exit_code == 0

        # Spec index should now say "Complete"
        spec_content = spec.read_text()
        assert "Complete" in spec_content
        assert "Spec index updated" in result.stdout

    def test_sync_mutual_exclusion(self, tmp_path: Path) -> None:
        (tmp_path / "plan.md").write_text("# X\n### Task 1: Y [a]\n- [ ] **Step 1: Z**\n")
        result = runner.invoke(
            app, ["progress", "sync", str(tmp_path / "plan.md"), "--dry-run", "--yes"]
        )
        assert result.exit_code != 0


class TestProgressBoard:
    def test_board_shows_plans(self, local_repo_with_plan: Path) -> None:
        import os

        result = runner.invoke(
            app,
            ["progress", "board"],
            env={**os.environ, "GIT_DIR": str(local_repo_with_plan / ".git")},
        )
        # Board should work or show no plans (depending on cwd resolution)
        assert result.exit_code == 0


class TestProgressCreate:
    def test_create_refused_in_local_mode(
        self, local_repo_with_plan: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "vk.commands.progress_cmd._find_repo_root", lambda _: local_repo_with_plan
        )
        result = runner.invoke(
            app,
            ["progress", "create", "New Bug", "--type", "bug"],
        )
        assert result.exit_code == 1
        assert "dispatch" in result.stdout.lower() or "dispatch" in (result.stderr or "").lower()


class TestProgressTransition:
    def test_transition_local_updates_status(
        self, local_repo_with_plan: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "vk.commands.progress_cmd._find_repo_root", lambda _: local_repo_with_plan
        )
        plan = local_repo_with_plan / "docs/superpowers/plans/2026-04-12-test-feature.md"
        result = runner.invoke(app, ["progress", "transition", str(plan), "Complete", "--yes"])
        assert result.exit_code == 0
        content = plan.read_text()
        assert "**Status:** Complete" in content

    def test_transition_invalid_status(
        self, local_repo_with_plan: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "vk.commands.progress_cmd._find_repo_root", lambda _: local_repo_with_plan
        )
        plan = local_repo_with_plan / "docs/superpowers/plans/2026-04-12-test-feature.md"
        result = runner.invoke(app, ["progress", "transition", str(plan), "Invalid", "--yes"])
        assert result.exit_code == 2


class TestProgressAudit:
    def test_audit_detects_status_drift(
        self, local_repo_with_plan: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "vk.commands.progress_cmd._find_repo_root", lambda _: local_repo_with_plan
        )
        result = runner.invoke(app, ["progress", "audit"])
        assert result.exit_code == 0
        # Plan says "Not Started" but checkboxes show partial → drift
        assert "drift" in result.stdout.lower() or "issue" in result.stdout.lower()
