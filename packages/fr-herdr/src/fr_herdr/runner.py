"""`HerdrRunner` — stub (spec 2026-09-25-triage-batches §3.C, plan phase 1).

Satisfies the `fr_dispatch.protocols.Runner` shape so the package can be
registered, type-checked and wired into CI before it does anything:
`can_dispatch` refuses every item, `slot_budget` is 0, and `dispatch`
raises. The real launch (herdr tab, agent start, prompt) arrives in phase 2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr_dispatch.work_item import WorkItem


class HerdrRunner:
    """The herdr runner, not yet able to take any item."""

    name = "herdr"
    capabilities: frozenset[str] = frozenset()

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        return "runner `herdr` is a skeleton and cannot dispatch yet"

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 0

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        return set()

    def can_dispatch(self, item: WorkItem) -> bool:
        return False

    def dispatch(self, item: WorkItem) -> None:
        raise NotImplementedError("runner `herdr` is a skeleton and cannot dispatch yet")
