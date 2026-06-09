"""PR-status observer for the bridge tick (#290).

Builds the `{card_id: "open"|"merged"}` map that `pr_state.tick` consumes.
For each active VK card (`In progress` / `In review`), resolves the card's
`latest_pr_url` to its merge state via `gh pr view` (injectable for tests,
mirroring `pr_state.tick`'s `close_gh_issue` seam).

This is the wiring the v2-bridge-rebuild deferred ("observations are wired in
Phase 6") and never landed — leaving `pr_state.tick` fed an empty map and the
Issue auto-close path dead. See #290.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from typing import Any, Protocol

from fr_vk.pr_state import _normalize_issues

__all__ = ["observe_pr_status"]

logger = logging.getLogger(__name__)


class _CardLister(Protocol):
    def list_issues(self, **kwargs: Any) -> Any: ...


def _default_pr_status_fetch(pr_url: str) -> str | None:
    """Resolve a PR URL to `"open"`/`"merged"` via `gh pr view`, else None.

    `"merged"` for a merged PR, `"open"` for an open non-draft PR; drafts,
    closed-unmerged PRs, and any failure (gh missing, rate-limited, malformed
    JSON) map to None so the observer simply omits that card. Non-fatal.
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_url, "--json", "state,isDraft"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("pr_observe: gh pr view %s failed: %s", pr_url, e)
        return None
    if result.returncode != 0:
        logger.warning(
            "pr_observe: gh pr view %s failed (rc=%s): %s",
            pr_url,
            result.returncode,
            (result.stderr or "").strip()[:512],
        )
        return None
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    state = data.get("state")
    if state == "MERGED":
        return "merged"
    if state == "OPEN" and not bool(data.get("isDraft")):
        return "open"
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
