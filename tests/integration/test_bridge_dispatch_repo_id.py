"""Bridge dispatch end-to-end with the REAL VK MCP wire shape.

The 2026-05-18 incident exposed that the v2 bridge dispatch path was never
exercised against the real `vibe-kanban-mcp` server:

- `list_repos` returns `{"repos": [{"id": <Uuid>, "name": <short>}], ...}`
  (short names; the `id` is the canonical handle).
- `start_workspace` expects
  `{"repositories": [{"repo_id": <Uuid>, "branch": <str>}], "name": ..., "executor": ...}`
  (per `crates/mcp/src/task_server/tools/task_attempts.rs`).

The bridge before this fix compared full `owner/name` against short
names (gate always failed) and sent `{"repositories": ["owner/name"]}`
(structurally invalid). Both ARE wrong at the same time, so the
existing `FakeMcpClient` (which used full `owner/name` everywhere)
masked the gap.

This module pins the corrected contract end-to-end with a wire-shape-faithful
double — refuses anything that doesn't match the real server.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

TARGET_REPO = "derio-net/superpowers-for-vk"
TARGET_REPO_ID = "uuid-superpowers-for-vk"


class WireShapeMcpClient:
    """MCP double that enforces the REAL `vibe-kanban-mcp` wire shape.

    Diverges from `FakeMcpClient` deliberately:
      - `list_repos()` → `{"repos": [{"id": <uuid>, "name": <short>}], "count": N}`
      - `start_workspace(*, name, repo_id, executor, branch, ...)` — no `repo=`,
        no top-level `branch` in the recorded payload (per-repo only).

    Raises on the wrong shape so a regression surfaces immediately rather
    than silently producing a successful-looking call.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._repos = [
            {"id": "uuid-agent-images", "name": "agent-images"},
            {"id": "uuid-frank", "name": "frank"},
            {"id": "uuid-superpowers-for-vk", "name": "superpowers-for-vk"},
            {"id": "uuid-willikins", "name": "willikins"},
        ]
        self._next_card = 0
        self._next_ws = 0
        self.issues: dict[str, dict[str, Any]] = {}
        self.workspaces: dict[str, dict[str, Any]] = {}

    def _record(self, name: str, args: dict[str, Any]) -> None:
        self.calls.append((name, args))

    def list_repos(self) -> dict[str, Any]:
        self._record("list_repos", {})
        return {"repos": [dict(r) for r in self._repos], "count": len(self._repos)}

    def list_issues(self, **kw: Any) -> list[dict[str, Any]]:
        self._record("list_issues", {**kw})
        return list(self.issues.values())

    def list_workspaces(self, **kw: Any) -> list[dict[str, Any]]:
        self._record("list_workspaces", {**kw})
        return list(self.workspaces.values())

    def create_issue(self, *, title: str, description: str = "", **kw: Any) -> dict[str, Any]:
        self._record("create_issue", {"title": title, "description": description, **kw})
        self._next_card += 1
        cid = f"card-{self._next_card}"
        self.issues[cid] = {"id": cid, "title": title, "description": description}
        return self.issues[cid]

    def update_issue(self, card_id: str, **changes: Any) -> dict[str, Any]:
        self._record("update_issue", {"card_id": card_id, **changes})
        self.issues.setdefault(card_id, {"id": card_id}).update(changes)
        return self.issues[card_id]

    def start_workspace(
        self,
        *,
        name: str,
        repo_id: str,
        executor: str,
        branch: str,
        **kw: Any,
    ) -> dict[str, Any]:
        # Hard-validate the real wire contract: repo_id must look like a Uuid
        # (or our test-uuid stand-in), executor must be a registered string,
        # branch must be non-empty. The real server returns 4xx otherwise; the
        # fake refuses to record so tests see the structural error directly.
        if not isinstance(repo_id, str) or not repo_id:
            raise TypeError(f"start_workspace: repo_id must be a non-empty string, got {repo_id!r}")
        if not branch:
            raise TypeError("start_workspace: branch must be non-empty")
        self._record(
            "start_workspace",
            {"name": name, "repo_id": repo_id, "executor": executor, "branch": branch, **kw},
        )
        self._next_ws += 1
        wid = f"ws-{self._next_ws}"
        self.workspaces[wid] = {
            "id": wid,
            "name": name,
            "repo_id": repo_id,
            "branch": branch,
            "executor": executor,
        }
        return self.workspaces[wid]

    def link_workspace_issue(self, workspace_id: str, issue_id: str) -> None:
        self._record("link_workspace_issue", {"workspace_id": workspace_id, "issue_id": issue_id})
        if workspace_id in self.workspaces:
            self.workspaces[workspace_id]["linked_issue"] = issue_id

    def close(self) -> None:
        self._record("close", {})


