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
import subprocess
from collections.abc import Callable
from typing import Any, Protocol

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


_GH_REPO_FROM_URL_RE = re.compile(r"https?://github\.com/([\w.-]+/[\w.-]+)/(?:pull|issues)/\d+")
_GH_ISSUE_NUM_FROM_TITLE_RE = re.compile(r"gh#(\d+)")
# The dispatch title is `gh#N: [owner/repo]` — the Issue's own coordinates.
_GH_REPO_FROM_TITLE_RE = re.compile(r"\[([\w.-]+/[\w.-]+)\]")
# Anchored full-title parse for the terminal-Done sweep (#294): num AND repo
# from the known `gh#N: [owner/repo]` prefix, so a free-text suffix (or a
# second bracketed token an operator typed) can't inject a mis-target.
_DONE_TITLE_RE = re.compile(r"^gh#(\d+):\s*\[([\w.-]+/[\w.-]+)\]")
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
    """Resolve owner/repo from `pr_url` and Issue number from `title`, then close.

    Guards against a split-source mismatch: if the card title carries an
    `[owner/repo]` that disagrees with the PR url's repo (a recycled / mis-
    linked card), skip the close rather than risk closing the wrong repo's
    issue N.
    """
    if not pr_url or not title:
        return
    m_repo = _GH_REPO_FROM_URL_RE.match(pr_url)
    m_num = _GH_ISSUE_NUM_FROM_TITLE_RE.search(title)
    if not m_repo or not m_num:
        return
    repo = m_repo.group(1)
    m_title_repo = _GH_REPO_FROM_TITLE_RE.search(title)
    if m_title_repo and m_title_repo.group(1) != repo:
        logger.warning(
            "pr_state: skip close — title repo %s != PR url repo %s (issue #%s)",
            m_title_repo.group(1),
            repo,
            m_num.group(1),
        )
        return
    closer(repo, m_num.group(1))


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
    close_gh_issue: Callable[[str, str], None] | None = None,
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
        m = _DONE_TITLE_RE.match(str(card.get("title") or ""))
        if not m:
            continue
        num, repo = m.group(1), m.group(2)
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
        try:
            closer(repo, num)
        except Exception as e:  # noqa: BLE001 — one bad close mustn't drop the rest
            logger.warning("pr_state: reconcile close %s failed: %s", key, e)
            continue
        seen.add(key)

    return seen
