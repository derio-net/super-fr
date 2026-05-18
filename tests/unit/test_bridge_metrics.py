"""D3 — Pushgateway metrics emit on dispatch success, failure, heartbeat.

The legacy bridge pushes three metrics per tick:
  - `willikins_vk_bridge_sync_total` (counter, no labels) on each card sync
  - `willikins_vk_bridge_failure_total{reason="..."}` on each dispatch failure
  - `willikins_heartbeat_last_success_timestamp` (gauge) at end of tick

Tests monkeypatch `urllib.request.urlopen` so they capture the HTTP
payload without actually opening a socket — Pushgateway exposition is
text/plain, easy to grep for the metric name + label set.
"""

from __future__ import annotations

import contextlib
from dataclasses import replace as dc_replace
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from tests.unit.fakes import FakeGhClient, FakeMcpClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


@pytest.fixture
def fake_pushgateway(monkeypatch):
    """Record every Pushgateway push so tests can inspect what was emitted.

    Returns the recorder list — each entry is the raw bytes body of one
    POST that would have hit the gateway. Tests assert via substring.
    """
    pushes: list[bytes] = []

    @contextlib.contextmanager
    def _fake_urlopen(req, timeout=10):
        # `req` is a Request object — pull its data + URL for inspection.
        body = req.data if hasattr(req, "data") else b""
        pushes.append(body if isinstance(body, bytes) else bytes(body))
        yield BytesIO(b"")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway.test.local:9091")
    return pushes


def _dispatched_plan(repo: str = "derio-net/superpowers-for-vk", issue_number: int = 42):
    from vk import parse

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


def _bodies(pushes: list[bytes]) -> str:
    """Concatenate every captured push body into one searchable string."""
    return "\n".join(b.decode(errors="replace") for b in pushes)


def test_push_sync_total_emits_counter(fake_pushgateway):
    from vk.bridge.metrics import push_sync_total

    push_sync_total()
    body = _bodies(fake_pushgateway)
    assert "willikins_vk_bridge_sync_total" in body


def test_push_failure_total_emits_reason_label(fake_pushgateway):
    from vk.bridge.metrics import push_failure_total

    push_failure_total(reason="unknown_repo")
    body = _bodies(fake_pushgateway)
    assert "willikins_vk_bridge_failure_total" in body
    assert 'reason="unknown_repo"' in body


def test_push_heartbeat_emits_gauge(fake_pushgateway):
    from vk.bridge.metrics import push_heartbeat

    push_heartbeat()
    body = _bodies(fake_pushgateway)
    assert "willikins_heartbeat_last_success_timestamp" in body


def test_push_metric_swallows_network_failure(monkeypatch, fake_pushgateway):
    """A Pushgateway outage must not break the bridge tick."""
    from vk.bridge.metrics import push_sync_total

    def _boom(*a: Any, **kw: Any):
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    # No exception — the call returns silently.
    push_sync_total()


def test_tick_emits_sync_metric_on_dispatch_success(fake_pushgateway):
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 1
    body = _bodies(fake_pushgateway)
    assert "willikins_vk_bridge_sync_total" in body
    # Heartbeat fires at end of tick regardless of per-phase outcome.
    assert "willikins_heartbeat_last_success_timestamp" in body


def test_tick_emits_failure_metric_on_dispatch_error(fake_pushgateway):
    """D3 — when `create_issue` (the first dispatch-side MCP call) raises,
    the failure metric must fire with `reason="mcp_error"`.

    Pre-dispatch tick now issues:
      0 list_workspaces (slot budget)
      1 list_issues     (dedup snapshot)
      2 list_repos      (config repo-known gate)
    So the first create_issue is call #3 — fail there to actually exercise
    the dispatch-error metric path (not the unknown-repo path that
    `list_repos` failure routes through).
    """
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient(fail_on_call=3)
    result = tick(plan, gh, mcp)

    assert result.synced == 0
    assert result.errors >= 1
    body = _bodies(fake_pushgateway)
    assert "willikins_vk_bridge_failure_total" in body
    # The reason label discriminates dispatch errors from the
    # unknown-repo gate — pin it so a future refactor that collapses
    # the two paths back together regresses this test.
    assert 'reason="mcp_error"' in body
    assert 'reason="unknown_repo"' not in body


def test_tick_emits_gh_error_metric_when_label_stamp_fails(fake_pushgateway):
    """When `gh.ensure_labels` / `gh.edit_issue_labels` fails after a
    successful dispatch, the failure metric must use `reason="gh_error"`,
    NOT `reason="mcp_error"` — operators paged on MCP must not chase a
    GH outage.
    """
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    # GH mutation order for one vk-ready phase:
    #   0 ensure_labels      (apply's RepoLabelEnsure at the top)
    #   1 edit_issue_labels  (apply's per-issue label diff)
    #   2 ensure_labels      (tick's post-dispatch — ensure vk-synced)
    #   3 edit_issue_labels  (tick's post-dispatch — add vk-synced)
    # Fail #3 — that's inside tick's GH-stamp try-block, so the failure
    # should route through `reason="gh_error"`.
    gh.fail_on_mutation = 3

    mcp = FakeMcpClient()
    result = tick(plan, gh, mcp)

    body = _bodies(fake_pushgateway)
    assert 'reason="gh_error"' in body, body
    assert result.synced == 0


def test_tick_emits_heartbeat_even_on_idle_plan(fake_pushgateway):
    """Heartbeat is the liveness signal — it must always fire, even
    when there's nothing to dispatch."""
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "vk-synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 0
    body = _bodies(fake_pushgateway)
    assert "willikins_heartbeat_last_success_timestamp" in body
