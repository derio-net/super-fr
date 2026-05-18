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
  - `start_workspace`: name = "{plan}-P{N} -> gh#{N}",
    `repo_id` = the VK Uuid resolved from the SHORT name (`owner/name`
    → `name` → VK `id`) via `vk.bridge.config.repo_id_for`,
    executor = CLAUDE_CODE, branch = "vk/gh-{N}".
  - `link_workspace_issue`: ties the workspace to the card.

VK indexes repos by SHORT name (no `owner/`) with the canonical handle
being the `repo_id` Uuid (see `vibe-kanban-mcp` task_attempts.rs).
The bridge resolves the short name from the `tracking_issue` URL's
`owner/name`, then looks up the repo_id via the cached `list_repos`
snapshot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from vk._mcp_client import VkMcpError
from vk._urls import parse_issue_url
from vk.bridge import config as _config
from vk.bridge.lifecycle import invoke_lifecycle_hook
from vk.parser import Plan
from vk.types import PhaseDoc

__all__ = ["DispatchResult", "MCPDispatch", "build_card_title", "dispatch_phase"]

logger = logging.getLogger(__name__)


def build_card_title(repo: str, issue_n: int) -> str:
    """Canonical card-title format.

    Shared with `vk.bridge.tick` so the pre-dispatch dedup check and the
    post-dispatch create_issue payload cannot drift. Format pinned by
    test D2 — `"gh#{n}: [{owner/repo}]"`.
    """
    return f"gh#{issue_n}: [{repo}]"


class MCPDispatch(Protocol):
    """Structural surface the bridge requires from its MCP client.

    Covers `dispatch_phase` (create_issue / update_issue / list_repos /
    start_workspace / link_workspace_issue) plus the read-only helpers
    `vk.bridge.tick` consults each iteration: `list_workspaces` for the
    slot budget and `list_issues` for the dedup snapshot.

    Both `vk._mcp_client.VkMcpClient` (production) and
    `tests.unit.fakes.FakeMcpClient` (tests) satisfy this Protocol by
    duck-typing — neither has to import or inherit from it. The Protocol
    exists so mypy can type-check the bridge implementation itself
    against a checkable contract, rather than leaving `mcp: Any` and
    letting typos through.
    """

    def create_issue(self, *, title: str, description: str, **kwargs: Any) -> Any: ...

    def update_issue(self, issue_id: str, **kwargs: Any) -> Any: ...

    def list_issues(self, **kwargs: Any) -> Any: ...

    def list_repos(self) -> Any: ...

    def list_workspaces(self, **kwargs: Any) -> Any: ...

    def start_workspace(
        self,
        *,
        name: str,
        repo_id: str,
        executor: str,
        branch: str,
        **kwargs: Any,
    ) -> Any: ...

    def link_workspace_issue(self, workspace_id: str, issue_id: str) -> Any: ...


@dataclass(frozen=True)
class DispatchResult:
    card_id: str
    workspace_id: str | None


def _resolve_repo_id(mcp: MCPDispatch, repo: str) -> str:
    """Issue the mandated `list_repos` call and resolve `repo` → VK repo_id.

    The dispatch contract requires this `list_repos` call (test B2) — kept
    even though `vk.bridge.config.repo_id_for` would cache it, because the
    call site here documents the per-dispatch read for any future caller
    bypassing the tick path. The lookup goes through `vk.bridge.config` so
    the per-tick cache populates whichever entry point sees VK first.

    Raises `VkMcpError` if VK has no repo registered for `repo`'s short
    name — `start_workspace` would 4xx otherwise with an opaque server-
    side error.
    """
    try:
        mcp.list_repos()
    except Exception as e:  # noqa: BLE001 — let _config swallow it consistently
        logger.warning("dispatch: list_repos failed (%s); proceeding", e)
    repo_id = _config.repo_id_for(repo, mcp)
    if repo_id is None:
        known = sorted(_config.known_repos(mcp).keys())
        raise VkMcpError(
            f"dispatch: VK has no repo registered for {repo!r}; "
            f"register the repo in VK first (known short names: {known})"
        )
    return repo_id


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

    title = build_card_title(repo, issue_n)
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

    repo_id = _resolve_repo_id(mcp, repo)
    ws = mcp.start_workspace(
        name=f"{plan.meta.plan}-P{phase.phase.number} -> gh#{issue_n}",
        repo_id=repo_id,
        executor="CLAUDE_CODE",
        branch=f"vk/gh-{issue_n}",
    )
    ws_id = _expect_id(ws, "start_workspace")

    mcp.link_workspace_issue(ws_id, card_id)

    # D5: notify the operator-configured hook that the phase transitioned
    # to in-progress. invoke_lifecycle_hook is fire-and-forget — failures
    # are logged and swallowed so a broken notifier can't undo a card
    # that has already been created.
    invoke_lifecycle_hook(tracking, "in-progress")

    return DispatchResult(card_id=card_id, workspace_id=ws_id)
