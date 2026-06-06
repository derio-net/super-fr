"""Pin `dispatch_phase` against the REAL `vibe-kanban-mcp` response shapes.

VK's MCP tools return DIFFERENT envelope keys per tool (see
`vibe-kanban-mcp` `crates/mcp/src/task_server/tools/`):

- `create_issue`    → `{"issue_id": "<uuid>"}`
- `update_issue`    → `{"issue": {...}}`
- `start_workspace` → `{"workspace_id": "<uuid>"}`
- `link_workspace_issue` → `{"success": True, "workspace_id": ..., "issue_id": ...}`

Before this fix `fr_dispatch.dispatch._expect_id` only looked for `"id"`
(the legacy v1 bridge's convention), so `create_issue` and
`start_workspace` raised `VkMcpError` even though the calls succeeded
server-side. The bridge tick caught the exception AFTER VK had already
created the card → card stranded in the default "To do" status with
no linked workspace (operator-visible bug observed on
`agent-images/2026-05-17-v2-bridge-cutover` 2026-05-18 20:26 UTC).

This module pins the corrected contract with a wire-shape-faithful
double — refuses any response key that doesn't match VK's real
schema, so a regression surfaces immediately.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient

TARGET_REPO = "derio-net/superpowers-for-vk"
TARGET_SHORT = "superpowers-for-vk"
TARGET_REPO_ID = "uuid-superpowers-for-vk"


class _RealShapeMcp:
    """MCP double that returns the exact envelopes VK's MCP tools use.

    Diverges from `FakeMcpClient`: `create_issue` returns
    `{"issue_id": ...}` (no `id` key), `start_workspace` returns
    `{"workspace_id": ...}` (no `id` key), `update_issue` returns
    `{"issue": {...}}` (wrapped). Bridges that look at the wrong key
    surface as test failures here.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._next_card = 0
        self._next_ws = 0
        self.cards: dict[str, dict[str, Any]] = {}
        self.workspaces: dict[str, dict[str, Any]] = {}

    def _record(self, name: str, args: dict[str, Any]) -> None:
        self.calls.append((name, args))

    def list_repos(self) -> dict[str, Any]:
        self._record("list_repos", {})
        return {
            "repos": [{"id": TARGET_REPO_ID, "name": TARGET_SHORT}],
            "count": 1,
        }

    def list_issues(self, **kw: Any) -> dict[str, Any]:
        self._record("list_issues", {**kw})
        return {"issues": list(self.cards.values()), "count": len(self.cards)}

    def list_workspaces(self, **kw: Any) -> dict[str, Any]:
        self._record("list_workspaces", {**kw})
        return {"workspaces": list(self.workspaces.values())}

    def create_issue(self, *, title: str, description: str = "", **kw: Any) -> dict[str, Any]:
        self._record("create_issue", {"title": title, "description": description, **kw})
        self._next_card += 1
        card_id = f"card-uuid-{self._next_card}"
        # Real VK assigns a `simple_id` (e.g. "FFE-196") at creation
        # and surfaces it on subsequent reads. The bridge uses simple_id
        # as the sid prefix in workspace names so `reap_orphans` can
        # match workspace → card.
        simple_id = f"FFE-{self._next_card}"
        self.cards[card_id] = {
            "id": card_id,
            "simple_id": simple_id,
            "title": title,
            "description": description,
            "status": "To do",  # VK's default
        }
        # Real VK envelope — no top-level `id`.
        return {"issue_id": card_id}

    def update_issue(self, card_id: str, **changes: Any) -> dict[str, Any]:
        self._record("update_issue", {"card_id": card_id, **changes})
        self.cards.setdefault(card_id, {"id": card_id}).update(changes)
        # Real VK envelope — wrapped. Includes `simple_id` so callers
        # can extract it post-update without a separate `get_issue`.
        return {"issue": dict(self.cards[card_id])}

    def start_workspace(
        self,
        *,
        name: str,
        repo_id: str,
        executor: str,
        branch: str,
        **kw: Any,
    ) -> dict[str, Any]:
        self._record(
            "start_workspace",
            {"name": name, "repo_id": repo_id, "executor": executor, "branch": branch, **kw},
        )
        # VK's server-side rule (see `task_attempts.rs::start_workspace`):
        # the workspace MUST have a prompt — pass `prompt=` or pass
        # `issue_id=` so VK can derive the prompt from the issue's
        # title/description. Neither → server returns
        # `{success: False, error: "Provide `prompt`, or `issue_id` ..."}`.
        if not kw.get("prompt") and not kw.get("issue_id"):
            return {
                "success": False,
                "error": (
                    "Provide `prompt`, or `issue_id` that has a non-empty title/description."
                ),
            }
        # The `branch` field is the BASE branch (target_branch in the
        # internal payload — see `task_attempts.rs::start_workspace`
        # mapping `r.branch -> WorkspaceRepoInput.target_branch`). VK
        # forks the new workspace branch off this one, so it must
        # exist in the target repo. The bridge sending `vk/gh-{N}`
        # (the fork name) triggers a 400. Pin the contract here.
        if branch not in {"main", "master", "trunk"}:
            return {
                "success": False,
                "error": (
                    f"VK API returned error status: 400 Bad Request "
                    f"(base branch {branch!r} not found in target repo)"
                ),
            }
        self._next_ws += 1
        ws_id = f"ws-uuid-{self._next_ws}"
        self.workspaces[ws_id] = {
            "id": ws_id,
            "name": name,
            "repo_id": repo_id,
            "branch": branch,
            "executor": executor,
            "linked_issue": kw.get("issue_id"),
        }
        # Real VK envelope — no top-level `id`.
        return {"workspace_id": ws_id}

    def link_workspace_issue(self, workspace_id: str, issue_id: str) -> dict[str, Any]:
        self._record("link_workspace_issue", {"workspace_id": workspace_id, "issue_id": issue_id})
        if workspace_id in self.workspaces:
            self.workspaces[workspace_id]["linked_issue"] = issue_id
        return {"success": True, "workspace_id": workspace_id, "issue_id": issue_id}

    def close(self) -> None:
        self._record("close", {})


