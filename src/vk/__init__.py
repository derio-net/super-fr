"""VK CLI toolchain — v2 plan-as-folder model + projection chain."""

from importlib.metadata import version

from vk.parser import Plan, PlanSchemaError, parse
from vk.types import (
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

__version__ = version("vk")

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
