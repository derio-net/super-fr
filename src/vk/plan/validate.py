"""Structural validation for phase dependency declarations."""

from __future__ import annotations

from pathlib import Path

from vk.plan.models import Plan


class DagValidationError(ValueError):
    """Raised when a plan's declared DAG is structurally invalid."""


def validate_dag(plan: Plan, plan_path: Path | None = None) -> None:
    """Check cycle, forward-ref, self-ref, unknown-ref, and missing-line.

    Backward-only deps (depends_on[i] < i) make cycles impossible unless a
    forward reference is present; checking forward-ref is the cycle check.

    When ``plan_path`` is supplied and does NOT live under ``archived-plans/``,
    additionally enforce that every phase declared a ``**Depends on:**`` line
    (spec §1.3). Passing ``plan_path=None`` (the test-helper default) keeps
    the old lax behaviour for in-memory fixtures.
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

    if plan_path is None:
        return
    if "archived-plans" in plan_path.parts:
        return
    if not plan.phase_has_depends_line:
        # Guards an in-memory Plan(...) built by a caller that passed
        # ``phases`` but left ``phase_has_depends_line`` at its default
        # empty tuple. Without this early return the strict zip below
        # would raise on a length mismatch. Real parser output always
        # populates both tuples in lockstep; this path only fires for
        # test fixtures and the flat-format case (no phases).
        return

    for phase, present in zip(plan.phases, plan.phase_has_depends_line, strict=True):
        if not present:
            raise DagValidationError(
                f"Phase {phase.number} has no **Depends on:** line. "
                f"Run 'vk plan convert {plan_path} --add-deps --yes' to migrate, "
                f"or declare it manually."
            )
