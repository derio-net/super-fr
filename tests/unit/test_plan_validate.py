from __future__ import annotations

import pytest

from vk.plan.models import Phase, Plan, PlanFormat
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
