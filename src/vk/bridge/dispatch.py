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

from dataclasses import dataclass
from typing import Any

from vk._urls import parse_issue_url
from vk.parser import Plan
from vk.types import PhaseDoc

__all__ = ["DispatchResult", "dispatch_phase"]


@dataclass(frozen=True)
class DispatchResult:
    card_id: str
    workspace_id: str | None


def _resolve_repo(mcp: Any, repo: str) -> str:
    """Resolve `owner/name` to whatever VK MCP's `list_repos` calls it.

    VK returns each repo as a dict with at least a `name` key. We accept
    the first match by name; if the repo isn't in the list we fall back
    to the raw `owner/name` string so the start_workspace call surfaces
    the real failure rather than swallowing it as a KeyError.
    """
    try:
        repos = mcp.list_repos()
    except Exception:
        return repo
    for entry in repos or []:
        if isinstance(entry, dict) and entry.get("name") == repo:
            return repo
    return repo


def dispatch_phase(plan: Plan, phase: PhaseDoc, mcp: Any) -> DispatchResult:
    """Create VK card + workspace for a vk-ready phase.

    `mcp` is typed `Any` so both `vk._mcp_client.VkMcpClient` and
    `tests.unit.fakes.FakeMcpClient` satisfy it structurally without
    forcing a Protocol indirection. The set of methods actually called
    is documented in this module's docstring.
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
    card_id = card["id"] if isinstance(card, dict) else card
    mcp.update_issue(card_id, status="In progress")

    resolved_repo = _resolve_repo(mcp, repo)
    ws = mcp.start_workspace(
        name=f"{plan.meta.plan}-P{phase.phase.number} -> gh#{issue_n}",
        repo=resolved_repo,
        executor="CLAUDE_CODE",
        branch=f"vk/gh-{issue_n}",
    )
    ws_id = ws["id"] if isinstance(ws, dict) else ws

    mcp.link_workspace_issue(ws_id, card_id)

    # Phase 4 will optionally invoke VK_LIFECYCLE_HOOK_SCRIPT here. The
    # hook point is intentionally a no-op for Phase 2.

    return DispatchResult(card_id=card_id, workspace_id=ws_id)
