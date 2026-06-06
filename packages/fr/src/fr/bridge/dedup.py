"""Card-title dedup detection for `fr.bridge.tick`.

Detection lives in tick (not `dispatch_phase`) because the decision
needs both the MCP card listing and the GH client used to stamp
`vk-synced` on the source Issue. `dispatch_phase`'s signature
`(plan, phase, mcp)` has no `gh` client, so it can't drive the
post-dedup label stamp anyway.

The contract is "title equality" rather than richer matching: if a
human (or an earlier botched dispatch) created a card with the exact
title `gh#<n>: [<owner/repo>]`, we treat the phase as already synced
and idempotency-stamp the GH Issue. Anything fancier (fuzzy match on
issue number) would risk false positives across plans that legitimately
reuse phase numbers.
"""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["fetch_existing_titles", "is_dispatched"]


class _IssueLister(Protocol):
    def list_issues(self, **kwargs: Any) -> Any: ...


def fetch_existing_titles(mcp: _IssueLister, *, project_id: str | None = None) -> set[str]:
    """Return the set of card titles currently visible in VK.

    Accepts the bare-list or dict-wrapped shape — same defensive
    posture as `slots.count_active_ws`. A missing/None response is
    treated as the empty set so a transient list_issues hiccup
    can't trip a duplicate-card creation: dispatch will surface its
    own server-side conflict if a real collision exists.

    When `project_id` is supplied, the call is scoped to that VK
    project — both for correctness (VK requires `project_id` when the
    MCP server isn't running in a workspace context) and to avoid
    matching unrelated cards from other projects.
    """
    kwargs: dict[str, str] = {}
    if project_id:
        kwargs["project_id"] = project_id
    resp = mcp.list_issues(**kwargs)
    if resp is None:
        return set()
    items = resp.get("issues", []) if isinstance(resp, dict) else resp
    return {item["title"] for item in items if isinstance(item, dict) and "title" in item}


def is_dispatched(title: str, existing: set[str]) -> bool:
    """True iff `title` is already a card title in VK."""
    return title in existing
