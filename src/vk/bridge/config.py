"""Per-tick VK-known-repo lookup.

VK keeps an enumerable list of repos it knows about. The bridge
refuses to dispatch a phase whose `tracking_issue` lives outside
that list — dispatch against an unknown repo always fails
server-side, but the failure mode is opaque to operators ("workspace
create returned 500"). Pre-flighting via `list_repos` gives us a
clean failure-metric reason and keeps Pushgateway counters honest.

`list_repos` is cached per-MCP-client (keyed on `id(mcp)`) so a
tick that consults the lookup many times only pays one MCP roundtrip.
The daemon explicitly clears the cache between ticks via
`clear_repo_cache()`.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

__all__ = ["clear_repo_cache", "is_known_repo", "known_repos"]

logger = logging.getLogger(__name__)


class _RepoLister(Protocol):
    def list_repos(self) -> Any: ...


_cache: dict[int, set[str]] = {}


def clear_repo_cache() -> None:
    """Drop the cached `list_repos` snapshot. The daemon calls this once
    per tick so config drift propagates."""
    _cache.clear()


def known_repos(mcp: _RepoLister) -> set[str]:
    """Return the cached set of repo names known to VK.

    On the first call for a given MCP client, performs one `list_repos`
    roundtrip and caches the result. Accepts both list-of-dicts and
    dict-wrapped responses (legacy + current wire shapes).
    """
    key = id(mcp)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        resp = mcp.list_repos()
    except Exception as e:  # noqa: BLE001 — tick must survive an MCP hiccup
        logger.warning("config: list_repos failed: %s", e)
        _cache[key] = set()
        return _cache[key]
    if resp is None:
        repos: list[Any] = []
    elif isinstance(resp, dict):
        repos = resp.get("repos", resp.get("workspaces", [])) or []
    else:
        repos = resp
    names = {r["name"] for r in repos if isinstance(r, dict) and isinstance(r.get("name"), str)}
    _cache[key] = names
    return names


def is_known_repo(repo: str, mcp: _RepoLister) -> bool:
    """True iff `repo` (owner/name) is in VK's known-repo list."""
    return repo in known_repos(mcp)
