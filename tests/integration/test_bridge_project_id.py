"""Bridge tick threads `VK_DERIO_OPS_PROJECT` to `create_issue`.

VK's MCP server requires `project_id` for `create_issue` when the
server isn't running inside a linked workspace (the cron bridge is
exactly that case — see `vibe-kanban-mcp` `remote_issues.rs`).

The legacy bridge hard-coded the env var name `VK_DERIO_OPS_PROJECT`.
The v2 rebuild's `dispatch_phase` shipped without threading the value,
so the cron tick called `create_issue` without `project_id` and got
back `{success: False, error: "project_id is required (not available
from workspace context)"}` — surfaced as
`phase 1: create_issue returned unexpected shape: ...` in TickResult.

This module pins the corrected contract: tick reads the env (or an
explicit `project_id=` override), passes it through to `dispatch_phase`,
which forwards it as a kwarg to `mcp.create_issue`. A test asserts the
unset path fails cleanly with a single "project_id missing" failure
instead of leaking the opaque server error.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient, FakeMcpClient

TARGET_REPO = "derio-net/superpowers-for-vk"


def _write_plan(plan_dir: Path) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: 2026-05-18-project-id-fixture
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
              title: Project-id fixture
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


def _prep_gh(gh: FakeGhClient) -> None:
    gh.repo_labels.setdefault(TARGET_REPO, set()).update(
        {"vk-ready", "vk-blocked", "vk-synced", "phase:1", "plan:2026-05-18-project-id-fixture"}
    )
    gh.add_issue(
        TARGET_REPO,
        42,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-project-id-fixture"},
    )


def test_tick_passes_project_id_to_create_issue(tmp_path: Path) -> None:
    """
    GIVEN a vk-ready phase and `VK_DERIO_OPS_PROJECT` set in the env
    WHEN  bridge.tick() runs
    THEN  the mcp.create_issue call carries the project_id kwarg
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _prep_gh(gh)
    mcp = FakeMcpClient()

    result = tick(plan, gh, VkRunner(mcp))

    assert result.errors == 0, f"unexpected failures: {result.failures}"
    assert result.synced == 1, f"phase should have dispatched; result={result}"

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
    assert create_calls[0][1].get("project_id") == "test-vk-project-id", (
        f"create_issue must carry project_id from VK_DERIO_OPS_PROJECT; "
        f"got args={create_calls[0][1]!r}"
    )


def test_tick_fails_clean_when_project_id_unset(tmp_path: Path, monkeypatch) -> None:
    """
    GIVEN no `VK_DERIO_OPS_PROJECT_ID` AND no `VK_DERIO_OPS_PROJECT` env
    WHEN  bridge.tick() runs with a vk-ready phase
    THEN  the phase is NOT dispatched (no create_issue call)
    AND   the result carries one failure naming the env var
    AND   the `project_id_missing` metric reason is recorded
    """
    from fr import parse
    from fr_dispatch import tick

    monkeypatch.delenv("VK_DERIO_OPS_PROJECT", raising=False)
    monkeypatch.delenv("VK_DERIO_OPS_PROJECT_ID", raising=False)

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _prep_gh(gh)
    mcp = FakeMcpClient()

    result = tick(plan, gh, VkRunner(mcp))

    assert [c for c in mcp.calls if c[0] == "create_issue"] == [], (
        "no create_issue must be attempted when project_id is unset"
    )
    assert result.synced == 0
    assert any("VK_DERIO_OPS_PROJECT" in f or "project_id" in f for f in result.failures), (
        f"expected a project-id failure, got: {result.failures}"
    )


def test_tick_prefers_canonical_id_env_over_legacy(tmp_path: Path, monkeypatch) -> None:
    """
    GIVEN `VK_DERIO_OPS_PROJECT_ID` (the K8s-injected canonical name) set
          AND `VK_DERIO_OPS_PROJECT` (legacy fallback) ALSO set, to a
          different value
    WHEN  bridge.tick() runs
    THEN  create_issue receives the `VK_DERIO_OPS_PROJECT_ID` value

    Pins the K8s manifest's actual env name (`_ID` suffix) as the
    canonical reader, with the bare-name as a legacy fallback. The pod
    we deploy to injects `VK_DERIO_OPS_PROJECT_ID` and an earlier wave
    of this fix mis-read the bare name.
    """
    from fr import parse
    from fr_dispatch import tick

    monkeypatch.setenv("VK_DERIO_OPS_PROJECT_ID", "uuid-canonical-from-k8s")
    monkeypatch.setenv("VK_DERIO_OPS_PROJECT", "uuid-legacy-fallback")

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _prep_gh(gh)
    mcp = FakeMcpClient()

    tick(plan, gh, VkRunner(mcp))

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
    assert create_calls[0][1].get("project_id") == "uuid-canonical-from-k8s", (
        f"VK_DERIO_OPS_PROJECT_ID must win over the legacy name; got "
        f"{create_calls[0][1].get('project_id')!r}"
    )


def test_tick_dedup_passes_project_id_to_list_issues(tmp_path: Path) -> None:
    """
    GIVEN a vk-ready phase
    WHEN  bridge.tick() runs (dedup snapshot fires before dispatch)
    THEN  the mcp.list_issues call carries the project_id kwarg

    Scoping dedup to the bridge's own project avoids matching titles from
    unrelated VK projects (and keeps the call cheap on VK's side).
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _prep_gh(gh)
    mcp = FakeMcpClient()

    tick(plan, gh, VkRunner(mcp))

    list_calls = [c for c in mcp.calls if c[0] == "list_issues"]
    assert len(list_calls) >= 1
    assert all(c[1].get("project_id") == "test-vk-project-id" for c in list_calls), (
        f"list_issues calls must carry project_id; got {[c[1] for c in list_calls]!r}"
    )
