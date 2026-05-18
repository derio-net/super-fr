"""Canonical phase-dispatch implementation.

The ONE place that creates a VK card + workspace for a `vk-ready` phase.
Both `vk.bridge.tick` and any future direct callers (e.g. a CLI verb)
funnel through `dispatch_phase` so the create_issue + update_issue +
list_repos + start_workspace + link_workspace_issue sequence cannot
drift between implementations. Test B2 enforces this is the only such
sequence in `src/`.

Wire payload shape:
  - `create_issue`: title = "gh#N: [owner/repo]", description = newline-
    joined (plan, "Phase N/total", phase title, tracking_issue URL).
  - `update_issue`: status = "In progress".
  - `start_workspace`: name = "{plan}-P{N} -> gh#{N}", repo from the
    phase's tracking_issue (so cross-repo phases route to their dest),
    executor = CLAUDE_CODE, branch = "vk/gh-{N}".
  - `link_workspace_issue`: ties the workspace to the card.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from vk._mcp_client import VkMcpError
from vk._urls import parse_issue_url
from vk.parser import Plan
from vk.types import PhaseDoc

__all__ = ["DispatchResult", "MCPDispatch", "dispatch_phase"]

logger = logging.getLogger(__name__)


class MCPDispatch(Protocol):
    """Structural surface `dispatch_phase` requires from its MCP client.

    Both `vk._mcp_client.VkMcpClient` (production) and
    `tests.unit.fakes.FakeMcpClient` (tests) satisfy this Protocol by
    duck-typing — neither has to import or inherit from it. The Protocol
    exists so mypy can type-check the dispatch implementation itself
    against a checkable contract, rather than leaving `mcp: Any` and
    letting typos through.
    """

    def create_issue(self, *, title: str, description: str, **kwargs: Any) -> Any: ...

    def update_issue(self, issue_id: str, **kwargs: Any) -> Any: ...

    def list_repos(self) -> Any: ...

    def start_workspace(
        self,
        *,
        name: str,
        repo: str,
        executor: str,
        branch: str,
        **kwargs: Any,
    ) -> Any: ...

    def link_workspace_issue(self, workspace_id: str, issue_id: str) -> Any: ...


@dataclass(frozen=True)
class DispatchResult:
    card_id: str
    workspace_id: str | None


def _warmup_repo_listing(mcp: MCPDispatch, repo: str) -> None:
    """Issue the mandated `list_repos` call before `start_workspace`.

    The dispatch contract requires this call (see test B2 + the legacy
    `sync_issue` behavior it replaces). We use the result as a soft
    sanity check: if VK reports a known set of repos and the target
    isn't in it, we log a warning and proceed. We don't hard-fail —
    cross-repo dispatch can target repos not yet known to VK's local
    project list, and the subsequent `start_workspace` call surfaces
    a clearer server-side error than us swallowing here.

    A `list_repos` failure is logged at warning level but not raised:
    the downstream `start_workspace` call will fail with the actionable
    error message; suppressing it here would lose that context.
    """
    try:
        repos = mcp.list_repos()
    except Exception as e:  # noqa: BLE001 — see docstring
        logger.warning("dispatch: list_repos failed (%s); proceeding", e)
        return
    known: set[str] = {
        name
        for entry in (repos or [])
        if isinstance(entry, dict) and isinstance((name := entry.get("name")), str)
    }
    if repo not in known:
        logger.warning(
            "dispatch: repo %r not in list_repos result %s; "
            "start_workspace will surface a server-side error if the repo is unknown",
            repo,
            sorted(known),
        )


def _expect_id(value: Any, op: str) -> str:
    """Coerce an MCP result to its id-string, or raise with context."""
    if isinstance(value, dict):
        candidate = value.get("id")
        if isinstance(candidate, str) and candidate:
            return candidate
    raise VkMcpError(f"{op} returned unexpected shape: {value!r}")


def dispatch_phase(plan: Plan, phase: PhaseDoc, mcp: MCPDispatch) -> DispatchResult:
    """Create VK card + workspace for a vk-ready phase.

    Raises:
        ValueError: if the phase has no `tracking_issue` (dispatch
            requires an anchoring GH Issue).
        VkMcpError: if the MCP server returns an unexpected payload
            shape (no `id` on create_issue / start_workspace).
        Any: propagates exceptions from MCP calls (the caller — typically
            `vk.bridge.tick` — is responsible for swallowing one-phase
            failures so they don't kill the whole tick).
    """
    tracking = phase.phase.tracking_issue
    if not tracking:
        raise ValueError(
            f"phase {phase.phase.number} has no tracking_issue — "
            "dispatch requires a GH Issue to anchor the card"
        )
    repo, issue_n = parse_issue_url(tracking)

    title = f"gh#{issue_n}: [{repo}]"
    description = "\n".join(
        [
            plan.meta.plan,
            f"Phase {phase.phase.number}/{len(plan.phases)}",
            phase.phase.title,
            tracking,
        ]
    )

    card = mcp.create_issue(title=title, description=description)
    card_id = _expect_id(card, "create_issue")
    mcp.update_issue(card_id, status="In progress")

    _warmup_repo_listing(mcp, repo)
    ws = mcp.start_workspace(
        name=f"{plan.meta.plan}-P{phase.phase.number} -> gh#{issue_n}",
        repo=repo,
        executor="CLAUDE_CODE",
        branch=f"vk/gh-{issue_n}",
    )
    ws_id = _expect_id(ws, "start_workspace")

    mcp.link_workspace_issue(ws_id, card_id)

    # Phase 4 will optionally invoke VK_LIFECYCLE_HOOK_SCRIPT here. The
    # hook point is intentionally a no-op for Phase 2.

    return DispatchResult(card_id=card_id, workspace_id=ws_id)
