"""Plan format enum and structural detection from markdown content."""

from __future__ import annotations

import enum
import re


class PlanFormat(enum.Enum):
    """Plan structure format, derived from dispatch presence (Decision D3)."""

    FLAT = "flat"
    PHASED = "phased"

    @property
    def can_dispatch(self) -> bool:
        """Only phased plans can be dispatched to GitHub Issues."""
        return self is PlanFormat.PHASED


_RE_PHASE_HEADER = re.compile(r"^## Phase \d+:", re.MULTILINE)
_RE_TASK_HEADER = re.compile(r"^### Task \d+:", re.MULTILINE)


def detect(markdown: str) -> PlanFormat:
    """Detect plan format from markdown content.

    Detection is structural, not config-driven:
    - At least one ``## Phase N:`` header -> PHASED
    - No phase headers but has ``### Task N:`` headers -> FLAT
    - Neither -> raises ValueError (not a fr plan)
    """
    if _RE_PHASE_HEADER.search(markdown):
        return PlanFormat.PHASED
    if _RE_TASK_HEADER.search(markdown):
        return PlanFormat.FLAT
    msg = "Cannot detect plan format — not a fr plan (no Phase or Task headers found)"
    raise ValueError(msg)
