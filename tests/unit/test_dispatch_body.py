"""Tests for _build_issue_body in dispatch_cmd."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from vk.commands.dispatch_cmd import (
    _build_issue_body,
    _build_issue_title,
    _plan_path_for_body,
)
from vk.plan.models import Phase


def _make_phase(number: int, title: str = "Setup", tag: str = "agentic") -> Phase:
    return Phase(number=number, title=title, tag=tag, depends_on=(), tasks=(), tracking_url=None)


class TestBuildIssueBody:
    def test_contains_instruction_section(self) -> None:
        body = _build_issue_body(
            _make_phase(0),
            Path("/tmp/plan.md"),
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "## Instruction" in body
        assert "superpowers-for-vk:vk-execute" in body

    def test_contains_workspace_section(self) -> None:
        body = _build_issue_body(
            _make_phase(0),
            Path("/tmp/plan.md"),
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "## Workspace" in body
        assert "Repos: org/repo" in body

    def test_contains_dependencies_section(self) -> None:
        body = _build_issue_body(
            _make_phase(2),
            Path("/tmp/plan.md"),
            "org/repo",
            blocker_nums=(5,),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "## Dependencies" in body
        assert "- Blocked by #5" in body

    def test_phase_zero_no_blocking(self) -> None:
        body = _build_issue_body(
            _make_phase(0),
            Path("/tmp/plan.md"),
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "None — no blocking phases." in body

    def test_phase_with_prev_issue(self) -> None:
        body = _build_issue_body(
            _make_phase(3),
            Path("/tmp/plan.md"),
            "org/repo",
            blocker_nums=(42,),
            total_phases=4,
            spec="s.md",
            goal="G.",
        )
        assert "- Blocked by #42" in body

    def test_header_contains_phase_info(self) -> None:
        body = _build_issue_body(
            _make_phase(1, title="Bootstrap"),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(10,),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "🎯 Phase:  1/3 — Bootstrap [agentic]" in body

    def test_manual_type(self) -> None:
        body = _build_issue_body(
            _make_phase(0, tag="manual"),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "[manual]" in body

    def test_plan_path_in_body(self) -> None:
        plan = Path("/home/user/docs/plans/2026-04-12-feature.md")
        body = _build_issue_body(
            _make_phase(0),
            plan,
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert f"📋 Plan:   {plan}" in body

    def test_footer_contains_phase_title(self) -> None:
        body = _build_issue_body(
            _make_phase(2, title="Integration"),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(10,),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "🎯 Phase:  2/3 — Integration" in body

    def test_instruction_references_phase_number(self) -> None:
        body = _build_issue_body(
            _make_phase(5, title="Deploy"),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(10,),
            total_phases=6,
            spec="s.md",
            goal="G.",
        )
        assert "Phase 5 of this plan" in body

    def test_tracking_block_includes_repo_plan_spec(self) -> None:
        body = _build_issue_body(
            _make_phase(1, title="Bootstrap"),
            Path("docs/superpowers/plans/2026-04-14-feature.md"),
            "org/repo",
            blocker_nums=(10,),
            total_phases=3,
            spec="docs/superpowers/specs/2026-04-14-feature-design.md",
            goal="Build a thing that does X.",
        )
        assert "📦 Repo:   org/repo" in body
        assert "📋 Plan:   docs/superpowers/plans/2026-04-14-feature.md" in body
        assert "📐 Spec:   docs/superpowers/specs/2026-04-14-feature-design.md" in body
        assert "🎯 Phase:  1/3 — Bootstrap [agentic]" in body
        assert "**Goal (from plan):** Build a thing that does X." in body

    def test_dependencies_use_dash_prefix(self) -> None:
        body = _build_issue_body(
            _make_phase(2),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(42,),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "## Dependencies\n\n- Blocked by #42" in body

    def test_phase_zero_no_blocker_line(self) -> None:
        body = _build_issue_body(
            _make_phase(0),
            Path("/p.md"),
            "org/repo",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="G.",
        )
        assert "None — no blocking phases." in body
        assert "- Blocked by" not in body


class TestPlanPathForBody:
    def test_relativizes_plan_under_repo(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        plan = repo_root / "docs" / "superpowers" / "plans" / "2026-04-14-x.md"
        plan.parent.mkdir(parents=True)
        plan.touch()
        result = _plan_path_for_body(plan.resolve(), repo_root)
        assert result == Path("docs/superpowers/plans/2026-04-14-x.md")

    def test_falls_back_for_plan_outside_repo(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        outside = tmp_path / "other" / "plan.md"
        outside.parent.mkdir()
        outside.touch()
        resolved = outside.resolve()
        assert _plan_path_for_body(resolved, repo_root) == resolved

    @pytest.mark.skipif(sys.platform == "win32", reason="symlink perms differ on Windows")
    def test_relativizes_when_repo_root_reached_via_symlink(self, tmp_path: Path) -> None:
        """`_find_repo_root()` does not resolve its return value, so a symlinked
        repo root combined with a resolved plan path must still relativize
        cleanly — otherwise the helper falls back to the absolute path and
        leaks the dispatcher's filesystem layout into the Issue body.
        """
        real_repo = tmp_path / "real"
        real_repo.mkdir()
        plan_dir = real_repo / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / "p.md"
        plan.touch()

        symlinked_repo = tmp_path / "via-link"
        os.symlink(real_repo, symlinked_repo)

        result = _plan_path_for_body(plan.resolve(), symlinked_repo)
        assert result == Path("docs/plans/p.md")


class TestMultiBlockerBody:
    """_build_issue_body emits one '- Blocked by #N' per declared dep."""

    def test_empty_blocker_nums_emits_none(self) -> None:
        phase = Phase(
            number=1,
            title="Scaffold",
            tag="agentic",
            depends_on=(),
            tasks=(),
            tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase,
            plan_path=Path("plans/x.md"),
            target_repo="o/r",
            blocker_nums=(),
            total_phases=3,
            spec="s.md",
            goal="g",
        )
        assert "None — no blocking phases." in body
        assert "- Blocked by #" not in body

    def test_single_blocker_emits_one_line(self) -> None:
        phase = Phase(
            number=2,
            title="Second",
            tag="agentic",
            depends_on=(1,),
            tasks=(),
            tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase,
            plan_path=Path("plans/x.md"),
            target_repo="o/r",
            blocker_nums=(101,),
            total_phases=3,
            spec="s.md",
            goal="g",
        )
        assert body.count("- Blocked by #") == 1
        assert "- Blocked by #101" in body

    def test_multi_blocker_emits_lines_in_declared_order(self) -> None:
        phase = Phase(
            number=5,
            title="Fan in",
            tag="agentic",
            depends_on=(3, 4),
            tasks=(),
            tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase,
            plan_path=Path("plans/x.md"),
            target_repo="o/r",
            blocker_nums=(203, 204),
            total_phases=5,
            spec="s.md",
            goal="g",
        )
        idx_a = body.index("- Blocked by #203")
        idx_b = body.index("- Blocked by #204")
        assert idx_a < idx_b


class TestBuildIssueTitle:
    def test_title_format(self) -> None:
        phase = Phase(
            number=2,
            title="Content Migration",
            tag="agentic",
            depends_on=(),
            tasks=(),
            tracking_url=None,
        )
        title = _build_issue_title("blog-hextra", phase, target_repo="derio-net/frank", total=5)
        assert title == "[derio-net/frank] blog-hextra · Phase 2/5 · Content Migration"

    def test_manual_phase_title(self) -> None:
        phase = Phase(
            number=0,
            title="Operator Review",
            tag="manual",
            depends_on=(),
            tasks=(),
            tracking_url=None,
        )
        title = _build_issue_title("my-plan", phase, target_repo="org/repo", total=1)
        assert title == "[org/repo] my-plan · Phase 0/1 · Operator Review"
