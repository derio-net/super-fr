"""Card-title dedup detection for `fr_dispatch.tick`.

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

**v2 (2026-08-14 workflow-shapes spec §4.D).** `Runner.existing_dispatches()`
must return `WorkItem.id`s, but a VK card title only ever carried
`(repo, issue_number)` — no spec/plan slug, pre- or post-cutover. Rather
than invert that (the slugs simply aren't there to invert), the mapping
uses THIS TICK's own items as the source of truth: every item already
knows its own `id` and `(repo, issue_number)`, so a title that parses to
a coordinate one of those items also carries IS that item, dispatched
already. See `fr_vk.runner.VkRunner` for how the items get here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from fr_vk import _cardref

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr_dispatch.work_item import WorkItem

__all__ = ["fetch_existing_titles", "is_dispatched", "map_titles_to_item_ids"]


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


def map_titles_to_item_ids(titles: set[str], items: Sequence[WorkItem]) -> set[str]:
    """Map existing VK card titles back to `WorkItem.id`s, via `items`.

    `items` is THIS TICK's own eligible-item list (every item belongs to
    one plan, since `tick` runs per-plan) — each one already knows its
    `id` and `(repo, issue_number)` from `item.payload["issue_number"]`.
    A title parses to `(tag, repo, issue_number)` via `_cardref`; when
    that coordinate matches one of `items`, the card is a dispatch of
    THAT item — whether the card predates this cutover (title-only,
    no item-id concept ever existed on it) or was created by this same
    runner after it. A title with no matching item this tick (another
    plan's or phase's card) can't be resolved to an id and is skipped —
    harmlessly, since no item being checked against the returned set
    will ever share its coordinate.
    """
    by_repo_issue = {}
    for item in items:
        issue_number = item.payload.get("issue_number")
        if issue_number is None:
            continue
        by_repo_issue[(item.repo, int(issue_number))] = item.id  # type: ignore[call-overload]

    resolved: set[str] = set()
    for title in titles:
        parsed = _cardref.parse_card_title(title)
        if parsed is None:
            continue
        _tag, repo, issue_number = parsed
        item_id = by_repo_issue.get((repo, issue_number))
        if item_id is not None:
            resolved.add(item_id)
    return resolved
