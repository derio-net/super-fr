"""`VkRunner` — VibeKanban's implementation of the Runner protocol.

Wraps the MCP client + project id and delegates to the VK-shaped
modules that used to be welded into the tick loop (2026-06-05 super-fr
split design): slot accounting (`fr_vk.slots`), card-title dedup
(`fr_vk.dedup`), the known-repo gate (`fr_vk.config`), and the canonical
card+workspace creation chain (`fr_vk.dispatch.dispatch_phase`, B2
single-source).

`project_id` resolution preserves the legacy env conventions:
`VK_DERIO_OPS_PROJECT_ID` (canonical, K8s-injected) with
`VK_DERIO_OPS_PROJECT` as fallback. VK's `create_issue`/`list_issues`
require it outside a workspace context — exactly the cron bridge's case
— so `preflight()` fails every eligible phase cleanly when unset.

**v2 (2026-08-14 workflow-shapes spec §4.D).** `dedup_key` and
`can_dispatch_repo` are gone; identity lives on `WorkItem.id` and the
repo gate reads `item.repo`. `existing_dispatches()` still has to answer
in card-*title* terms (VK's board has no item-id concept, pre- or
post-cutover), but per the protocol it takes no arguments — so it maps
titles back to ids using THIS TICK's own items, cached from the
`preflight(items)` call that always precedes it in `tick`'s per-plan
loop (see `fr_dispatch.tick`). Every item in one tick shares one plan,
so `(item.repo, item.payload["issue_number"])` is a stable coordinate a
title also carries (`fr_vk.dedup.map_titles_to_item_ids`) — no title
format change, no inversion of spec/plan slugs that were never encoded
in the title to begin with (see the 2026-08-14 plan journal, phase 2/3
findings). This is what makes a VK card created *before* this cutover
still dedup correctly on the first post-deploy tick.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fr_vk import config as _config
from fr_vk import dedup as _dedup
from fr_vk import slots as _slots
from fr_vk.dispatch import MCPDispatch, dispatch_phase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr_dispatch.work_item import WorkItem

# Reserved for a runner that builds its own agent prompt (fr_dispatch.prompt.
# build_prompt params). VK derives workspace prompts server-side from the
# card description, so these are not consumed in the VK dispatch flow today.
AGENT_IDENTITY = "a VK-spawned agent"
EXECUTE_SKILL = "super-fr:fr-execute"
METRICS_NAMESPACE = "willikins_vk_bridge"
METRICS_JOB = "vk_issue_bridge"
HEARTBEAT_METRIC = "willikins_heartbeat_last_success_timestamp"
# Generic tick reason kinds -> the legacy wire values dashboards expect.
METRICS_REASON_ALIASES = {
    "backend_error": "mcp_error",
    "preflight": "project_id_missing",
}


def _env_project_id() -> str | None:
    return (
        os.environ.get("VK_DERIO_OPS_PROJECT_ID") or os.environ.get("VK_DERIO_OPS_PROJECT") or None
    )


class VkRunner:
    """Runner-protocol adapter over a VibeKanban MCP client."""

    name = "vk"

    capabilities = frozenset({"git", "tests", "scm"})

    def __init__(self, mcp: MCPDispatch, *, project_id: str | None = None) -> None:
        self.mcp = mcp
        self.project_id = project_id if project_id is not None else _env_project_id()
        # Cached by `preflight(items)`, which `fr_dispatch.tick` always calls
        # before `existing_dispatches()` in the same tick — see the module
        # docstring for why this is what lets a title-only VK card dedup.
        self._items_this_tick: Sequence[WorkItem] = ()

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        self._items_this_tick = items
        if not self.project_id:
            return (
                "VK_DERIO_OPS_PROJECT unset; cannot dispatch "
                "(set the env or pass project_id explicitly)"
            )
        return None

    def refresh(self) -> None:
        # Fresh repo lookup per tick so config drift propagates.
        _config.clear_repo_cache()

    def slot_budget(self) -> int:
        return _slots.max_concurrent() - _slots.count_active_ws(self.mcp)

    def existing_dispatches(self) -> set[str]:
        titles = _dedup.fetch_existing_titles(self.mcp, project_id=self.project_id)
        return _dedup.map_titles_to_item_ids(titles, self._items_this_tick)

    def can_dispatch(self, item: WorkItem) -> bool:
        return _config.is_known_repo(item.repo, self.mcp)

    def dispatch(self, item: WorkItem) -> None:
        # preflight() guarantees project_id is set before tick dispatches.
        assert self.project_id is not None
        plan = item.payload["plan"]
        phase = item.payload["phase"]
        dispatch_phase(plan, phase, self.mcp, project_id=self.project_id)  # type: ignore[arg-type]