def _write_plan(plan_dir: Path) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: 2026-05-18-response-shape-fixture
            target_repo: {TARGET_REPO}
            vk_version: ">=2.0.0,<3.0.0"
            created: "2026-05-18"
            """
        )
    )
    (plan_dir / "01.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            phase:
              number: 1
              title: Wire shape fixture
              tag: agentic
              depends_on: []
              tracking_issue: "https://github.com/{TARGET_REPO}/issues/42"
            tasks:
              - number: 1
                title: t
                steps:
                  - id: P1.T1.S1
                    text: s
            state:
              steps:
                P1.T1.S1: {{ state: " ", ticked_at: null, note: null }}
              completion: {{ at: null, note: null, observed_prs: [] }}
            """
        )
    )


def test_tick_dispatches_end_to_end_against_real_vk_envelopes(tmp_path: Path) -> None:
    """
    GIVEN  a vk-ready phase and an MCP double returning VK's real envelope
           keys (`issue_id` for create_issue, `workspace_id` for
           start_workspace, `{"issue": {...}}` for update_issue)
    WHEN   bridge.tick() runs
    THEN   create_issue → update_issue(In progress) → start_workspace →
           link_workspace_issue all execute in order
    AND    `update_issue` is called with the card_id extracted from
           `create_issue.issue_id`
    AND    `link_workspace_issue(workspace_id, issue_id)` ties the
           freshly-created workspace to the freshly-created card
    AND    the tick reports synced=1, errors=0

    Regression guard for the 2026-05-18 incident where the bridge's
    `_expect_id` only looked for `"id"` and raised on `create_issue` /
    `start_workspace` — VK had already created the card, but the
    subsequent `update_issue` + `start_workspace` calls never ran,
    stranding the card in the default "To do" status with no workspace.
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(TARGET_REPO, set()).update(
        {"fr:ready", "fr:blocked", "fr:synced", "phase:1", "plan:2026-05-18-response-shape-fixture"}
    )
    gh.add_issue(
        TARGET_REPO,
        42,
        state="OPEN",
        labels={"fr:ready", "phase:1", "plan:2026-05-18-response-shape-fixture"},
    )

    mcp = _RealShapeMcp()
    result = tick(plan, gh, VkRunner(mcp))

    assert result.errors == 0, f"unexpected failures: {result.failures}"
    assert result.synced == 1, f"phase must dispatch end-to-end; result={result}"

    # Pin the full sequence and that ids flowed between steps.
    names = [c[0] for c in mcp.calls]
    create_idx = names.index("create_issue")
    assert names[create_idx : create_idx + 5] == [
        "create_issue",
        "update_issue",
        "list_repos",
        "start_workspace",
        "link_workspace_issue",
    ]

    (create_args,) = [c[1] for c in mcp.calls if c[0] == "create_issue"]
    (update_args,) = [c[1] for c in mcp.calls if c[0] == "update_issue"]
    (start_args,) = [c[1] for c in mcp.calls if c[0] == "start_workspace"]
    (link_args,) = [c[1] for c in mcp.calls if c[0] == "link_workspace_issue"]

    # `update_issue` must reuse the card_id that came out of `create_issue.issue_id`
    assert update_args["card_id"] == "card-uuid-1", (
        f"update_issue should reuse create_issue's issue_id; got {update_args!r}"
    )
    assert update_args.get("status") == "In progress"
    # `start_workspace` must include `issue_id` so VK can derive a
    # prompt from the linked issue's title/description (the workspace
    # would otherwise be rejected with "Provide `prompt`, or `issue_id` ...").
    assert start_args["repo_id"] == TARGET_REPO_ID
    assert start_args.get("issue_id") == "card-uuid-1", (
        f"start_workspace must carry issue_id=<card_id>; got {start_args!r}"
    )
    # `branch` must be the BASE branch (target_branch in VK's internal
    # payload), not the workspace branch name. VK forks off this branch;
    # passing `vk/gh-{N}` triggers a 400 because that branch doesn't
    # exist in the target repo.
    assert start_args.get("branch") == "main", (
        f"start_workspace.branch must be the BASE branch (e.g. 'main'), "
        f"not the workspace branch name; got {start_args.get('branch')!r}"
    )
    # Workspace name uses the freshly-created card's `simple_id` as the
    # sid prefix so `reap_orphans` can match workspace ↔ card on the
    # next tick. Plan-slug-PN as the sid wouldn't match card simple_ids
    # in `card_status` and the workspace would be archived right after
    # creation (observed live 2026-05-18 21:38).
    assert start_args["name"].startswith("FFE-1 -> "), (
        f"start_workspace.name must use the card's simple_id as sid "
        f"prefix so reap_orphans can match; got {start_args['name']!r}"
    )
    assert "-> gh#42" in start_args["name"]
    # `start_workspace.workspace_id` must flow into `link_workspace_issue.workspace_id`
    assert link_args["workspace_id"] == "ws-uuid-1"
    assert link_args["issue_id"] == "card-uuid-1"
