"""Structural validation for phase dependency declarations."""

from __future__ import annotations

from vk.plan.models import Plan


class DagValidationError(ValueError):
    """Raised when a plan's declared DAG is structurally invalid."""


def validate_dag(plan: Plan) -> None:
    """Check cycle, forward-ref, self-ref, unknown-ref. Skip missing-line check.

    Backward-only deps (depends_on[i] < i) make cycles impossible unless a
    forward reference is present; checking forward-ref is the cycle check.
    """
    known = {p.number for p in plan.phases}
    for phase in plan.phases:
        for dep in phase.depends_on:
            if dep == phase.number:
                raise DagValidationError(f"Phase {phase.number} depends on itself.")
            if dep not in known:
                raise DagValidationError(
                    f"Phase {phase.number} depends on Phase {dep}, "
                    f"which does not exist in this plan."
                )
            if dep >= phase.number:
                raise DagValidationError(
                    f"Phase {phase.number} depends on Phase {dep} — "
                    f"forward reference; only backward deps are permitted."
                )
