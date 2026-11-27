"""The plan writers' one error type (moved from `fr.plan_ops`, spec 2026-11-27-plan-ops-split R4).

A leaf: it imports nothing from `fr`, so every module that raises it can.
"""

from __future__ import annotations


class PlanEditError(Exception):
    """Raised when an editing operation can't proceed."""
