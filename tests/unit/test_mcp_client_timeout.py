"""Tests for the per-call timeout knob on `vk._mcp_client.VkMcpClient`.

The 2026-05-18 incident showed that `start_workspace` is legitimately
slow under bridge-fed Longhorn load (often >30s, sometimes >2min). Two
layered fixes:

1. The `tick()` per-phase `except Exception` guard catches `TimeoutError`
   so a single slow phase doesn't orphan its siblings — covered by
   `tests/integration/test_bridge_resilience.py::test_tick_continues_
   when_one_phase_times_out`.

2. `VkMcpClient.start_workspace` opts up to a 180s timeout (vs. the 30s
   default that every other tool wrapper inherits). This file pins (2)
   so a future refactor can't quietly bring the default back down.
"""

from __future__ import annotations

import queue
from typing import Any

from vk._mcp_client import VkMcpClient


class _RecordingMcpClient(VkMcpClient):
    """VkMcpClient subclass that records the timeout each `_recv` sees."""

    def __init__(self) -> None:
        # Bypass real __init__ (no subprocess).
        self._msg_id = 0
        self._sent: list[dict[str, Any]] = []
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self.recv_timeouts: list[float] = []

    def _send(self, msg: dict[str, Any]) -> None:
        self._sent.append(msg)

    def _recv(self, timeout: float = 30.0) -> dict[str, Any]:
        self.recv_timeouts.append(timeout)
        return {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "result": {"content": [{"type": "text", "text": "{}"}]},
        }


def test_start_workspace_uses_180s_timeout() -> None:
    """`start_workspace` (the only slow tool) declares its own timeout
    of 180s. Cheap RPC tools inherit the 30s default. An explicit
    `timeout=` override on `call_tool` wins over both defaults."""
    client = _RecordingMcpClient()

    client.start_workspace(name="x", repo_id="uuid-r", executor="CLAUDE_CODE", branch="b")
    assert client.recv_timeouts[-1] == 180.0

    client.get_issue("id-1")
    assert client.recv_timeouts[-1] == 30.0

    client.call_tool("custom", {}, timeout=5.0)
    assert client.recv_timeouts[-1] == 5.0


def test_existing_tool_wrappers_inherit_30s_default() -> None:
    """Pin the "only `start_workspace` opts up" guarantee.

    If any other wrapper started passing a non-default timeout, the
    blast radius of a wedged MCP server would grow. This test fails
    fast if someone tightens `update_issue` to e.g. timeout=60 by
    accident.
    """
    client = _RecordingMcpClient()

    client.update_issue("id-1", status="In progress")
    client.list_issues()
    client.list_workspaces()
    client.list_repos()
    client.link_workspace_issue("ws-1", "card-1")

    # Five wrappers above → five `_recv` calls all at the default.
    last_five = client.recv_timeouts[-5:]
    assert last_five == [30.0, 30.0, 30.0, 30.0, 30.0]
