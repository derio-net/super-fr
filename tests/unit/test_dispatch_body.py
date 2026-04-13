"""Tests for _build_issue_body in dispatch_cmd."""

from __future__ import annotations

from pathlib import Path

from vk.commands.dispatch_cmd import _build_issue_body
from vk.plan.models import Phase


def _make_phase(number: int, title: str = "Setup", tag: str = "agentic") -> Phase:
    return Phase(number=number, title=title, tag=tag, tasks=(), tracking_url=None)


class TestBuildIssueBody:
    def test_contains_instruction_section(self) -> None:
        body = _build_issue_body(
            _make_phase(1), Path("/tmp/plan.md"), "org/repo", prev_num=None
        )
        assert "## Instruction" in body
        assert "superpowers-for-vk:vk-execute" in body

    def test_contains_workspace_section(self) -> None:
        body = _build_issue_body(
            _make_phase(1), Path("/tmp/plan.md"), "org/repo", prev_num=None
        )
        assert "## Workspace" in body
        assert "Repos: org/repo" in body

    def test_contains_dependencies_section(self) -> None:
        body = _build_issue_body(
            _make_phase(2), Path("/tmp/plan.md"), "org/repo", prev_num=5
        )
        assert "## Dependencies" in body
        assert "Blocked by #5" in body

    def test_phase_zero_no_blocking(self) -> None:
        body = _build_issue_body(
            _make_phase(0), Path("/tmp/plan.md"), "org/repo", prev_num=None
        )
        assert "None — no blocking phases." in body

    def test_phase_one_no_prev_issue(self) -> None:
        body = _build_issue_body(
            _make_phase(1), Path("/tmp/plan.md"), "org/repo", prev_num=None
        )
        assert "Phases 0-0 complete." in body
        assert "Blocked by" not in body

    def test_phase_with_prev_issue(self) -> None:
        body = _build_issue_body(
            _make_phase(3), Path("/tmp/plan.md"), "org/repo", prev_num=42
        )
        assert "Phases 0-2 complete. Blocked by #42." in body

    def test_header_contains_phase_info(self) -> None:
        body = _build_issue_body(
            _make_phase(1, title="Bootstrap"), Path("/p.md"), "org/repo", prev_num=None
        )
        assert "# Phase 1: Bootstrap" in body
        assert "**Type:** Agentic" in body
        assert "**Phase:** 1" in body

    def test_manual_type(self) -> None:
        body = _build_issue_body(
            _make_phase(1, tag="manual"), Path("/p.md"), "org/repo", prev_num=None
        )
        assert "**Type:** Manual" in body

    def test_plan_path_in_body(self) -> None:
        plan = Path("/home/user/docs/plans/2026-04-12-feature.md")
        body = _build_issue_body(
            _make_phase(1), plan, "org/repo", prev_num=None
        )
        assert f"**Plan:** `{plan}`" in body
        assert f"**Plan file:** `{plan}`" in body

    def test_footer_contains_phase_title(self) -> None:
        body = _build_issue_body(
            _make_phase(2, title="Integration"), Path("/p.md"), "org/repo", prev_num=None
        )
        assert "**Phase:** 2 — Integration" in body

    def test_instruction_references_phase_number(self) -> None:
        body = _build_issue_body(
            _make_phase(5, title="Deploy"), Path("/p.md"), "org/repo", prev_num=None
        )
        assert "Phase 5 of this plan" in body
