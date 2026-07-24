"""Tests for the per-call timeout knob on `vk._mcp_client.VkMcpClient`.

Issue #404 retires the old "cheap calls fail fast at 30s" policy this
file used to pin. Under bridge-fed load a 30s read deadline abandons
in-flight VK requests: the server-side future is dropped mid-flight,
the spawned child is never reaped, and each abandoned `start_workspace`
leaks a `VK_MAX_CONCURRENT_EXECUTIONS` permit. The leak is cumulative
and terminal — once `active == max` on dead executions, every later
spawn queues forever. The fail-fast deadline *caused* the wedge it was
meant to surface.

Policy now (operator decision qa-timeout-policy): a uniform 180s default
for every call, no env knob. `start_workspace` keeps its explicit 180.0
as documentation of the known-slow call. An explicit `timeout=` on
`call_tool` still wins. This file pins that so a future refactor can't
quietly bring the default back down.
"""

from __future__ import annotations

import queue
from typing import Any

from fr_vk._mcp_client import VkMcpClient


class _RecordingMcpClient(VkMcpClient):
    """VkMcpClient subclass that records the timeout each `_recv` sees.

    `call_tool` routes through `_recv_matching`, which re-`_recv`s with
    the *remaining* deadline budget; the FIRST timeout recorded per call
    is the full requested budget, which is what these tests assert on.
    """

    def __init__(self) -> None:
        # Bypass real __init__ (no subprocess).
        self._msg_id = 0
        self._sent: list[dict[str, Any]] = []
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self.recv_timeouts: list[float] = []

    def _send(self, msg: dict[str, Any]) -> None:
        self._sent.append(msg)

    def _recv(self, timeout: float = 180.0) -> dict[str, Any]:
        self.recv_timeouts.append(timeout)
        return {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "result": {"content": [{"type": "text", "text": "{}"}]},
        }


def test_default_timeout_is_180s() -> None:
    """Every tool wrapper inherits the uniform 180s default (#404).

    Each wrapper issues exactly one `_recv` here (the double always
    answers with a matching id), so the recorded list is one entry per
    call.
    """
    client = _RecordingMcpClient()

    client.get_issue("id-1")
    client.update_issue("id-1", status="In progress")
    client.list_issues()
    client.list_workspaces()
    client.list_repos()
    client.link_workspace_issue("ws-1", "card-1")

    # Six wrappers above → six `_recv` calls, all at the new default.
    assert client.recv_timeouts[-6:] == [180.0] * 6


def test_start_workspace_uses_180s_timeout() -> None:
    """`start_workspace` still declares 180.0 explicitly — now equal to
    the default, retained as documentation of the known-slow call."""
    client = _RecordingMcpClient()

    client.start_workspace(name="x", repo_id="uuid-r", executor="CLAUDE_CODE", branch="b")

    assert client.recv_timeouts[0] == 180.0


def test_explicit_call_tool_timeout_wins() -> None:
    """An explicit `timeout=` on `call_tool` overrides the default."""
    client = _RecordingMcpClient()

    client.call_tool("custom", {}, timeout=5.0)

    assert client.recv_timeouts[0] == 5.0
