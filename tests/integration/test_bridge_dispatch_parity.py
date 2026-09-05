"""Executable half of `vk-dispatch-unchanged-after-cutover` (P4.T3.S2).

Spec 2026-08-14-workflow-shapes-and-workitem-dispatch §4.D / §8 Test Plan
step 3: "a phase-unit dispatch still creates exactly one VK card per ready
phase, and a second tick creates none (identity-based dedup holds)." This
pins that against `fr_dispatch.tick` + `VkRunner` post-cutover, driven by
a fake MCP client over a two-phase, two-ready-phase fixture plan — the
LIVE-bridge half of the row (walking the real board) stays the operator's
post-merge Test Plan and is NOT what flips the acceptance row's status.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient, FakeMcpClient

REPO = "derio-net/superpowers-for-vk"


def _write_two_ready_phase_plan(plan_dir: Path) -> None:
    """Two ROOT phases (no depends_on between them) — both project ready
    in the same tick, so a correct dispatch creates two cards, one each."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: dispatch-parity-fixture
            target_repo: {REPO}
            vk_version: ">=2.0.0,<3.0.0"
            created: "2026-08-14"
            """
        )
    )
    for n, issue in ((1, 501), (2, 502)):
        (plan_dir / f"{n:02d}.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                phase:
                  number: {n}
                  title: Ready phase {n}
                  tag: agentic
                  depends_on: []
                  tracking_issue: "https://github.com/{REPO}/issues/{issue}"
                tasks:
                  - number: 1
                    title: t
                    steps:
                      - id: P{n}.T1.S1
                        text: s
                state:
                  steps:
                    P{n}.T1.S1: {{ state: " ", ticked_at: null, note: null }}
                  completion: {{ at: null, note: null, observed_prs: [] }}
                """
            )
        )


def _preload_repo_labels(gh: FakeGhClient, repo: str) -> None:
    gh.repo_labels.setdefault(repo, set()).update(
        {
            "fr:ready",
            "fr:blocked",
            "fr:synced",
            "in-progress",
            "pr-ready",
            "manual",
            "plan:dispatch-parity-fixture",
            "phase:1",
            "phase:2",
        }
    )


def test_one_card_per_ready_phase_then_second_tick_creates_none(tmp_path: Path) -> None:
    """
    GIVEN a two-phase plan where BOTH phases are ready (no depends_on
          between them) and neither has been dispatched yet
    WHEN  fr_dispatch.tick() runs once
    THEN  exactly one VK card + one workspace is created PER ready phase
          (two of each)
    AND   both Issues are stamped fr:synced
    WHEN  fr_dispatch.tick() runs a SECOND time (same plan, same runner)
    THEN  no new cards, no new workspaces — identity-based dedup holds
          across ticks, matching pre-cutover VK dispatch behavior
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_two_ready_phase_plan(plan_dir)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_repo_labels(gh, REPO)
    gh.add_issue(
        REPO, 501, state="OPEN", labels={"fr:ready", "phase:1", "plan:dispatch-parity-fixture"}
    )
    gh.add_issue(
        REPO, 502, state="OPEN", labels={"fr:ready", "phase:2", "plan:dispatch-parity-fixture"}
    )

    mcp = FakeMcpClient()
    runner = VkRunner(mcp)

    first = tick(plan, gh, runner)
    assert first.errors == 0, f"unexpected failures: {first.failures}"
    assert first.synced == 2, f"expected one dispatch per ready phase; result={first}"

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    ws_calls = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert len(create_calls) == 2, f"expected one card per ready phase; got {create_calls}"
    assert len(ws_calls) == 2, f"expected one workspace per ready phase; got {ws_calls}"

    assert "fr:synced" in gh.issues[(REPO, 501)].labels
    assert "fr:synced" in gh.issues[(REPO, 502)].labels

    calls_after_first = len(mcp.calls)

    second = tick(plan, gh, runner)
    assert second.errors == 0, f"unexpected failures on second tick: {second.failures}"
    assert second.synced == 0, "second tick must dispatch nothing new — dedup holds"

    new_calls = mcp.calls[calls_after_first:]
    new_mutations = [
        c
        for c in new_calls
        if c[0] in {"create_issue", "start_workspace", "link_workspace_issue", "update_issue"}
    ]
    assert new_mutations == [], f"second tick produced new VK mutations: {new_mutations}"
