"""D3 — Pushgateway metrics emit on dispatch success, failure, heartbeat.

`fr_dispatch.metrics.MetricsPusher` pushes three metrics per tick:
  - `<namespace>_sync_total` (counter, no labels) on each dispatch
  - `<namespace>_failure_total{reason="..."}` on each dispatch failure
  - the heartbeat gauge at end of tick

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
from fr_dispatch.metrics import MetricsPusher

from tests.unit.fakes import FakeGhClient
from tests.unit.test_tick_workitem import FakeRunner

NS = "fr_test_bridge"
HEARTBEAT = "fr_test_heartbeat_last_success_timestamp"


def bridge_metrics() -> MetricsPusher:
    """A pusher with an adapter-style heartbeat name and reason alias."""
    return MetricsPusher(
        namespace=NS,
        job="fr-test-bridge",
        heartbeat_metric=HEARTBEAT,
        reason_aliases={"backend_error": "runner_error"},
    )


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


def _dispatched_plan(repo: str = "derio-net/fixture-repo", issue_number: int = 42):
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


def _phase_1_id(repo: str) -> str:
    """The id `tick` gives the minimal fixture's phase 1 (see test_tick_workitem)."""
    return f"{repo}/fixture-spec-design/2026-05-09-fixture-minimal/phase/1"


def _bodies(pushes: list[bytes]) -> str:
    """Concatenate every captured push body into one searchable string."""
    return "\n".join(b.decode(errors="replace") for b in pushes)


def test_push_sync_total_emits_counter(fake_pushgateway):
    push = bridge_metrics()
    push.push_sync_total()
    body = _bodies(fake_pushgateway)
    assert f"{NS}_sync_total" in body


def test_push_failure_total_emits_reason_label(fake_pushgateway):
    push = bridge_metrics()
    push.push_failure_total(reason="unknown_repo")
    body = _bodies(fake_pushgateway)
    assert f"{NS}_failure_total" in body
    assert 'reason="unknown_repo"' in body


def test_push_heartbeat_emits_gauge(fake_pushgateway):
    push = bridge_metrics()
    push.push_heartbeat()
    body = _bodies(fake_pushgateway)
    assert HEARTBEAT in body


def test_push_repo_desync_total_emits_counter_with_repo_label(fake_pushgateway):
    """#286 — a self-healed desync emits a dedicated counter labelled by repo,
    kept distinct from failure_total so it never reads as a tick failure."""
    push = bridge_metrics()
    push.push_repo_desync_total(repo="derio-net/runs-fr")
    body = _bodies(fake_pushgateway)
    assert f"{NS}_repo_desync_total" in body
    assert 'repo="derio-net/runs-fr"' in body
    assert f"# TYPE {NS}_repo_desync_total counter" in body
    # Distinct from failure_total — a heal event is not a failure.
    assert f"{NS}_failure_total" not in body


def test_null_metrics_desync_is_noop(fake_pushgateway):
    from fr_dispatch.metrics import NullMetrics

    NullMetrics().push_repo_desync_total(repo="x/y")  # no push, no raise
    assert _bodies(fake_pushgateway) == ""


def test_push_metric_swallows_network_failure(monkeypatch, fake_pushgateway):
    """A Pushgateway outage must not break the bridge tick."""
    push = bridge_metrics()

    def _boom(*a: Any, **kw: Any):
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    # No exception — the call returns silently.
    push.push_sync_total()


def test_tick_emits_sync_metric_on_dispatch_success(fake_pushgateway):
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    result = tick(plan, gh, FakeRunner(), metrics=bridge_metrics())

    assert result.synced == 1
    body = _bodies(fake_pushgateway)
    assert f"{NS}_sync_total" in body
    # Heartbeat fires at end of tick regardless of per-phase outcome.
    assert HEARTBEAT in body


def test_tick_emits_failure_metric_on_dispatch_error(fake_pushgateway):
    """D3 — when the runner's `dispatch` raises, the failure metric fires
    with the adapter's alias for `backend_error`, never `unknown_repo`."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    runner = FakeRunner(dispatch_fails={_phase_1_id(repo)})
    result = tick(plan, gh, runner, metrics=bridge_metrics())

    assert result.synced == 0
    assert result.errors >= 1
    body = _bodies(fake_pushgateway)
    assert f"{NS}_failure_total" in body
    # The reason label discriminates dispatch errors from the
    # unknown-repo gate — pin it so a future refactor that collapses
    # the two paths back together regresses this test.
    assert 'reason="runner_error"' in body
    assert 'reason="unknown_repo"' not in body


def test_tick_emits_gh_error_metric_when_label_stamp_fails(fake_pushgateway):
    """When `gh.ensure_labels` / `gh.edit_issue_labels` fails after a
    successful dispatch, the failure metric must use `reason="gh_error"`,
    NOT the backend-error reason — operators paged on the runner must not
    chase a GH outage.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    # GH mutation order for one ready phase:
    #   0 ensure_labels      (apply's RepoLabelEnsure at the top)
    #   1 edit_issue_labels  (apply's per-issue label diff)
    #   2 ensure_labels      (tick's post-dispatch — ensure fr:synced)
    #   3 edit_issue_labels  (tick's post-dispatch — add fr:synced)
    # Fail #3 — that's inside tick's GH-stamp try-block, so the failure
    # should route through `reason="gh_error"`.
    gh.fail_on_mutation = 3

    result = tick(plan, gh, FakeRunner(), metrics=bridge_metrics())

    body = _bodies(fake_pushgateway)
    assert 'reason="gh_error"' in body, body
    assert result.synced == 0


def test_tick_emits_heartbeat_even_on_idle_plan(fake_pushgateway):
    """Heartbeat is the liveness signal — it must always fire, even
    when there's nothing to dispatch."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "fr:synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    result = tick(plan, gh, FakeRunner(), metrics=bridge_metrics())

    assert result.synced == 0
    body = _bodies(fake_pushgateway)
    assert HEARTBEAT in body
