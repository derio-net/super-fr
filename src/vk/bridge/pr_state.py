"""Card status transitions driven by PR observations.

Ported from `poll_pr_status` (legacy bridge). The PR observation source
is decoupled: callers pass `pr_observations` as a `{card_id: "open" |
"merged"}` mapping built upstream (Phase 5 wires the real `vk.observe`
call). This keeps the transition logic unit-testable without spinning
up a GhClient.

Transitions:
  - In progress + PR open (non-draft) → In review
  - In review   + PR merged           → Done
      + archive the linked workspace
      + close the linked GH Issue (belt-and-braces for PR bodies missing
        `Fixes #N`; gh's native auto-close would have already fired
        otherwise)
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Callable
from typing import Any, Protocol

from vk.bridge.workspaces import MCPArchiver, archive_for_card

__all__ = ["tick"]

logger = logging.getLogger(__name__)


class MCPCardClient(MCPArchiver, Protocol):
    """Structural MCP surface required by `tick`.

    Extends `MCPArchiver` so a single object satisfies both `tick`'s
    surface and the `archive_for_card` cascade — keeps the two
    Protocols in lockstep with one place to edit.
    """

    def list_issues(self, **kwargs: Any) -> Any: ...

    def update_issue(self, card_id: str, **changes: Any) -> Any: ...


_GH_REPO_FROM_URL_RE = re.compile(r"https?://github\.com/([\w.-]+/[\w.-]+)/(?:pull|issues)/\d+")
_GH_ISSUE_NUM_FROM_TITLE_RE = re.compile(r"gh#(\d+)")


def _normalize_issues(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, dict):
        items = resp.get("issues", [])
    elif isinstance(resp, list):
        items = resp
    else:
        return []
    return [c for c in items if isinstance(c, dict)]


def _default_close_gh_issue(repo: str, issue_number: str) -> None:
    """Run `gh issue close <num> --repo <repo>`. Non-fatal on failure.

    Already-closed issues are a no-op (gh reports the state and exits
    non-zero with 'already closed' in stderr).
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "close", issue_number, "--repo", repo],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("pr_state: close %s#%s failed: %s", repo, issue_number, e)
        return
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "already closed" in stderr.lower():
            return
        # Truncate at 512 (was 160) so auth / rate-limit errors with
        # longer stderr survive the WARNING line. Full text always
        # available at DEBUG.
        logger.debug("pr_state: close %s#%s full stderr: %s", repo, issue_number, stderr)
        logger.warning(
            "pr_state: close %s#%s failed (rc=%s): %s",
            repo,
            issue_number,
            result.returncode,
            stderr[:512],
        )
        return
    logger.info("pr_state: closed %s#%s", repo, issue_number)


def _close_linked_gh_issue(
    title: str,
    pr_url: str | None,
    closer: Callable[[str, str], None],
) -> None:
    """Resolve owner/repo from `pr_url` and Issue number from `title`, then close."""
    if not pr_url or not title:
        return
    m_repo = _GH_REPO_FROM_URL_RE.match(pr_url)
    m_num = _GH_ISSUE_NUM_FROM_TITLE_RE.search(title)
    if not m_repo or not m_num:
        return
    closer(m_repo.group(1), m_num.group(1))


def tick(
    mcp: MCPCardClient,
    pr_observations: dict[str, str],
    *,
    close_gh_issue: Callable[[str, str], None] | None = None,
    project_id: str | None = None,
) -> int:
    """Transition cards based on their linked PR's observed status.

    `pr_observations` is a `{card_id: "open" | "merged" | ...}` map.
    Cards without an entry in the map are left untouched. Observation
    values outside the recognized set (e.g. "draft", "closed", "") are
    ignored — only `"open"` (→ In review) and `"merged"` (→ Done) cause
    a transition.

    `close_gh_issue(repo, issue_number)` is the side-channel that runs
    the belt-and-braces `gh issue close` for the In-review → Done
    cascade. Injectable for unit tests; defaults to a `gh` subprocess
    call.

    `project_id` is forwarded to `list_issues` so the sweep only
    considers cards in the bridge's own VK project. The legacy bridge
    hard-coded `VK_DERIO_OPS_PROJECT`; we accept it as an explicit
    kwarg so Phase 5 can thread it from config. When unset, the MCP
    server's session-default scope applies.

    Returns the count of cards that transitioned. Per-card failures are
    logged but do not abort the sweep.
    """
    closer = close_gh_issue if close_gh_issue is not None else _default_close_gh_issue
    transitioned = 0

    for current_status in ("In progress", "In review"):
        list_kwargs: dict[str, Any] = {"status": current_status}
        if project_id is not None:
            list_kwargs["project_id"] = project_id
        try:
            resp = mcp.list_issues(**list_kwargs)
        except Exception as e:  # noqa: BLE001 — non-fatal
            logger.warning("pr_state: list_issues(%s) failed: %s", current_status, e)
            continue

        for card in _normalize_issues(resp):
            # Defensive: the MCP server filter is the source of truth, but we
            # re-check `status` here so a server that ignores the filter (or
            # an in-memory fake) can't push a card through a transition that
            # doesn't match its actual current state.
            if str(card.get("status", "")) != current_status:
                continue
            card_id = card.get("id")
            if not isinstance(card_id, str) or not card_id:
                continue
            simple_id = str(card.get("simple_id", "?"))
            title = str(card.get("title") or "")
            pr_url = card.get("latest_pr_url")
            pr_status = pr_observations.get(card_id)
            if not pr_status:
                continue

            new_status: str | None = None
            if current_status == "In progress" and pr_status == "open":
                new_status = "In review"
            elif current_status == "In review" and pr_status == "merged":
                new_status = "Done"
            if new_status is None:
                continue

            try:
                mcp.update_issue(card_id, status=new_status)
            except Exception as e:  # noqa: BLE001 — non-fatal
                logger.warning(
                    "pr_state: update_issue(%s, %s) failed: %s",
                    card_id,
                    new_status,
                    e,
                )
                continue
            transitioned += 1
            logger.info(
                "pr_state: %s: %s → %s (PR %s)",
                simple_id,
                current_status,
                new_status,
                pr_status,
            )

            if new_status == "Done":
                archive_for_card(mcp, simple_id)
                _close_linked_gh_issue(
                    title,
                    pr_url if isinstance(pr_url, str) else None,
                    closer,
                )

    return transitioned
