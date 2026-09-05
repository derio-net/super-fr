"""Card-title dedup detection for `fr_dispatch.tick`.

Detection lives in tick (not `dispatch_phase`) because the decision
needs both the MCP card listing and the GH client used to stamp
`vk-synced` on the source Issue. `dispatch_phase`'s signature
`(plan, phase, mcp)` has no `gh` client, so it can't drive the
post-dedup label stamp anyway.

The contract is card-*coordinate* equality — `(backend tag, repo, issue
number)`, parsed off the title: if a human (or an earlier botched
dispatch) created a card for the same coordinate, we treat the phase as
already synced and idempotency-stamp the GH Issue. Nothing fuzzier (a
match on issue number alone, or across backends) — that would risk false
positives across plans that legitimately reuse phase numbers, and across
hosts that legitimately reuse issue numbers.

**v2 (2026-08-14 workflow-shapes spec §4.D).**
`Runner.existing_dispatches(items)` must return `WorkItem.id`s, but a VK card
title only ever carried `(repo, issue_number)` — no spec/plan slug, pre- or
post-cutover. Rather than invert that (the slugs simply aren't there to
invert), the mapping uses the tick's own items as the source of truth: every
item already knows its `id` and `(repo, issue_number)`, so a title that parses
to a coordinate one of those items also carries IS that item, dispatched
already. The items are a parameter all the way down — `tick` → `VkRunner` →
here — so nothing depends on an earlier call having cached them.
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

    `items` is the tick's own eligible-item list (every item belongs to one
    plan, since `tick` runs per-plan) — each one already knows its `id` and
    `(repo, issue_number)` from `item.payload["issue_number"]`.

    The coordinate is the FULL `(tag, repo, issue_number)` triple
    `_cardref.parse_card_title` returns, not just `(repo, issue_number)`:
    the backend tag is what tells `gh#`/`gl#`/`gt#` cards apart, and
    dropping it would let a card for another host's issue #42 suppress the
    dispatch of `owner/repo#42` here — while `tick` still stamped
    `fr:synced`, so the real dispatch would never happen and never retry.
    The expected tag comes from `_cardref.DISPATCH_BACKEND`, the same
    constant `dispatch.build_card_title` stamps with, so producer and dedup
    cannot drift apart.

    Matching is on the coordinate, not on the whole title string: a title
    carrying a free-text suffix (`"gh#42: [owner/repo] retry"`) is the same
    card, and the pre-cutover exact-string compare would have created a
    duplicate card + workspace for it. `_cardref`'s regex is prefix-anchored
    for exactly that tolerance.

    A title with no matching item this tick (another plan's or phase's
    card) can't be resolved to an id and is skipped — harmlessly, since no
    item being checked against the returned set shares its coordinate.
    """
    expected_tag = _cardref.TAG_FOR_BACKEND[_cardref.DISPATCH_BACKEND]
    by_coordinate: dict[tuple[str, str, int], str] = {}
    for item in items:
        issue_number = item.payload.get("issue_number")
        if issue_number is None:
            continue
        key = (expected_tag, item.repo, int(issue_number))  # type: ignore[call-overload]
        by_coordinate[key] = item.id

    resolved: set[str] = set()
    for title in titles:
        parsed = _cardref.parse_card_title(title)
        if parsed is None:
            continue
        item_id = by_coordinate.get(parsed)
        if item_id is not None:
            resolved.add(item_id)
    return resolved
