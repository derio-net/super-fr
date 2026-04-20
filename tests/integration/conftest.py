"""Integration test fixtures."""

from __future__ import annotations

import subprocess
import textwrap
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repo with plan-config.yaml."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    yield tmp_path


@pytest.fixture()
def dispatch_config(tmp_repo: Path) -> Path:
    """Create a dispatch-enabled plan-config.yaml."""
    config_dir = tmp_repo / "docs" / "superpowers"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "plan-config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        plan:
          filename: "YYYY-MM-DD-{name}.md"
          save_to: docs/superpowers/plans/

        header:
          required:
            - Spec
            - Status
          status_values:
            - Not Started
            - In Progress
            - Complete

        dispatch:
          target: github-issues
          owner: derio-net
          project_board: "Derio Ops"
          default_repo: derio-net/test-repo
          labels:
            agentic: vk-ready
            manual: manual
    """)
    )
    return config_file


@pytest.fixture()
def phased_plan(tmp_repo: Path) -> Path:
    """Create a phased plan file for dispatch testing."""
    plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "2026-04-12-test-feature.md"
    plan_file.write_text(
        textwrap.dedent("""\
        # Test Feature Implementation Plan

        **Spec:** `docs/superpowers/specs/2026-04-12-test-feature.md`
        **Status:** Not Started

        **Goal:** Implement the test feature.

        ---

        ## Phase 0: Setup [agentic]
        **Depends on:** —

        ### Task 1: Create schema

        - [ ] **Step 1: Write the test**
        - [ ] **Step 2: Implement**

        ## Phase 1: Integration [manual]
        **Depends on:** Phase 0

        ### Task 1: Configure DNS

        - [ ] **Step 1: Log in to dashboard**
        - [ ] **Step 2: Add records**

        ## Phase 2: Finalize [agentic]
        **Depends on:** Phase 1

        ### Task 1: Write docs

        - [ ] **Step 1: Draft README**
    """)
    )
    return plan_file
