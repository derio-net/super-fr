"""Public runner contract — the fr-dispatch / adapter seam.

A *runner* is whatever consumes queued phases and executes them:
VibeKanban (`fr_vk.VkRunner`, the first implementation), a future
GitHub-Actions runner, a headless `claude -p` daemon. `fr_dispatch.tick`
orchestrates the queue against this Protocol and nothing else — no
adapter types, no board vocabulary, no VK strings (2026-06-05 super-fr
split design, §Runner registry; promoted from the duck-typed MCP seam
the bridge tests already used).

Implementations are duck-typed (`Protocol`): no inheritance required.
Every method may raise — `tick` accumulates failures per phase and
never lets one bad call kill the loop (apply's doctrine).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fr.parser import Plan
    from fr.types import PhaseDoc


class Runner(Protocol):
    """One dispatch backend, as seen by `fr_dispatch.tick`."""

    name: str
    """Registry name (`runner:<name>` label value; e.g. ``vk``)."""

    def preflight(self) -> str | None:
        """Config check before any dispatch this tick.

        Return an error string (every eligible phase fails cleanly with
        it) or None when ready. Example: the VK runner requires a
        project id outside workspace contexts.
        """
        ...

    def refresh(self) -> None:
        """Per-tick cache reset so config drift propagates."""
        ...

    def slot_budget(self) -> int:
        """Remaining dispatch capacity for this tick (0 = defer all)."""
        ...

    def existing_dispatches(self) -> set[str]:
        """Dedup snapshot: keys of work already handed to this runner."""
        ...

    def dedup_key(self, repo: str, issue_number: int) -> str:
        """The key `existing_dispatches` uses for one phase's Issue."""
        ...

    def can_dispatch_repo(self, repo: str) -> bool:
        """Repo gate — refuse early when the backend doesn't know it."""
        ...

    def dispatch(self, plan: Plan, phase: PhaseDoc, repo: str, issue_number: int) -> None:
        """Hand one phase to the backend (create card/job/workspace…).

        Raising marks the phase failed for this tick; the synced stamp
        is NOT written, so the next tick retries.
        """
        ...
