"""D1 — `fr.bridge.tick` respects MAX_CONCURRENT slot budget.

The slot gate lives in `fr.bridge.tick` (not `dispatch_phase`) because
the decision needs both a slot-aware counter (`count_active_ws(mcp)`)
and a per-plan iteration scope. We stub `count_active_ws` rather than
seeding `FakeMcpClient.workspaces` so the test pins the behavior at the
function boundary the spec actually names.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from tests.unit.fakes import FakeGhClient, FakeMcpClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan(repo: str = "derio-net/superpowers-for-vk", issue_number: int = 42):
    from fr import parse

    plan = parse(FIXTURE)
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{issue_number}"}
            )
        }
    )
    plan = dc_replace(
        plan, phases=(phase,), meta=plan.meta.model_copy(update={"target_repo": repo})
    )
    return plan, repo, issue_number


def test_tick_defers_when_active_workspaces_saturate_budget(monkeypatch):
    """count_active_ws=3 with MAX_CONCURRENT=2 → no MCP dispatch calls."""
    from fr.bridge import tick
    from fr.observe import observe
    from fr.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()

    from fr.bridge import slots as slots_mod

    monkeypatch.setattr(slots_mod, "count_active_ws", lambda _mcp: 3)
    monkeypatch.setenv("MAX_CONCURRENT", "2")

    result = tick(plan, gh, mcp)

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert create_calls == []
    assert result.synced == 0
    # The phase that *would* have dispatched is recorded as skipped/deferred
    # so the operator sees the budget pressure in the tick result.
    assert result.skipped >= 1


def test_tick_dispatches_within_budget(monkeypatch):
    """count_active_ws=0 with MAX_CONCURRENT=2 → dispatch fires normally."""
    from fr.bridge import tick
    from fr.observe import observe
    from fr.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()

    from fr.bridge import slots as slots_mod

    monkeypatch.setattr(slots_mod, "count_active_ws", lambda _mcp: 0)
    monkeypatch.setenv("MAX_CONCURRENT", "2")

    result = tick(plan, gh, mcp)

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
    assert result.synced == 1


def test_count_active_ws_counts_unarchived():
    """The helper itself must filter on the `archived` flag."""
    from fr.bridge.slots import count_active_ws

    class _Stub:
        def list_workspaces(self):
            return [
                {"id": "a", "archived": False},
                {"id": "b", "archived": True},
                {"id": "c", "archived": False},
            ]

    assert count_active_ws(_Stub()) == 2


def test_max_concurrent_env_override(monkeypatch):
    """Default is 8; env var overrides."""
    from fr.bridge.slots import max_concurrent

    monkeypatch.delenv("MAX_CONCURRENT", raising=False)
    assert max_concurrent() == 8

    monkeypatch.setenv("MAX_CONCURRENT", "3")
    assert max_concurrent() == 3
