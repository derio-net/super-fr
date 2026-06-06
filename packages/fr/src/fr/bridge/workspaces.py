"""Workspace lifecycle: archive on card-Done, reap orphans, recover orphan cards.

Ported from the legacy `agent-images/kali/scripts/vk-issue-bridge.py`:

- `archive_workspace_for_card` → `archive_for_card`
- `reap_orphan_workspaces`    → `reap_orphans`

I5 adds the inverse — when a VK card exists without a workspace, the
legacy bridge could only log the orphan. Opt-in env flag
`VK_BRIDGE_RECOVER_ORPHAN_CARDS=1` recreates the workspace so the card
isn't stuck silently.

The MCP surface is duck-typed via two Protocols so both
`vk._mcp_client.VkMcpClient` and `tests.unit.fakes.FakeMcpClient`
satisfy them without inheritance:

- `MCPArchiver` — narrow: just `list_workspaces` + `update_workspace`,
  for the `archive_for_card` primitive that `pr_state.tick` cascades to.
- `MCPWorkspaceClient(MCPArchiver)` — full lifecycle surface adding
  `list_issues`, `get_issue`, `start_workspace`, `link_workspace_issue`
  for `reap_orphans` and `recover_orphan_card`.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Protocol

__all__ = ["archive_for_card", "reap_orphans", "recover_orphan_card"]

logger = logging.getLogger(__name__)


_BRIDGE_WS_NAME_RE = re.compile(r"^(?P<sid>\S+)\s*->\s*gh#(?P<num>\d+)\s*$")


class MCPArchiver(Protocol):
    """Minimal surface for `archive_for_card`.

    A narrow Protocol so callers that only need the archive primitive
    (e.g. `fr.bridge.pr_state.tick`) don't have to satisfy the larger
    `MCPWorkspaceClient` surface.
    """

    def list_workspaces(self, **kwargs: Any) -> Any: ...

    def update_workspace(self, ws_id: str, **changes: Any) -> Any: ...


class MCPWorkspaceClient(MCPArchiver, Protocol):
    """Full workspace-lifecycle surface."""

    def list_issues(self, **kwargs: Any) -> Any: ...

    def get_issue(self, card_id: str) -> Any: ...

    def list_repos(self) -> Any: ...

    def start_workspace(
        self,
        *,
        name: str,
        repo_id: str,
        executor: str,
        branch: str,
        **kwargs: Any,
    ) -> Any: ...

    def link_workspace_issue(self, ws_id: str, card_id: str) -> Any: ...


def _normalize_workspaces(resp: Any) -> list[dict[str, Any]]:
    """Accept both wire shape `{"workspaces": [...]}` and bare list."""
    if isinstance(resp, dict):
        items = resp.get("workspaces", [])
    elif isinstance(resp, list):
        items = resp
    else:
        return []
    return [w for w in items if isinstance(w, dict)]


def _normalize_issues(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, dict):
        items = resp.get("issues", [])
    elif isinstance(resp, list):
        items = resp
    else:
        return []
    return [c for c in items if isinstance(c, dict)]


def archive_for_card(mcp: MCPArchiver, simple_id: str) -> bool:
    """Archive the workspace whose name starts with f'{simple_id} ->'.

    Returns True iff a workspace was archived. Empty / placeholder
    `simple_id` is a silent no-op. Per-workspace archive failures are
    logged but don't abort — the card has already transitioned to Done,
    so the cleanup is best-effort.
    """
    if not simple_id or simple_id == "?":
        return False
    try:
        resp = mcp.list_workspaces(archived=False, limit=200)
    except Exception as e:  # noqa: BLE001 — non-fatal, see docstring
        logger.warning("workspaces: list_workspaces failed for %s: %s", simple_id, e)
        return False
    prefix = f"{simple_id} ->"
    archived_any = False
    for w in _normalize_workspaces(resp):
        name = w.get("name") or ""
        if not name.startswith(prefix):
            continue
        ws_id = w.get("id")
        if not ws_id:
            continue
        try:
            mcp.update_workspace(ws_id, archived=True)
            archived_any = True
            logger.info("workspaces: archived %s for card %s", ws_id, simple_id)
        except Exception as e:  # noqa: BLE001 — non-fatal
            logger.warning("workspaces: archive %s failed: %s", ws_id, e)
    return archived_any


def reap_orphans(
    mcp: MCPWorkspaceClient,
    pinned: set[str] | None = None,
    *,
    project_id: str | None = None,
) -> int:
    """Archive bridge-created workspaces whose card is Done or missing.

    Only workspaces matching the `<simple_id> -> gh#<n>` naming
    convention are candidates. Workspaces whose name is in `pinned`
    (or that carry `pinned=True` in their MCP payload) are skipped.

    `project_id` is forwarded to `list_issues` so the card-status
    lookup only considers cards in the bridge's own VK project. The
    legacy bridge hard-coded `VK_DERIO_OPS_PROJECT` here; we accept it
    as an explicit kwarg so Phase 5 can thread it from config. When
    unset, the MCP server's session-default scope applies — fine for
    deployments with a single project, but risky in multi-project VKs.

    Returns count of workspaces archived.
    """
    pinned_names = pinned or set()
    try:
        ws_resp = mcp.list_workspaces(archived=False, limit=200)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: reap list_workspaces failed: %s", e)
        return 0
    workspaces = _normalize_workspaces(ws_resp)
    if not workspaces:
        return 0

    issues_kwargs: dict[str, Any] = {"limit": 500}
    if project_id is not None:
        issues_kwargs["project_id"] = project_id
    try:
        cards_resp = mcp.list_issues(**issues_kwargs)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: reap list_issues failed: %s", e)
        return 0

    card_status: dict[str, str] = {}
    for c in _normalize_issues(cards_resp):
        sid = c.get("simple_id")
        if sid is not None:
            card_status[str(sid)] = str(c.get("status", ""))

    archived = 0
    for w in workspaces:
        if w.get("pinned"):
            continue
        name = w.get("name") or ""
        if name in pinned_names:
            continue
        m = _BRIDGE_WS_NAME_RE.match(name)
        if not m:
            continue
        sid = m.group("sid")
        issue_num = m.group("num")
        status = card_status.get(sid)
        if status is not None and status != "Done":
            continue
        ws_id = w.get("id")
        if not ws_id:
            continue
        try:
            mcp.update_workspace(ws_id, archived=True)
            archived += 1
            reason = "no card" if status is None else "card Done"
            logger.info(
                "workspaces: reaped %s (sid=%s, gh#%s, %s)",
                ws_id,
                sid,
                issue_num,
                reason,
            )
        except Exception as e:  # noqa: BLE001 — non-fatal
            logger.warning("workspaces: reap %s failed: %s", ws_id, e)
    return archived


def recover_orphan_card(
    mcp: MCPWorkspaceClient,
    card_id: str,
    simple_id: str,
) -> str | None:
    """Recreate a workspace for a card that has none.

    Opt-in via `VK_BRIDGE_RECOVER_ORPHAN_CARDS=1`. With the flag unset,
    the call logs a warning so the orphan is at least visible in the
    cron log — matching the spec I5 "leaves the card alone but logs"
    branch.

    The new workspace name follows the bridge convention so the next
    `reap_orphans` tick can recognize it. The card's title (set during
    dispatch as `gh#<N>: [<owner/repo>]`) carries the GH Issue number
    and repo; we parse them out to drive the workspace branch + repo.

    Returns the new workspace id, or None if the flag is off or
    recovery wasn't possible. Idempotent: if a workspace already exists
    matching the `<simple_id> ->` prefix, the existing id is returned
    rather than creating a duplicate (defends against racing recover
    calls and against transient orphan-detection false positives).
    """
    # Same sentinel guard as `archive_for_card` — a "?" simple_id would
    # produce a workspace literally named "? -> gh#100" which would then
    # confuse `reap_orphans` matching.
    if not simple_id or simple_id == "?":
        logger.warning(
            "workspaces: recover refused for placeholder sid=%r (card=%s)",
            simple_id,
            card_id,
        )
        return None
    if os.environ.get("VK_BRIDGE_RECOVER_ORPHAN_CARDS") != "1":
        logger.warning(
            "workspaces: card without workspace (card=%s sid=%s); "
            "set VK_BRIDGE_RECOVER_ORPHAN_CARDS=1 to recreate",
            card_id,
            simple_id,
        )
        return None

    # Idempotency: bail with the existing id if a workspace already
    # exists for this simple_id. The legacy bridge had no inverse-reap
    # path, so this is a brand-new race surface — guard it.
    try:
        ws_resp = mcp.list_workspaces(archived=False, limit=200)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: recover list_workspaces failed: %s", e)
        return None
    prefix = f"{simple_id} ->"
    for w in _normalize_workspaces(ws_resp):
        name = w.get("name") or ""
        if not name.startswith(prefix):
            continue
        existing_id = w.get("id")
        if isinstance(existing_id, str) and existing_id:
            logger.info(
                "workspaces: recover found existing %s for sid=%s; skipping recreate",
                existing_id,
                simple_id,
            )
            # Re-link to be safe — the orphan symptom is "card has no
            # workspace", which could mean the workspace exists but the
            # link is broken. link_workspace_issue is idempotent on the
            # MCP server side.
            try:
                mcp.link_workspace_issue(existing_id, card_id)
            except Exception as e:  # noqa: BLE001 — non-fatal
                logger.warning(
                    "workspaces: recover re-link %s ↔ %s failed: %s",
                    existing_id,
                    card_id,
                    e,
                )
            return existing_id

    try:
        card = mcp.get_issue(card_id)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: recover get_issue(%s) failed: %s", card_id, e)
        return None
    if not isinstance(card, dict):
        logger.warning("workspaces: recover got non-dict card for %s; bailing", card_id)
        return None
    # VK's `get_issue` returns `{"issue": {...}}` (wrapped). Unwrap to the
    # inner record so `.get("title")` / `.get("simple_id")` work.
    if "issue" in card and isinstance(card["issue"], dict):
        card = card["issue"]

    title = card.get("title") or ""
    m = re.search(r"gh#(\d+):\s*\[([\w./-]+)\]", title)
    if not m:
        logger.warning(
            "workspaces: recover can't parse card title %r for sid %s; bailing",
            title,
            simple_id,
        )
        return None
    issue_num = m.group(1)
    repo = m.group(2)

    # VK indexes repos by SHORT name (no `owner/`); resolve here so the
    # start_workspace call carries the canonical repo_id Uuid. If VK
    # has no entry for this repo's short name the recovery bails cleanly
    # — the next operator action will see the orphan in the metrics.
    from fr.bridge import config as _config

    repo_id = _config.repo_id_for(repo, mcp)
    if repo_id is None:
        logger.warning(
            "workspaces: recover skip — VK has no repo registered for %r; card %s left orphan",
            repo,
            card_id,
        )
        return None

    try:
        ws = mcp.start_workspace(
            name=f"{simple_id} -> gh#{issue_num}",
            repo_id=repo_id,
            executor="CLAUDE_CODE",
            branch=f"vk/gh-{issue_num}",
        )
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: recover start_workspace failed: %s", e)
        return None
    if not isinstance(ws, dict):
        logger.warning("workspaces: recover got non-dict workspace; bailing")
        return None
    # VK's start_workspace returns `{"workspace_id": "<uuid>"}` (NOT `id`).
    # Accept `id` as a forward-compat fallback in case the wire shape
    # changes; both pre-fix tests and the FakeMcpClient happened to use
    # `id`, so the legacy form stays valid even though VK doesn't emit it.
    ws_id = ws.get("workspace_id") or ws.get("id")
    if not isinstance(ws_id, str) or not ws_id:
        logger.warning("workspaces: recover workspace missing id; bailing")
        return None

    try:
        mcp.link_workspace_issue(ws_id, card_id)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("workspaces: recover link_workspace_issue failed: %s", e)
        return None

    logger.info("workspaces: recovered orphan card %s with workspace %s", card_id, ws_id)
    return ws_id
