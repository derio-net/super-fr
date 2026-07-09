"""Canonical phase-dispatch implementation.

The ONE place that creates a VK card + workspace for a `vk-ready` phase.
Both `fr_dispatch.tick` and any future direct callers (e.g. a CLI verb)
funnel through `dispatch_phase` so the create_issue + update_issue +
list_repos + start_workspace + link_workspace_issue sequence cannot
drift between implementations. Test B2 enforces this is the only such
sequence in `src/`.

Wire payload shape:
  - `create_issue`: title = "gh#N: [owner/repo]", description = newline-
    joined (plan, "Phase N/total", phase title, tracking_issue URL),
    followed by a `Spec:` link line and the shared enrichment block
    (plan prose + phase yaml — see `vk.render.enrichment_block`). The
    description seeds the workspace agent prompt, so the enrichment
    puts the full task context in front of the agent.
    Returns `{"issue_id": "<uuid>"}`.
  - `update_issue`: status = "In progress". Returns the wrapped
    `{"issue": {..., "simple_id": "FFE-NNN", ...}}` — the bridge
    extracts simple_id from here to build the workspace name.
  - `start_workspace`: name = "{simple_id} -> gh#{N}" (matches legacy
    convention so `reap_orphans` can match workspace ↔ card by sid),
    `repo_id` = the VK Uuid resolved from the SHORT name (`owner/name`
    → `name` → VK `id`) via `fr_vk.config.repo_id_for`,
    executor = CLAUDE_CODE, `branch` = the BASE branch ("main") VK
    forks the workspace branch off, `issue_id` = the freshly-created
    card so VK derives the workspace prompt from its title/description
    AND auto-links the workspace to the card. Returns
    `{"workspace_id": "<uuid>"}`.
  - `link_workspace_issue`: defensive safety net — VK already
    auto-linked via `start_workspace.issue_id`, but the explicit call
    documents the intent and survives any future server-side change.

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

from fr._urls import parse_issue_url
from fr.parser import Plan
from fr.render import enrichment_block, spec_url
from fr.types import PhaseDoc
from fr_dispatch.lifecycle import invoke_lifecycle_hook

from fr_vk import _cardref
from fr_vk import config as _config
from fr_vk._mcp_client import VkMcpError

__all__ = ["DispatchResult", "MCPDispatch", "build_card_title", "dispatch_phase"]

logger = logging.getLogger(__name__)


def build_card_title(repo: str, issue_n: int) -> str:
    """Canonical card-title format.

    Shared with `fr_dispatch.tick` so the pre-dispatch dedup check and the
    post-dispatch create_issue payload cannot drift. Format pinned by
    test D2 — `"gh#{n}: [{owner/repo}]"`.

    Delegates to `fr_vk._cardref.build_card_title`, defaulting to the
    `"github"` tag — preserves every existing call site's behavior with
    zero call-site changes. Nothing in the dispatch bridge threads a
    phase's actual backend through to here yet (that would mean plumbing
    it through `fr_dispatch.tick`/`dispatch_phase`'s signatures, out of
    scope for this pass — see docs/superpowers/specs/
    2026-07-09-multi-backend-git-host-adapters-design.md's non-goals);
    the card-title FORMAT is multi-backend-capable (parses gl#/gt#-tagged
    titles correctly) even though nothing produces them yet.
    """
    return _cardref.build_card_title("github", repo, issue_n)


class MCPDispatch(Protocol):
    """Structural surface the bridge requires from its MCP client.

    Covers `dispatch_phase` (create_issue / update_issue / list_repos /
    start_workspace / link_workspace_issue) plus the read-only helpers
    `fr_dispatch.tick` consults each iteration: `list_workspaces` for the
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
    even though `fr_vk.config.repo_id_for` would cache it, because the
    call site here documents the per-dispatch read for any future caller
    bypassing the tick path. The lookup goes through `fr_vk.config` so
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


def _extract_simple_id(update_resp: Any) -> str | None:
    """Pull `simple_id` out of VK's `update_issue` response.

    VK returns `update_issue` wrapped: `{"issue": {"id": ..., "simple_id":
    "FFE-NNN", ...}}`. The bridge uses `simple_id` as the workspace
    name's sid prefix so `reap_orphans` can match workspace → card by
    name. Returns None on an unexpected shape — callers fall back to a
    plan-slug-derived sid (still visible to operators).
    """
    if not isinstance(update_resp, dict):
        return None
    inner = update_resp.get("issue")
    if not isinstance(inner, dict):
        return None
    sid = inner.get("simple_id")
    return sid if isinstance(sid, str) and sid else None


