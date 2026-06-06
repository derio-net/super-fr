"""D4 — Unknown-repo phases are skipped with a failure metric.

The legacy bridge fetches the VK-known repo list once per tick via
`mcp.list_repos()` and refuses to dispatch any phase whose
`tracking_issue` lives outside that set. The v2 port keeps the
behaviour: in `fr.bridge.config`, the cached lookup is exposed via
`is_known_repo(repo, mcp)`; tick consults it before dispatching.
"""

from __future__ import annotations

import contextlib
from dataclasses import replace as dc_replace
from io import BytesIO
from pathlib import Path

import pytest

from tests.unit.fakes import FakeGhClient, FakeMcpClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


@pytest.fixture
def fake_pushgateway(monkeypatch):
    pushes: list[bytes] = []

    @contextlib.contextmanager
    def _fake_urlopen(req, timeout=10):
        body = req.data if hasattr(req, "data") else b""
        pushes.append(body if isinstance(body, bytes) else bytes(body))
        yield BytesIO(b"")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway.test.local:9091")
    return pushes


def _bodies(pushes: list[bytes]) -> str:
    return "\n".join(b.decode(errors="replace") for b in pushes)


def _dispatched_plan(repo: str, issue_number: int = 42):
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


def test_is_known_repo_uses_mcp_list_repos():
    """`is_known_repo` consults `mcp.list_repos()` (cached per tick)."""
    from fr.bridge.config import is_known_repo

    mcp = FakeMcpClient()
    # FakeMcpClient.list_repos() returns derio-net/{frank,willikins,superpowers-for-vk}.
    assert is_known_repo("derio-net/frank", mcp) is True
    assert is_known_repo("derio-net/superpowers-for-vk", mcp) is True
    assert is_known_repo("derio-net/unknown-repo", mcp) is False


def test_is_known_repo_caches_within_a_tick():
    """Repeated lookups inside one tick share a single list_repos call.

    The cache is process-wide and keyed on the MCP client id; the tick
    daemon is single-threaded and short-lived per iteration, so we don't
    bother with TTL/eviction. A long-running daemon with config drift
    would call `clear_repo_cache()` between ticks.
    """
    from fr.bridge import config

    mcp = FakeMcpClient()
    config.clear_repo_cache()

    config.is_known_repo("derio-net/frank", mcp)
    config.is_known_repo("derio-net/willikins", mcp)
    config.is_known_repo("derio-net/superpowers-for-vk", mcp)

    list_repo_calls = [c for c in mcp.calls if c[0] == "list_repos"]
    assert len(list_repo_calls) == 1, list_repo_calls


def test_tick_skips_unknown_repo_and_pushes_failure_metric(fake_pushgateway):
    from fr.bridge import config, tick
    from fr.observe import observe
    from fr.render import render

    config.clear_repo_cache()

    # FakeMcpClient.list_repos() does NOT include 'derio-net/foreign'.
    plan, repo, n = _dispatched_plan("derio-net/foreign")
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, mcp)

    # No dispatch sequence — no card, no workspace.
    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert create_calls == []
    ws_calls = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert ws_calls == []

    # Failure metric with reason="unknown_repo" was emitted.
    body = _bodies(fake_pushgateway)
    assert "willikins_vk_bridge_failure_total" in body
    assert 'reason="unknown_repo"' in body

    # Tick still completes (no exception) and the failure is in the result.
    assert result.synced == 0
    assert result.errors >= 1


def test_tick_dispatches_known_repo_normally(fake_pushgateway):
    """Sanity check — a known repo is not affected by the unknown-repo gate."""
    from fr.bridge import config, tick
    from fr.observe import observe
    from fr.render import render

    config.clear_repo_cache()

    plan, repo, n = _dispatched_plan("derio-net/superpowers-for-vk")
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 1
    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
