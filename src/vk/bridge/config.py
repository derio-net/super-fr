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

Wire shape (real `vibe-kanban-mcp`):
  list_repos → `{"repos": [{"id": <Uuid>, "name": <short>}], "count": N}`

VK identifies repos by SHORT name (no `owner/`), with the canonical
handle being the `id` (a Uuid). The bridge receives `owner/name` strings
from `tracking_issue` URLs, so the comparison strips the `owner/` prefix
before checking VK. The `id` is exposed via `repo_id_for` for the
dispatch call (`start_workspace.repositories[].repo_id`).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

__all__ = ["clear_repo_cache", "is_known_repo", "known_repos", "repo_id_for"]

logger = logging.getLogger(__name__)


class _RepoLister(Protocol):
    def list_repos(self) -> Any: ...


# Single-slot cache: `None` means "not yet queried this tick".
# Earlier revisions used `dict[int, set[str]]` keyed on `id(mcp)`, but
# `id()` is reused after GC and the bridge only ever holds one MCP
# client per process anyway — the dict added a collision surface for
# tests that recycled FakeMcpClient instances without paying for any
# real flexibility.
_cache: dict[str, str] | None = None


def clear_repo_cache() -> None:
    """Drop the cached `list_repos` snapshot. The daemon (and tick)
    call this once per iteration so config drift propagates."""
    global _cache
    _cache = None


def known_repos(mcp: _RepoLister) -> dict[str, str]:
    """Return the cached `{short_name: repo_id}` map known to VK.

    On first call after `clear_repo_cache()` (or process start),
    performs one `list_repos` roundtrip and caches the result.
    Accepts both list-of-dicts and dict-wrapped responses (legacy +
    current wire shapes). A `list_repos` failure is logged and
    cached as the empty mapping — the bridge then refuses to
    dispatch until the next tick clears and retries.

    Entries missing either `id` or `name` are skipped (a malformed
    VK response shouldn't crash the tick — the affected repo will
    just look "unknown" until the next list_repos comes back
    well-formed).
    """
    global _cache
    if _cache is not None:
        return _cache
    try:
        resp = mcp.list_repos()
    except Exception as e:  # noqa: BLE001 — tick must survive an MCP hiccup
        logger.warning("config: list_repos failed: %s", e)
        _cache = {}
        return _cache
    if resp is None:
        repos: list[Any] = []
    elif isinstance(resp, dict):
        repos = resp.get("repos", resp.get("workspaces", [])) or []
    else:
        repos = resp
    mapping: dict[str, str] = {}
    for r in repos:
        if not isinstance(r, dict):
            continue
        name = r.get("name")
        repo_id = r.get("id")
        if isinstance(name, str) and isinstance(repo_id, str) and name and repo_id:
            mapping[name] = repo_id
    _cache = mapping
    return _cache


def _short_name(repo: str) -> str:
    """`owner/name` → `name`; pass-through if no `/`."""
    return repo.rsplit("/", 1)[-1]


def is_known_repo(repo: str, mcp: _RepoLister) -> bool:
    """True iff the SHORT name of `repo` is in VK's known-repo list.

    `repo` may be either `owner/name` (the bridge's canonical form
    parsed from a `tracking_issue` URL) or a bare short name. VK only
    indexes by short name, so the gate compares short-against-short —
    `derio-net/agent-images` matches a VK repo named `agent-images`.
    """
    return _short_name(repo) in known_repos(mcp)


def repo_id_for(repo: str, mcp: _RepoLister) -> str | None:
    """Return the VK `repo_id` (Uuid) for `repo`, or None if unknown.

    `repo` is `owner/name` (or bare short name). The dispatch path
    needs the repo_id to build a `start_workspace.repositories[]`
    entry — VK rejects bare names.
    """
    return known_repos(mcp).get(_short_name(repo))
