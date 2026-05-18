"""Tests for vk._mcp_client — B3 acceptance test + ported unit tests.

Ported from agent-images/kali/tests/test_vk_mcp_client.py. The wire
protocol tests are identical; convenience-method tests are adapted for
the new keyword-only interface introduced when moving to the vk package.
"""

from __future__ import annotations

import queue
from typing import Any

import pytest

from vk._mcp_client import VkMcpClient, VkMcpError


def test_mcp_client_importable_from_vk():  # B3
    assert VkMcpClient is not None
    assert issubclass(VkMcpError, Exception)


# --- Test double (subclass that bypasses subprocess I/O) ---


class _FakeVkMcpClient(VkMcpClient):
    """VkMcpClient subclass that replaces subprocess I/O with queues.

    Mirrors `FakeVkMcpClient` in the agent-images source tests: skip the
    real `__init__` so no subprocess is spawned, capture sent messages,
    and serve responses from a pre-loaded queue.
    """

    def __init__(self) -> None:
        # Bypass VkMcpClient.__init__ — no subprocess, no threads.
        self._msg_id = 0
        self._sent: list[dict[str, Any]] = []
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()

    def _send(self, msg: dict[str, Any]) -> None:
        self._sent.append(msg)

    def _recv(self, timeout: float = 0.1) -> dict[str, Any]:
        # Default override: tests never wait on real I/O, so a tight
        # timeout fails fast on missing queue setup. Honors the caller-
        # supplied timeout if non-default, for parity with the parent.
        try:
            return self._responses.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("No response queued")


def _ok(result_text: str, msg_id: int = 1) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {"content": [{"type": "text", "text": result_text}]},
    }


def _err(code: int, message: str, msg_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _client_with(response_text: str = "{}") -> _FakeVkMcpClient:
    c = _FakeVkMcpClient()
    c._responses.put(_ok(response_text))
    return c


# --- call_tool core ---


def test_call_tool_sends_correct_jsonrpc():
    client = _FakeVkMcpClient()
    client._responses.put(_ok('{"ok": true}'))
    client.call_tool("test_tool", {"key": "value"})
    msg = client._sent[0]
    assert msg["jsonrpc"] == "2.0"
    assert msg["method"] == "tools/call"
    assert msg["params"]["name"] == "test_tool"
    assert msg["params"]["arguments"] == {"key": "value"}
    assert "id" in msg


def test_call_tool_parses_json_result():
    client = _client_with('{"items": [1, 2, 3]}')
    assert client.call_tool("list_things", {}) == {"items": [1, 2, 3]}


def test_call_tool_returns_text_when_not_json():
    client = _client_with("plain text result")
    assert client.call_tool("some_tool", {}) == "plain text result"


def test_call_tool_raises_on_error_response():
    client = _FakeVkMcpClient()
    client._responses.put(_err(-32600, "Invalid request"))
    with pytest.raises(VkMcpError, match="Invalid request"):
        client.call_tool("bad_tool", {})


def test_call_tool_increments_id():
    client = _FakeVkMcpClient()
    client._responses.put(_ok("{}", msg_id=1))
    client._responses.put(_ok("{}", msg_id=2))
    client.call_tool("tool_a", {})
    client.call_tool("tool_b", {})
    assert client._sent[0]["id"] == 1
    assert client._sent[1]["id"] == 2


# --- Convenience methods (keyword-only interface) ---


def test_create_issue_keyword_args():
    client = _client_with('{"id": "issue-1"}')
    result = client.create_issue(title="My Issue", description="desc")
    args = client._sent[0]["params"]["arguments"]
    assert args["title"] == "My Issue"
    assert args["description"] == "desc"
    assert result == {"id": "issue-1"}


def test_create_issue_passes_project_id_via_kwargs():
    """Wire-protocol fidelity: project_id is still reachable for callers
    that need it — it just isn't a required positional arg anymore."""
    client = _client_with('{"id": "issue-1"}')
    client.create_issue(title="t", project_id="proj-1")
    args = client._sent[0]["params"]["arguments"]
    assert args["project_id"] == "proj-1"
    assert args["title"] == "t"


def test_update_issue():
    client = _client_with('{"id": "issue-1"}')
    client.update_issue("issue-1", status="done")
    args = client._sent[0]["params"]["arguments"]
    assert args["issue_id"] == "issue-1"
    assert args["status"] == "done"


def test_list_issues_keyword_args():
    client = _client_with('[{"id": "i1"}, {"id": "i2"}]')
    result = client.list_issues(status="open")
    args = client._sent[0]["params"]["arguments"]
    assert args["status"] == "open"
    assert len(result) == 2


def test_start_workspace_keyword_args():
    client = _client_with('{"id": "ws-1"}')
    client.start_workspace(
        name="my-ws", repo="owner/repo", executor="CLAUDE_CODE", branch="vk/gh-1"
    )
    args = client._sent[0]["params"]["arguments"]
    assert args["name"] == "my-ws"
    assert args["executor"] == "CLAUDE_CODE"
    assert args["repositories"] == ["owner/repo"]
    assert args["branch"] == "vk/gh-1"


def test_list_workspaces():
    client = _client_with('[{"id": "ws-1"}]')
    result = client.list_workspaces(status="running")
    args = client._sent[0]["params"]["arguments"]
    assert args["status"] == "running"
    assert len(result) == 1


def test_list_repos():
    client = _client_with('[{"name": "repo-a"}]')
    result = client.list_repos()
    assert client._sent[0]["params"]["name"] == "list_repos"
    assert len(result) == 1


def test_link_workspace_issue():
    client = _client_with('{"linked": true}')
    client.link_workspace_issue("ws-1", "issue-1")
    args = client._sent[0]["params"]["arguments"]
    assert args["workspace_id"] == "ws-1"
    assert args["issue_id"] == "issue-1"


def test_get_issue():
    client = _client_with('{"id": "issue-1", "title": "Test"}')
    result = client.get_issue("issue-1")
    args = client._sent[0]["params"]["arguments"]
    assert args["issue_id"] == "issue-1"
    assert result["title"] == "Test"


def test_delete_issue():
    """Parity with upstream agent-images surface — the wire protocol
    contract preserves delete_issue even though dispatch doesn't use it."""
    client = _client_with('{"deleted": true}')
    client.delete_issue("issue-1")
    args = client._sent[0]["params"]["arguments"]
    assert client._sent[0]["params"]["name"] == "delete_issue"
    assert args["issue_id"] == "issue-1"


def test_start_workspace_rejects_repositories_kwarg_collision():
    """Block ambiguity: if a caller passes both `repo=` and
    `repositories=` in kwargs, the spread-last semantics would silently
    let kwargs win. Raise instead so the bug surfaces at call site."""
    client = _client_with('{"id": "ws-1"}')
    with pytest.raises(TypeError, match="repositories list is built internally"):
        client.start_workspace(
            name="my-ws",
            repo="owner/repo",
            executor="CLAUDE_CODE",
            branch="vk/gh-1",
            repositories=["other/repo"],
        )
