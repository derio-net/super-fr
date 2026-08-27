"""Public runner contract — the fr-dispatch / adapter seam.

A *runner* is whatever consumes queued work items and executes them:
VibeKanban (`fr_vk.VkRunner`, the first implementation), the cncd control
plane (`fr_cncd.CncdRunner`), a future GitHub-Actions runner, a headless
agent daemon. `fr_dispatch.tick` orchestrates the queue against this
Protocol and nothing else — no adapter types, no board vocabulary, no VK
strings (2026-06-05 super-fr split design, §Runner registry; promoted from
the duck-typed MCP seam the bridge tests already used).

**v2 (2026-08-14 workflow-shapes-and-workitem-dispatch spec §4.D).** The
unit of dispatch is a `WorkItem`, not a `(plan, phase, repo, issue_number)`
tuple: the decomposition granularity (`run` | `phase` | `spec`, §4.E) is
now a workflow shape's declared `unit`, not a hardcoded assumption. Six
methods, down from seven — `dedup_key` is gone because identity lives on
the item (`WorkItem.id`), so `existing_dispatches(items)` returns item ids
and `can_dispatch_repo(repo)` widens to `can_dispatch(item)`. Hard cutover,
no compatibility shim.

Implementations are duck-typed (`Protocol`): no inheritance required.
Every method may raise — `tick` accumulates failures per item and never
lets one bad call kill the loop (apply's doctrine).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr_dispatch.work_item import WorkItem


class Runner(Protocol):
    """One dispatch backend, as seen by `fr_dispatch.tick`."""

    name: str
    """Registry name (`runner:<name>` label value; e.g. ``vk``)."""

    capabilities: frozenset[str]
    """What this backend can provide (§4.F).

    Drawn from the closed capability set (`git`, `tests`, `scm`, `browser`,
    `network`, `devcontainer`). A workflow shape declares `requires`; the
    mismatch is refused in `preflight`, which is why that method receives
    the items. The *negotiation* itself is not implemented here — declaring
    the attribute is.
    """

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        """Config/capability check before any dispatch this tick.

        Return an error string (every eligible item fails cleanly with it,
        and none is dispatched) or None when ready. Examples: the VK runner
        requires a project id outside workspace contexts; a shape requiring
        `browser` on a headless runner is refused here rather than dying
        mid-flight (§4.F).
        """
        ...

    def refresh(self) -> None:
        """Per-tick cache reset so config drift propagates."""
        ...

    def slot_budget(self) -> int:
        """Remaining dispatch capacity for this tick (0 = defer all)."""
        ...

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        """Dedup snapshot: which of `items` this runner is already holding.

        Item ids, not backend-native keys — identity is the item's position
        in the graph (`work_item.item_id`), computable before any tracker
        artifact exists. An adapter whose board stores something else (a VK
        card title, say) maps back to ids here; the title stays that
        backend's *presentation* of an item and stops being its identity.

        `items` is the same sequence `preflight` receives. An adapter that
        has to invert board state into ids needs the candidate items to
        invert *against*, and passing them is what keeps that from becoming
        an undocumented "call `preflight` first" ordering contract — one
        whose failure mode (an empty snapshot) is silent duplicate
        dispatch. Returning ids outside `items` is harmless: `tick` only
        tests membership for the items it is about to dispatch.
        """
        ...

    def can_dispatch(self, item: WorkItem) -> bool:
        """Routing gate — refuse early when this backend can't take `item`.

        Replaces `can_dispatch_repo(repo)`: the repo is still the usual
        reason to refuse (`item.repo`), but the item carries its unit,
        workflow and payload too, so a runner that only handles some units
        can say so without a second protocol method.
        """
        ...

    def dispatch(self, item: WorkItem) -> None:
        """Hand one item to the backend (create card/job/workspace…).

        Raising marks the item failed for this tick; the dispatch stamp is
        NOT written, so the next tick retries.
        """
        ...
