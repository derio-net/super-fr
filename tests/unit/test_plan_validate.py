from __future__ import annotations

from pathlib import Path

import pytest

from vk.plan.models import Phase, Plan, PlanFormat
from vk.plan.parser import parse_plan
from vk.plan.validate import DagValidationError, validate_dag


def _phase(number: int, depends_on: tuple[int, ...]) -> Phase:
    return Phase(
        number=number,
        title=f"Phase {number}",
        tag="agentic",
        depends_on=depends_on,
        tasks=(),
        tracking_url=None,
    )


def _plan(phases: tuple[Phase, ...]) -> Plan:
    return Plan(
        title="T",
        spec="s.md",
        status="Not Started",
        goal="g",
        format=PlanFormat.PHASED,
        phases=phases,
        tasks=(),
    )


class TestValidateDag:
    def test_root_only_plan_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()),)))

    def test_linear_plan_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()), _phase(2, (1,)), _phase(3, (2,)))))

    def test_fan_in_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()), _phase(2, ()), _phase(3, (1, 2)))))

    def test_self_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="Phase 2 depends on itself"):
            validate_dag(_plan((_phase(1, ()), _phase(2, (2,)))))

    def test_forward_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="forward reference"):
            validate_dag(_plan((_phase(1, (2,)), _phase(2, ()))))

    def test_unknown_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="does not exist"):
            validate_dag(_plan((_phase(1, ()), _phase(2, (99,)))))

    def test_absent_depends_on_is_ignored_in_phase_1_window(self) -> None:
        """Pre-DAG plans (no **Depends on:** anywhere) pass structural validation."""
        validate_dag(_plan((_phase(1, ()), _phase(2, ()), _phase(3, ()))))


class TestMissingLineEnforcement:
    def test_missing_line_on_non_root_live_plan_fails(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        with pytest.raises(DagValidationError, match=r"has no \*\*Depends on:\*\* line"):
            validate_dag(plan, plan_path=plan_path)

    def test_missing_line_on_archived_plan_is_allowed(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "archived-plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Complete\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        validate_dag(plan, plan_path=plan_path)

    def test_root_phase_missing_line_also_fails_in_live(self, tmp_path: Path) -> None:
        """Root phases MUST declare '**Depends on:** —' explicitly in live plans."""
        plan_path = tmp_path / "plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        with pytest.raises(DagValidationError, match=r"has no \*\*Depends on:\*\* line"):
            validate_dag(plan, plan_path=plan_path)

    def test_plan_path_none_skips_missing_line_check(self, tmp_path: Path) -> None:
        """Passing plan_path=None (unit-test usage) keeps the old lax behavior."""
        validate_dag(_plan((_phase(1, ()), _phase(2, ()))), plan_path=None)

    def test_all_lines_present_passes_in_live(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n"
            "**Depends on:** Phase 1\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        validate_dag(plan, plan_path=plan_path)