def _write_plan(plan_dir: Path, *, target_repo: str, issue_number: int) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: 2026-05-18-dispatch-fixture
            target_repo: {target_repo}
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
              title: Dispatch fixture
              tag: agentic
              depends_on: []
              tracking_issue: "https://github.com/{target_repo}/issues/{issue_number}"
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


def test_tick_dispatches_workspace_using_repo_id_from_list_repos(tmp_path: Path) -> None:
    """
    GIVEN a vk-ready phase with tracking_issue pointing at owner/name
    AND   VK's MCP server returning {repos: [{id, name}]} (short names)
    AND   start_workspace expecting {repositories: [{repo_id, branch}]}
    WHEN  bridge.tick() runs
    THEN  the unknown-repo gate accepts the phase (short name match)
    AND   start_workspace is called with repo_id=<the matching uuid>
          and branch="vk/gh-<issue_n>"
    AND   the workspace was linked to the freshly-created VK card
    AND   the gh Issue is stamped vk-synced
    AND   the tick reports synced=1, errors=0

    Regression guard for the 2026-05-18 incident: the v2 bridge rebuild was
    never tested against real `vibe-kanban-mcp`; both the unknown-repo gate
    AND the start_workspace payload had the wrong shape.
    """
    from fr import parse
    from fr.bridge import tick

    from tests.unit.fakes import FakeGhClient

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir, target_repo=TARGET_REPO, issue_number=42)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(TARGET_REPO, set()).update(
        {"vk-ready", "vk-blocked", "vk-synced", "phase:1", "plan:2026-05-18-dispatch-fixture"}
    )
    gh.add_issue(
        TARGET_REPO,
        42,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-dispatch-fixture"},
    )

    mcp = WireShapeMcpClient()
    result = tick(plan, gh, mcp)

    assert result.errors == 0, f"unexpected failures: {result.failures}"
    assert result.synced == 1, f"phase should have been dispatched; result={result}"

    start_calls = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert len(start_calls) == 1
    (_, start_args) = start_calls[0]
    assert start_args["repo_id"] == TARGET_REPO_ID, (
        f"start_workspace must use the uuid from list_repos, not the owner/name; "
        f"got repo_id={start_args['repo_id']!r}"
    )
    assert start_args["branch"] == "main"  # base branch (VK forks off this)
    assert start_args["executor"] == "CLAUDE_CODE"
    # No `repo=` kwarg should slip through.
    assert "repo" not in start_args, (
        f"start_workspace should NOT carry a `repo=` kwarg anymore; got {start_args!r}"
    )

    link_calls = [c for c in mcp.calls if c[0] == "link_workspace_issue"]
    assert len(link_calls) == 1

    assert "vk-synced" in gh.issues[(TARGET_REPO, 42)].labels


def test_tick_refuses_dispatch_when_short_name_not_in_vk(tmp_path: Path) -> None:
    """
    GIVEN a phase whose tracking_issue points at a repo whose SHORT NAME
          is not in VK's list_repos
    WHEN  bridge.tick() runs
    THEN  the gate refuses with a clean reason (no workspace dispatched)
    AND   no start_workspace call is made
    """
    from fr import parse
    from fr.bridge import tick

    from tests.unit.fakes import FakeGhClient

    other_repo = "derio-net/never-registered-repo"
    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir, target_repo=other_repo, issue_number=7)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    gh.repo_labels.setdefault(other_repo, set()).update(
        {"vk-ready", "vk-blocked", "vk-synced", "phase:1", "plan:2026-05-18-dispatch-fixture"}
    )
    gh.add_issue(
        other_repo,
        7,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-dispatch-fixture"},
    )

    mcp = WireShapeMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 0
    assert result.errors == 1
    assert any("unknown repo" in f or "never-registered-repo" in f for f in result.failures), (
        f"expected an unknown-repo failure, got: {result.failures}"
    )
    assert [c for c in mcp.calls if c[0] == "start_workspace"] == []
