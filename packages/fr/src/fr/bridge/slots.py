"""Slot-budget accounting for the live bridge tick loop.

`MAX_CONCURRENT` (env-overridable; default 8) caps the number of
non-archived VK workspaces. `count_active_ws(mcp)` queries the current
count via MCP. `fr.bridge.tick` subtracts these to derive available
slots and stops dispatching when the budget is exhausted.

Both helpers are isolated here so tests can monkeypatch `count_active_ws`
at the module boundary without having to seed `FakeMcpClient.workspaces`
with realistic objects.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

__all__ = ["count_active_ws", "max_concurrent"]


class _WorkspaceLister(Protocol):
    def list_workspaces(self, **kwargs: Any) -> Any: ...


def count_active_ws(mcp: _WorkspaceLister) -> int:
    """Count non-archived workspaces. Slot budget = max_concurrent() - this.

    Accepts both shapes the VK MCP server has returned over time:
    a bare list of workspace dicts, or a dict wrapping them under
    `"workspaces"`. A missing/None response counts as zero — the
    bridge would rather over-dispatch by one slot than freeze on
    a transient MCP hiccup.
    """
    resp = mcp.list_workspaces()
    if resp is None:
        return 0
    workspaces = resp.get("workspaces", []) if isinstance(resp, dict) else resp
    return sum(1 for ws in workspaces if not ws.get("archived"))


def max_concurrent() -> int:
    """Slot ceiling. Default 8; override via `MAX_CONCURRENT` env."""
    return int(os.environ.get("MAX_CONCURRENT", "8"))
