"""Card status transitions driven by PR observations.

Ported from `poll_pr_status` (legacy bridge). The PR observation source
is decoupled: callers pass `pr_observations` as a `{card_id: "open" |
"merged"}` mapping built upstream (Phase 5 wires the real `vk.observe`
call). This keeps the transition logic unit-testable without spinning
up a GhClient.

Transitions:
  - In progress + PR open (non-draft) → In review
  - In progress + PR merged           → Done   (skip-stage, #290: PR merged
        before In-review was ever observed — reconciles backlog cards)
  - In review   + PR merged           → Done
      + archive the linked workspace
      + close the linked GH Issue (belt-and-braces for PR bodies missing
        `Fixes #N`; gh's native auto-close would have already fired
        otherwise)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlparse

from fr import _hosts, hostclient

from fr_vk import _cardref
from fr_vk.workspaces import MCPArchiver, archive_for_card

__all__ = ["reconcile_done_issues", "tick"]

logger = logging.getLogger(__name__)


class MCPCardClient(MCPArchiver, Protocol):
    """Structural MCP surface required by `tick`.

    Extends `MCPArchiver` so a single object satisfies both `tick`'s
    surface and the `archive_for_card` cascade — keeps the two
    Protocols in lockstep with one place to edit.
    """

    def list_issues(self, **kwargs: Any) -> Any: ...

    def update_issue(self, card_id: str, **changes: Any) -> Any: ...


# Repo (+ optional host) from a PR/issue/MR url — used ONLY as a
# cross-check against the card title's own `[owner/repo]` (a recycled /
# mis-linked card guard), independent of `_cardref`'s title parsing.
# Generalized beyond the original github.com-only pattern to cover all
# three backends' PR-url shapes (gh `/pull/N`, gitea `/pulls/N`, gitlab
# `/-/merge_requests/N`) — see docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §6.
_REPO_FROM_URL_RE = re.compile(
    r"https?://[^/]+/(.+?)(?:/-)?/(?:pull|pulls|issues|merge_requests)/\d+"
)
# Bound the per-tick gh-close burst so a large first-deploy backlog (empty
# seen-set) is amortized across ticks instead of spawning N `gh issue close`
# under one flock — avoids secondary-rate-limit throttle loops.
_MAX_DONE_CLOSES_PER_TICK = 50


def _normalize_issues(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, dict):
        items = resp.get("issues", [])
    elif isinstance(resp, list):
        items = resp
    else:
        return []
    return [c for c in items if isinstance(c, dict)]


def _default_close_gh_issue(repo: str, issue_number: str, backend: str) -> None:
    """Resolve a `GhClient`-shaped adapter for `backend` and call
    `edit_issue_state(..., state="CLOSED")`. Non-fatal on failure.

    Previously shelled out to a raw `gh issue close` subprocess directly,
    bypassing `GhClient` entirely — fixed as part of the multi-backend
    design (see docs/superpowers/specs/
    2026-07-09-multi-backend-git-host-adapters-design.md §6). Each
    adapter's own already-closed-is-a-no-op behavior (or lack thereof)
    is that adapter's concern, not this caller's.

    `backend` is typed `str`, not `fr._hosts.HostBackend`, to match the
    public `closer: Callable[[str, str, str], None]` signature every
    caller (including test doubles) satisfies structurally; it's always
    one of the three literal values in practice (both call sites derive
    it via `fr._hosts.backend_for_hostname`/`fr_vk._cardref.BACKEND_FOR_TAG`).
    """
    client = hostclient.client_for_backend(backend)  # type: ignore[arg-type]
    try:
        client.edit_issue_state(repo, int(issue_number), state="CLOSED")
    except Exception as e:  # noqa: BLE001 — non-fatal, mirrors the old subprocess posture
        logger.warning("pr_state: close %s#%s failed: %s", repo, issue_number, e)
        return
    logger.info("pr_state: closed %s#%s", repo, issue_number)


def _close_linked_gh_issue(
    title: str,
    pr_url: str | None,
    closer: Callable[[str, str, str], None],
) -> None:
    """Resolve owner/repo from `pr_url`, Issue number from `title`, and
    backend from `pr_url`'s own hostname, then close.

    Guards against a split-source mismatch: if the card title carries an
    `[owner/repo]` that disagrees with the PR url's repo (a recycled / mis-
    linked card), skip the close rather than risk closing the wrong repo's
    issue N. Backend is resolved from the PR url's hostname (not the
    title's tag) since that's the authoritative signal for where the PR
    actually lives — the title's tag may not reflect the real backend yet
    (see `fr_vk.dispatch.build_card_title`'s docstring).
    """
    if not pr_url or not title:
        return
    parsed_title = _cardref.parse_card_title(title)
    m_repo = _REPO_FROM_URL_RE.match(pr_url)
    if not parsed_title or not m_repo:
        return
    _tag, title_repo, issue_num = parsed_title
    url_repo = m_repo.group(1)
    if url_repo != title_repo:
        logger.warning(
            "pr_state: skip close — title repo %s != PR url repo %s (issue #%s)",
            title_repo,
            url_repo,
            issue_num,
        )
        return
    backend = _hosts.backend_for_hostname(urlparse(pr_url).hostname)
    closer(title_repo, str(issue_num), backend)


def tick(
    mcp: MCPCardClient,
    pr_observations: dict[str, str],
    *,
    close_gh_issue: Callable[[str, str, str], None] | None = None,
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
            elif current_status == "In progress" and pr_status == "merged":
                # Skip-stage (#290): the PR merged before we ever observed it
                # In review (e.g. observations were empty the whole time).
                # Transition straight to Done so backlog cards reconcile.
                new_status = "Done"
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
                # The Done cascade is best-effort and must never abort the
                # sweep — on the first post-#290 tick the WHOLE backlog flows
                # through here, so one card's cleanup failure can't be allowed
                # to starve the rest. (`archive_for_card` and the default
                # closer are already internally non-fatal; this guard also
                # covers an injected closer or a future change.)
                try:
                    archive_for_card(mcp, simple_id)
                    _close_linked_gh_issue(
                        title,
                        pr_url if isinstance(pr_url, str) else None,
                        closer,
                    )
                except Exception as e:  # noqa: BLE001 — non-fatal cleanup
                    logger.warning("pr_state: Done cascade for %s failed: %s", simple_id, e)

    return transitioned


def reconcile_done_issues(
    mcp: MCPCardClient,
    *,
    project_id: str | None = None,
    seen: set[str] | None = None,
    close_gh_issue: Callable[[str, str, str], None] | None = None,
    max_closes: int = _MAX_DONE_CLOSES_PER_TICK,
) -> set[str]:
    """Close the linked GH Issue of every terminal-Done card (#294).

    `pr_state.tick` only closes Issues for cards IT transitions In-review→Done.
    A card moved to Done out-of-band (operator manual move, VK auto-move) is
    never scanned by `tick`, so its Issue stays open and downstream phases
    wedge. This sweep closes the linked Issue for ALL Done cards, deriving the
    Issue's coordinates from the card TITLE (`gh#N: [owner/repo]`) — the Issue's
    own identity, independent of any PR url (a manually-Done card may have none).

    Bounded by `seen`, a set of `"<owner/repo>#<n>"` keys already handled:
    keys in `seen` are skipped (no gh call), so the first post-deploy tick
    closes (up to `max_closes`) of the open backlog and every later tick is
    ~0 gh calls. At most `max_closes` Issues are closed per call — a large
    first-deploy backlog is amortized across ticks rather than bursting under
    one flock. Returns the updated `seen` for the caller to persist. Fully
    defensive — never raises.

    The `seen` set grows for the daemon's lifetime (never pruned); keys are
    short strings and the idempotent closer makes a lost/stale file harmless,
    so unbounded growth is an accepted trade-off.

    Backend is resolved from the card title's tag (`_cardref.BACKEND_FOR_TAG`)
    — there's no PR url here to derive it from (a manually-Done card may
    have none), so the title's tag is the only signal available. In
    practice this is "github" for every card today (nothing threads a
    real backend into dispatched titles yet — see
    `fr_vk.dispatch.build_card_title`'s docstring), but the parse is
    already multi-backend-capable.
    """
    closer = close_gh_issue if close_gh_issue is not None else _default_close_gh_issue
    seen = set(seen or ())

    list_kwargs: dict[str, Any] = {"status": "Done"}
    if project_id is not None:
        list_kwargs["project_id"] = project_id
    try:
        resp = mcp.list_issues(**list_kwargs)
    except Exception as e:  # noqa: BLE001 — non-fatal
        logger.warning("pr_state: reconcile list_issues failed: %s", e)
        return seen

    closes = 0
    for card in _normalize_issues(resp):
        # Defensive: the MCP filter is authoritative, but re-check (an
        # in-memory fake returns all cards regardless of the status kwarg).
        if str(card.get("status", "")) != "Done":
            continue
        parsed = _cardref.parse_card_title(str(card.get("title") or ""))
        if not parsed:
            continue
        tag, repo, num = parsed
        key = f"{repo}#{num}"
        # A key in `seen` is skipped before any gh call. This also means a
        # human who REOPENS an Issue we closed is intentionally honoured — the
        # sweep never re-closes it (manual intent wins).
        if key in seen:
            continue
        if closes >= max_closes:
            logger.info(
                "pr_state: reconcile hit per-tick cap (%d); remaining Done "
                "Issues deferred to the next tick",
                max_closes,
            )
            break
        closes += 1
        backend = _cardref.BACKEND_FOR_TAG.get(tag, "github")
        try:
            closer(repo, str(num), backend)
        except Exception as e:  # noqa: BLE001 — one bad close mustn't drop the rest
            logger.warning("pr_state: reconcile close %s failed: %s", key, e)
            continue
        seen.add(key)

    return seen
