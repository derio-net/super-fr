"""PR-status observer for the bridge tick (#290).

Builds the `{card_id: "open"|"merged"}` map that `pr_state.tick` consumes.
For each active VK card (`In progress` / `In review`), resolves the card's
`latest_pr_url` to its merge state via the backend-appropriate `GhClient`
adapter (injectable for tests, mirroring `pr_state.tick`'s `close_gh_issue`
seam) — resolved per-URL via its own hostname, since one VK board can hold
cards from repos on different backends. Previously shelled out to a raw
`gh pr view` subprocess directly, bypassing `GhClient` entirely; fixed as
part of the multi-backend design (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §6).

This is the wiring the v2-bridge-rebuild deferred ("observations are wired in
Phase 6") and never landed — leaving `pr_state.tick` fed an empty map and the
Issue auto-close path dead. See #290.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlparse

from fr import _hosts, hostclient

from fr_vk.pr_state import _normalize_issues

__all__ = ["observe_pr_status"]

logger = logging.getLogger(__name__)


class _CardLister(Protocol):
    def list_issues(self, **kwargs: Any) -> Any: ...


def _default_pr_status_fetch(pr_url: str) -> str | None:
    """Resolve a PR URL to `"open"`/`"merged"` via the backend-appropriate
    `GhClient` adapter, else None.

    `"merged"` for a merged PR, `"open"` for an open non-draft PR; drafts,
    closed-unmerged PRs, and any failure (client missing/erroring,
    unresolvable URL) map to None so the observer simply omits that card.
    Non-fatal. The backend is resolved from `pr_url`'s own hostname
    (`fr._hosts.backend_for_hostname`) — NOT from any ambient single-repo
    context — since one VK board can hold cards from repos on different
    backends.
    """
    hostname = urlparse(pr_url).hostname
    backend = _hosts.backend_for_hostname(hostname)
    client = hostclient.client_for_backend(backend)
    try:
        result = client.pr_status_by_url(pr_url)
    except Exception as e:  # noqa: BLE001 — non-fatal, mirrors the old subprocess posture
        logger.warning("pr_observe: pr_status_by_url(%s) failed: %s", pr_url, e)
        return None
    if result is None:
        return None
    state = result.get("state")
    if state == "MERGED":
        return "merged"
    if state == "OPEN" and not bool(result.get("draft")):
        return "open"
    # A draft (OPEN+draft) or a closed-unmerged PR maps to None — an
    # intentional "hold this card" (the consumer acts only on open/merged),
    # NOT an error. Do not "fix" drafts to "open".
    return None


def observe_pr_status(
    mcp: _CardLister,
    *,
    project_id: str | None = None,
    pr_status_fetch: Callable[[str], str | None] | None = None,
) -> dict[str, str]:
    """Return `{card_id: "open"|"merged"}` for active cards with a linked PR.

    Lists cards in `In progress` and `In review` (the statuses `pr_state.tick`
    acts on), resolves each card's `latest_pr_url` to its state, and keeps
    only `open`/`merged` (drafts, closed-unmerged, and url-less cards are
    omitted — nothing to transition). Each card's PR is resolved at most once
    even if the MCP server doesn't honour the status filter.

    Fully defensive: a `list_issues` failure or a per-card fetch error is
    logged and skipped — the observer never raises, so a hiccup can't kill the
    tick (which already wraps the sweep in a `pr_state_error` guard).
    """
    fetch = pr_status_fetch if pr_status_fetch is not None else _default_pr_status_fetch
    out: dict[str, str] = {}
    seen: set[str] = set()

    for status in ("In progress", "In review"):
        kwargs: dict[str, Any] = {"status": status}
        if project_id is not None:
            kwargs["project_id"] = project_id
        try:
            resp = mcp.list_issues(**kwargs)
        except Exception as e:  # noqa: BLE001 — non-fatal
            logger.warning("pr_observe: list_issues(%s) failed: %s", status, e)
            continue
        for card in _normalize_issues(resp):
            cid = card.get("id")
            url = card.get("latest_pr_url")
            if not isinstance(cid, str) or not cid or cid in seen:
                continue
            if not isinstance(url, str) or not url:
                continue
            seen.add(cid)
            try:
                st = fetch(url)
            except Exception as e:  # noqa: BLE001 — one bad PR mustn't drop the map
                logger.warning("pr_observe: PR status fetch failed for %s: %s", url, e)
                continue
            if st in ("open", "merged"):
                out[cid] = st
    return out
