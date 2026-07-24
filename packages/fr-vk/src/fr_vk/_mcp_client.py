"""MCP JSON-RPC client for VibeKanban.

Spawns `vibe-kanban-mcp --mode global` (or falls back to
`npx -y vibe-kanban@latest --mcp`) as a subprocess and communicates
via JSON-RPC 2.0 over stdin/stdout.

Moved from agent-images/kali/scripts/vk_mcp_client.py. The wire
protocol is unchanged; only the Python-level interface is adapted
to use keyword-only args that match fr_vk.dispatch's calling
convention.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Per-call read deadline (seconds), uniform for every call including the
# init handshake (issue #404). `start_workspace` states it explicitly as
# documentation of the known-slow call; everything else references this.
DEFAULT_TIMEOUT = 180.0


class VkMcpError(Exception):
    """Raised when the MCP server returns a JSON-RPC error response."""


class VkMcpClient:
    """MCP client that talks JSON-RPC 2.0 to the VibeKanban MCP server."""

    DEFAULT_COMMAND = ["vibe-kanban-mcp", "--mode", "global"]
    FALLBACK_COMMAND = ["npx", "-y", "vibe-kanban@latest", "--mcp"]

    @classmethod
    def _resolve_command(cls) -> list[str]:
        """Use local binary if available, fall back to npx."""
        if shutil.which(cls.DEFAULT_COMMAND[0]):
            return cls.DEFAULT_COMMAND
        return cls.FALLBACK_COMMAND

    def __init__(self, command: list[str] | None = None):
        self._msg_id = 0
        cmd = command or self._resolve_command()
        env = {**os.environ}
        if "VIBE_BACKEND_URL" not in env:
            env["VIBE_BACKEND_URL"] = "http://localhost:8081"
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self._recv_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self._initialize()

    def _read_loop(self) -> None:
        """Read JSON-RPC messages from subprocess stdout into a queue."""
        assert self._process.stdout is not None
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                self._recv_queue.put(msg)
            except json.JSONDecodeError:
                continue

    def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the subprocess stdin."""
        assert self._process.stdin is not None
        data = json.dumps(msg) + "\n"
        self._process.stdin.write(data.encode())
        self._process.stdin.flush()

    def _recv(self, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Receive a JSON-RPC message from the subprocess stdout."""
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"No response from MCP server within {timeout}s")

    def _recv_matching(self, msg_id: int, timeout: float) -> dict[str, Any]:
        """Receive the message whose `id` matches `msg_id`, within `timeout`.

        Anything else is discarded with a warning: a stale response from a
        previously timed-out call, or a server-initiated notification (no
        `id`). Ids are allocated monotonically from `self._msg_id`, so a
        mismatch is always stale/foreign — never "not yet sent".

        Without this, a late reply left in the queue by a timed-out call is
        misattributed to the *next* call, corrupting every response that
        follows (issue #404).
        """
        deadline = time.monotonic() + timeout
        remaining = timeout
        while remaining > 0:
            try:
                msg = self._recv(timeout=remaining)
            except TimeoutError:
                # Re-raise below with the awaited id and the OVERALL budget —
                # _recv's own message would report only the remaining slice.
                break
            if msg.get("id") == msg_id:
                return msg
            if msg.get("id") is None and "error" in msg:
                # JSON-RPC 2.0: a server that can't parse/associate the
                # request answers `id: null` + error. Surface it (call_tool
                # raises VkMcpError) instead of draining it into a timeout.
                return msg
            logger.warning(
                "vk-mcp: discarding stale/foreign message id=%r (awaiting id=%s)",
                msg.get("id"),
                msg_id,
            )
            remaining = deadline - time.monotonic()
        raise TimeoutError(f"No response with id={msg_id} from MCP server within {timeout}s")

    def _initialize(self) -> None:
        """Perform MCP handshake: initialize + notifications/initialized."""
        self._msg_id += 1
        msg_id = self._msg_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "vk-mcp-client", "version": "0.1.0"},
                },
            }
        )
        self._recv_matching(msg_id, DEFAULT_TIMEOUT)
        self._send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        """Call an MCP tool and return the parsed result.

        Returns parsed JSON if the result text is valid JSON,
        otherwise returns the raw text string.

        Raises VkMcpError if the server returns an error response.

        `timeout` is the per-call read deadline (in seconds), 180s for
        every call (issue #404). The old 30s fail-fast default is
        retired: a client-side timeout only abandons the *client's* half
        of the request — the server-side future is dropped mid-flight,
        the spawned child is never reaped, and each abandoned
        `start_workspace` leaks a `VK_MAX_CONCURRENT_EXECUTIONS` permit.
        Those leaks are cumulative and terminal, so the fail-fast
        deadline caused the executor wedge it was meant to surface.
        `start_workspace` keeps an explicit 180.0 as documentation of
        the known-slow call; an explicit `timeout=` here still wins.
        """
        self._msg_id += 1
        msg_id = self._msg_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        response = self._recv_matching(msg_id, timeout)

        if "error" in response:
            err = response["error"]
            raise VkMcpError(f"MCP error {err['code']}: {err['message']}")

        content = response.get("result", {}).get("content", [])
        text = ""
        for item in content:
            if item.get("type") == "text":
                text = item["text"]
                break

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # --- High-level convenience methods ---
    # Thin wrappers around call_tool. Signatures are keyword-only so callers
    # (fr_vk.dispatch + FakeMcpClient in tests) share one calling
    # convention. The wire payload still names the same JSON-RPC tools the
    # VK MCP server has always used; all unknown kwargs flow through so the
    # full upstream surface (e.g. project_id) remains reachable.

    def create_issue(self, *, title: str, **kwargs: Any) -> Any:
        return self.call_tool("create_issue", {"title": title, **kwargs})

    def update_issue(self, issue_id: str, **kwargs: Any) -> Any:
        return self.call_tool("update_issue", {"issue_id": issue_id, **kwargs})

    def get_issue(self, issue_id: str) -> Any:
        return self.call_tool("get_issue", {"issue_id": issue_id})

    def delete_issue(self, issue_id: str) -> Any:
        return self.call_tool("delete_issue", {"issue_id": issue_id})

    def list_issues(self, **kwargs: Any) -> Any:
        return self.call_tool("list_issues", {**kwargs})

    def start_workspace(
        self,
        *,
        name: str,
        repo_id: str,
        executor: str,
        branch: str,
        **kwargs: Any,
    ) -> Any:
        # The VK MCP server expects a list of `{repo_id, branch}` objects at
        # the `repositories` key (see `vibe-kanban-mcp` task_attempts.rs:
        # `repositories: Vec<McpWorkspaceRepoInput>` with fields
        # `repo_id: Uuid, branch: String`). VK indexes repos by `id`; the
        # caller resolves short name → repo_id via
        # `fr_vk.config.repo_id_for` first. Branch lives inside the
        # repo entry — there is no top-level `branch` field. Block
        # `repositories=` in kwargs so a stray override can't slip past
        # spread-last semantics.
        if "repositories" in kwargs:
            raise TypeError(
                "start_workspace: pass repo_id='<uuid>' (singular); "
                "the repositories list is built internally"
            )
        return self.call_tool(
            "start_workspace",
            {
                "name": name,
                "executor": executor,
                "repositories": [{"repo_id": repo_id, "branch": branch}],
                **kwargs,
            },
            timeout=180.0,
        )

    def list_workspaces(self, **kwargs: Any) -> Any:
        return self.call_tool("list_workspaces", {**kwargs})

    def update_workspace(self, workspace_id: str, **kwargs: Any) -> Any:
        return self.call_tool("update_workspace", {"workspace_id": workspace_id, **kwargs})

    def list_repos(self) -> Any:
        return self.call_tool("list_repos", {})

    def link_workspace_issue(self, workspace_id: str, issue_id: str) -> Any:
        return self.call_tool(
            "link_workspace_issue",
            {
                "workspace_id": workspace_id,
                "issue_id": issue_id,
            },
        )

    def close(self) -> None:
        """Terminate the subprocess."""
        if hasattr(self, "_process") and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)
