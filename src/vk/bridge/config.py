"""Per-tick VK-known-repo lookup.

VK keeps an enumerable list of repos it knows about. The bridge
refuses to dispatch a phase whose `tracking_issue` lives outside
that list — dispatch against an unknown repo always fails
server-side, but the failure mode is opaque to operators ("workspace
create returned 500"). Pre-flighting via `list_repos` gives us a
clean failure-metric reason and keeps Pushgateway counters honest.

The bridge runs single-MCP-per-process, so the cache is a single
optional snapshot rather than a per-client dict. `clear_repo_cache()`
fires once per tick (the daemon — or `vk.bridge.tick` — calls it)
so config drift propagates without a daemon restart.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

__all__ = ["clear_repo_cache", "is_known_repo", "known_repos"]

logger = logging.getLogger(__name__)


class _RepoLister(Protocol):
    def list_repos(self) -> Any: ...


# Single-slot cache: `None` means "not yet queried this tick".
# Earlier revisions used `dict[int, set[str]]` keyed on `id(mcp)`, but
# `id()` is reused after GC and the bridge only ever holds one MCP
# client per process anyway — the dict added a collision surface for
# tests that recycled FakeMcpClient instances without paying for any
# real flexibility.
_cache: set[str] | None = None


def clear_repo_cache() -> None:
    """Drop the cached `list_repos` snapshot. The daemon (and tick)
    call this once per iteration so config drift propagates."""
    global _cache
    _cache = None


def known_repos(mcp: _RepoLister) -> set[str]:
    """Return the cached set of repo names known to VK.

    On first call after `clear_repo_cache()` (or process start),
    performs one `list_repos` roundtrip and caches the result.
    Accepts both list-of-dicts and dict-wrapped responses (legacy +
    current wire shapes). A `list_repos` failure is logged and
    cached as the empty set — the bridge then refuses to dispatch
    until the next tick clears and retries.
    """
    global _cache
    if _cache is not None:
        return _cache
    try:
        resp = mcp.list_repos()
    except Exception as e:  # noqa: BLE001 — tick must survive an MCP hiccup
        logger.warning("config: list_repos failed: %s", e)
        _cache = set()
        return _cache
    if resp is None:
        repos: list[Any] = []
    elif isinstance(resp, dict):
        repos = resp.get("repos", resp.get("workspaces", [])) or []
    else:
        repos = resp
    _cache = {r["name"] for r in repos if isinstance(r, dict) and isinstance(r.get("name"), str)}
    return _cache


def is_known_repo(repo: str, mcp: _RepoLister) -> bool:
    """True iff `repo` (owner/name) is in VK's known-repo list."""
    return repo in known_repos(mcp)
