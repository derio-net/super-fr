"""VK CLI toolchain — v2 plan-as-folder model + projection chain."""

from importlib.metadata import version

from fr import bridge as bridge  # noqa: F401 — public sub-package for the live VK bridge
from fr.parser import Plan, PlanSchemaError, parse
from fr.types import (
    Completion,
    OriginItem,
    PhaseDoc,
    PhaseHeader,
    PhaseStateBlock,
    PlanMeta,
    Step,
    StepState,
    Task,
)

__version__ = version("fr")

__all__ = [
    "Completion",
    "OriginItem",
    "PhaseDoc",
    "PhaseHeader",
    "PhaseStateBlock",
    "Plan",
    "PlanMeta",
    "PlanSchemaError",
    "Step",
    "StepState",
    "Task",
    "__version__",
    "bridge",
    "parse",
]
