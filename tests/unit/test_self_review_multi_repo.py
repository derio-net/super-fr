"""Tests for vk plan self-review multi-repo warning (Thread 1a)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()

_DISPATCH_CONFIG = """\
plan:
  save_to: docs/superpowers/plans/
dispatch:
  target: github-issues
  owner: derio-net
  default_repo: derio-net/frank
  labels:
    agentic: vk-ready
    manual: manual
"""

_NO_DISPATCH_CONFIG = """\
plan:
  save_to: docs/superpowers/plans/
"""

PLAN_MIXED_REPOS = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Target repo:** derio-net/frank
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**

## Phase 2: Phase B [agentic]
**Target repo:** derio-net/agent-images
**Depends on:** Phase 1

### Task 1: Something

- [ ] **Step 1: Do B**
"""

PLAN_SAME_REPO = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Target repo:** derio-net/frank
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**

## Phase 2: Phase B [agentic]
**Target repo:** derio-net/frank
**Depends on:** Phase 1

### Task 1: Something

- [ ] **Step 1: Do B**
"""

PLAN_NO_TARGET = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**
"""


def _write_config(tmp_path: Path, content: str) -> None:
    config_dir = tmp_path / "docs" / "superpowers"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "plan-config.yaml").write_text(content)


def _write_plan(tmp_path: Path, content: str) -> Path:
    plan_dir = tmp_path / "docs" / "superpowers" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "test-plan.md"
    plan_path.write_text(content)
    return plan_path


def test_mixed_target_repos_warns_with_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_MIXED_REPOS)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stdout or "")
    assert "Multi-repo plan" in combined


def test_same_target_repo_no_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_SAME_REPO)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")


def test_no_target_repo_no_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_NO_TARGET)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")


def test_mixed_target_no_dispatch_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _write_config(tmp_path, _NO_DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_MIXED_REPOS)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")