def _expect_id(value: Any, op: str, *, field: str = "id") -> str:
    """Extract an id-string from an MCP tool response.

    VK's MCP tools use tool-specific envelope keys, not a generic `id`
    (see `vibe-kanban-mcp/.../remote_issues.rs` +
    `.../task_attempts.rs`):

    - `create_issue`    → `{"issue_id": "<uuid>"}`
    - `start_workspace` → `{"workspace_id": "<uuid>"}`

    Pass `field=` to name the key the tool actually uses. Falls back
    to a wrapped shape (`{"issue": {"id": ...}}`) and to a bare `id`
    for forward-compat with tools whose response shape is unchanged.
    Raises `VkMcpError` (with the offending payload in the message)
    if nothing matches — better than letting a `None` id propagate.

    Pre-2026-05-18 this only checked the bare `id` key, so the bridge
    raised on `create_issue` / `start_workspace` AFTER VK had already
    created the card → cards stranded in default "To do" with no
    workspace. The fix lets the full dispatch chain land.
    """
    if isinstance(value, dict):
        # Primary key for the tool (e.g. issue_id, workspace_id).
        candidate = value.get(field)
        if isinstance(candidate, str) and candidate:
            return candidate
        # Some tools return `{"<entity>": {"id": ...}}` — try the wrapped
        # form derived from the field name (`issue_id` → `issue`).
        wrap_key = field[:-3] if field.endswith("_id") else field
        wrapped = value.get(wrap_key)
        if isinstance(wrapped, dict):
            wrap_id = wrapped.get("id")
            if isinstance(wrap_id, str) and wrap_id:
                return wrap_id
        # Last-ditch: bare `id` (legacy convention; unused by VK today).
        bare = value.get("id")
        if isinstance(bare, str) and bare:
            return bare
    raise VkMcpError(f"{op} returned unexpected shape: {value!r}")


def dispatch_phase(
    plan: Plan,
    phase: PhaseDoc,
    mcp: MCPDispatch,
    *,
    project_id: str,
) -> DispatchResult:
    """Create VK card + workspace for a vk-ready phase.

    `project_id` is the VK project Uuid the card lands in. Required
    because the cron bridge runs outside any workspace context, so
    `create_issue` can't infer it server-side (see VK MCP's
    `remote_issues.rs::create_issue`). The caller — typically
    `fr_dispatch.tick` — reads `VK_DERIO_OPS_PROJECT` and forwards it.

    Raises:
        ValueError: if the phase has no `tracking_issue` (dispatch
            requires an anchoring GH Issue).
        VkMcpError: if the MCP server returns an unexpected payload
            shape (no `id` on create_issue / start_workspace) or VK
            has no repo registered for the tracking_issue's owner/name.
        Any: propagates exceptions from MCP calls (the caller — typically
            `fr_dispatch.tick` — is responsible for swallowing one-phase
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
    # First four lines are the legacy pinned shape (test H9 keeps them as
    # the prefix). The enrichment that follows — spec link, plan prose,
    # phase yaml — feeds the workspace agent directly: VK derives the
    # workspace prompt from this description via `start_workspace.issue_id`.
    desc_parts = [
        plan.meta.plan,
        f"Phase {phase.phase.number}/{len(plan.phases)}",
        phase.phase.title,
        tracking,
        "",
        f"Spec: {spec_url(plan) or plan.meta.spec or '—'}",
    ]
    enrichment = enrichment_block(plan, phase)
    if enrichment:
        desc_parts += ["", enrichment]
    description = "\n".join(desc_parts)

    card = mcp.create_issue(title=title, description=description, project_id=project_id)
    card_id = _expect_id(card, "create_issue", field="issue_id")
    # Extract `simple_id` from the wrapped update_issue response so the
    # workspace name can use it as the sid prefix — matching the legacy
    # bridge's `{simple_id} -> gh#{N}` convention so `reap_orphans` can
    # match workspace ↔ card. Falls back to plan-slug-PN if VK somehow
    # omits simple_id (defensive — operator sees the legacy-shaped name
    # in that case rather than a crash).
    update_resp = mcp.update_issue(card_id, status="In progress")
    simple_id = _extract_simple_id(update_resp) or (f"{plan.meta.plan}-P{phase.phase.number}")

    repo_id = _resolve_repo_id(mcp, repo)
    # `issue_id` serves a dual purpose at the server:
    #   1. VK refuses `start_workspace` without a prompt; passing
    #      `issue_id` lets VK derive the prompt from the linked card's
    #      title/description (see `task_attempts.rs::start_workspace`).
    #   2. VK auto-links the new workspace ↔ card on the server side
    #      (we still call `link_workspace_issue` below as a no-op safety
    #      net for any future change to the server-side link path).
    # `branch` is the BASE branch VK forks the new workspace off — see
    # `task_attempts.rs` which maps `r.branch -> WorkspaceRepoInput.
    # target_branch`. It must exist in the target repo; passing the
    # would-be workspace branch (`vk/gh-{N}`) returns 400.
    ws = mcp.start_workspace(
        name=f"{simple_id} -> gh#{issue_n}",
        repo_id=repo_id,
        executor="CLAUDE_CODE",
        branch="main",
        issue_id=card_id,
    )
    ws_id = _expect_id(ws, "start_workspace", field="workspace_id")

    mcp.link_workspace_issue(ws_id, card_id)

    # D5: notify the operator-configured hook that the phase transitioned
    # to in-progress. invoke_lifecycle_hook is fire-and-forget — failures
    # are logged and swallowed so a broken notifier can't undo a card
    # that has already been created.
    invoke_lifecycle_hook(tracking, "in-progress")

    return DispatchResult(card_id=card_id, workspace_id=ws_id)
