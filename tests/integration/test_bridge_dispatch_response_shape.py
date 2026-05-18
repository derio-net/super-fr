"""Pin `dispatch_phase` against the REAL `vibe-kanban-mcp` response shapes.

VK's MCP tools return DIFFERENT envelope keys per tool (see
`vibe-kanban-mcp` `crates/mcp/src/task_server/tools/`):

- `create_issue`    → `{"issue_id": "<uuid>"}`
- `update_issue`    → `{"issue": {...}}`
- `start_workspace` → `{"workspace_id": "<uuid>"}`
- `link_workspace_issue` → `{"success": True, "workspace_id": ..., "issue_id": ...}`

Before this fix `vk.bridge.dispatch._expect_id` only looked for `"id"`
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
        self.cards[card_id] = {
            "id": card_id,
            "title": title,
            "description": description,
            "status": "To do",  # VK's default
        }
        # Real VK envelope — no top-level `id`.
        return {"issue_id": card_id}

    def update_issue(self, card_id: str, **changes: Any) -> dict[str, Any]:
        self._record("update_issue", {"card_id": card_id, **changes})
        self.cards.setdefault(card_id, {"id": card_id}).update(changes)
        # Real VK envelope — wrapped.
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
        self._next_ws += 1
        ws_id = f"ws-uuid-{self._next_ws}"
        self.workspaces[ws_id] = {
            "id": ws_id,
            "name": name,
            "repo_id": repo_id,
            "branch": branch,
            "executor": executor,
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
    from vk import parse
    from vk.bridge import tick

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(TARGET_REPO, set()).update(
        {"vk-ready", "vk-blocked", "vk-synced", "phase:1", "plan:2026-05-18-response-shape-fixture"}
    )
    gh.add_issue(
        TARGET_REPO,
        42,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-response-shape-fixture"},
    )

    mcp = _RealShapeMcp()
    result = tick(plan, gh, mcp)

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
    # `start_workspace.workspace_id` must flow into `link_workspace_issue.workspace_id`
    assert start_args["repo_id"] == TARGET_REPO_ID
    assert link_args["workspace_id"] == "ws-uuid-1"
    assert link_args["issue_id"] == "card-uuid-1"
