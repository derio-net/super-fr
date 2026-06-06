"""super-fr base — v2 plan-as-folder model + projection chain."""

from importlib.metadata import version

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
    "parse",
]
