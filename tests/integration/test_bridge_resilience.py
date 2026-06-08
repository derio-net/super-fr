"""Integration tests for bridge resilience properties.

These tests pin invariants that must hold even under operator interference
or partial failures. Phase 1 covers I7 (renderer is source of truth for
labels). Phase 5 adds I1-I4, I6, I9, plus the I2 TimeoutError sub-case
from the 2026-05-18 MCP timeout cascade incident.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

import pytest
from fr_vk.runner import VkRunner

MULTI_PHASE = Path(__file__).parent.parent / "unit" / "fixtures" / "v2_plan_multi_phase"
MINIMAL = Path(__file__).parent.parent / "unit" / "fixtures" / "v2_plan_minimal"


def test_renderer_reverses_manual_label_change():
    """
    GIVEN a queued phase (fr:ready + runner:vk) in steady state
    AND   an operator manually removes fr:ready via `gh issue edit`
    WHEN  render() + diff() run again (simulating next bridge tick)
    THEN  the renderer projects fr:ready back — the surviving runner:<name>
    attribution anchors queue membership, so the state machine restores
    the lifecycle (v3: removing EVERY queue marker incl. runner:<name> is
    the label-level dequeue; `fr undispatch` is the clean verb for that).
    """
    from fr import parse
    from fr.apply import apply
    from fr.diff import IssueLabelChange, diff
    from fr.render import render
    from fr.states import GhState, PhaseObservation

    from tests.unit.fakes import FakeGhClient

    plan = parse(MULTI_PHASE)
    # Use only the first phase (no deps, agentic) and give it a tracking_issue
    p1 = next(p for p in plan.phases if p.phase.number == 1)
    p1_dispatched = p1.model_copy(
        update={
            "phase": p1.phase.model_copy(
                update={
                    "tracking_issue": "https://github.com/derio-net/superpowers-for-vk/issues/500"
                }
            )
        }
    )
    plan = dc_replace(plan, phases=(p1_dispatched,))

    # Steady-state observation: issue has all the right labels
    rendered_ref = render(plan, GhState(phases={}), queue_runner="vk")
    ref_labels = {ld.name for ld in rendered_ref.issue_per_phase[1].labels}

    # Operator manually removes vk-ready from the observed state
    observed_after_op = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(ref_labels - {"fr:ready"}),  # fr:ready gone; runner:vk stays
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )

    # Simulate next tick: render from plan state (not operator-edited observed)
    rendered = render(plan, observed_after_op)

    # Renderer still projects vk-ready (plan state is authoritative)
    label_names = {ld.name for ld in rendered.issue_per_phase[1].labels}
    assert "fr:ready" in label_names

    # diff sees the gap and emits a label change to restore vk-ready
    d = diff(rendered, observed_after_op, plan=plan)
    label_changes = [m for m in d.mutations if isinstance(m, IssueLabelChange)]
    assert any("fr:ready" in m.add for m in label_changes), (
        "expected IssueLabelChange adding fr:ready back"
    )

    # apply restores it
    gh = FakeGhClient()
    gh.add_issue(
        "derio-net/superpowers-for-vk", 500, state="OPEN", labels=ref_labels - {"fr:ready"}
    )
    result = apply(d, gh, plan=plan)
    assert result.failures == (), f"unexpected failures: {result.failures}"
    assert "fr:ready" in gh.issues[("derio-net/superpowers-for-vk", 500)].labels


# ── I1: MCP subprocess startup failure → loud exit ────────────────────


def test_bridge_exits_loud_when_mcp_subprocess_fails_to_start(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When neither `vibe-kanban-mcp` nor `npx` is on PATH, the bridge
    must exit non-zero and tell the operator which package to install."""
    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit) as exc_info:
        bridge_cli._construct_mcp_client()
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "vibe-kanban-mcp" in err
    assert "npx" in err
    assert "npm install -g vibe-kanban" in err


# ── I2: MCP subprocess crash mid-tick → tick aborts cleanly ──────────


def test_tick_aborts_cleanly_on_mcp_subprocess_death() -> None:
    """If an MCP call raises a low-level subprocess failure mid-tick,
    the tick records the failure and stops cleanly — no `vk-synced` flip
    on the GH side, no half-state."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr_dispatch import tick

    from tests.unit.fakes import FakeGhClient, FakeMcpClient

    plan = parse(MINIMAL)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/42"}
            )
        }
    )
    plan = dc_replace(
        plan, phases=(phase,), meta=plan.meta.model_copy(update={"target_repo": repo})
    )
    gh = FakeGhClient()
    gh.add_issue(repo, 42, state="OPEN", labels={"fr:ready", "phase:1"})

    class _DyingMcp(FakeMcpClient):
        _calls = 0

        def list_repos(self) -> Any:
            self._calls += 1
            raise BrokenPipeError("MCP subprocess gone")

    mcp = _DyingMcp()
    result = tick(plan, gh, VkRunner(mcp))
    assert result.synced == 0
    assert result.errors >= 1
    # `vk-synced` must NOT land on the issue.
    assert "fr:synced" not in gh.issues[(repo, 42)].labels


def test_tick_continues_when_one_phase_times_out() -> None:
    """2026-05-18 incident: when `start_workspace` for one phase raises
    TimeoutError, sibling phases dispatch normally. The in-tick per-phase
    guard at src/vk/bridge/__init__.py must catch TimeoutError (not just
    BrokenPipeError / CalledProcessError) — TimeoutError is a subclass of
    Exception, so `except Exception` already covers it; this test pins
    that behaviour against future narrowing."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr_dispatch import tick

    from tests.unit.fakes import FakeGhClient, FakeMcpClient

    plan = parse(MULTI_PHASE)
    repo = "derio-net/superpowers-for-vk"
    # The multi_phase fixture has phases 1 (agentic), 2 (agentic), and
    # 10 (manual). Stamp tracking_issues on all three and force phase 10
    # to agentic so all three are dispatch-eligible.
    phases_list = list(plan.phases)
    new_phases = []
    for i, ph in enumerate(phases_list[:3]):
        new_phases.append(
            ph.model_copy(
                update={
                    "phase": ph.phase.model_copy(
                        update={
                            "tracking_issue": f"https://github.com/{repo}/issues/{100 + i}",
                            "depends_on": [],  # let all three be eligible
                            "tag": "agentic",
                        }
                    )
                }
            )
        )
    plan = dc_replace(
        plan,
        phases=tuple(new_phases),
        meta=plan.meta.model_copy(update={"target_repo": repo}),
    )

    gh = FakeGhClient()
    # Phase numbers from the fixture are 1, 2, 10 — labels match those.
    phase_numbers = [ph.phase.number for ph in plan.phases]
    issue_numbers = [100, 101, 102]
    for n, pn in zip(issue_numbers, phase_numbers, strict=True):
        gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", f"phase:{pn}"})

    class _TimeoutOnPhase2(FakeMcpClient):
        """Raise TimeoutError on phase 2's start_workspace (the second
        dispatch). FakeMcpClient receives one start_workspace per phase."""

        _ws_calls = 0

        def start_workspace(self, **kw: Any) -> dict[str, Any]:
            self._ws_calls += 1
            if self._ws_calls == 2:
                raise TimeoutError("No response from MCP server within 180.0s")
            return super().start_workspace(**kw)

    mcp = _TimeoutOnPhase2()
    result = tick(plan, gh, VkRunner(mcp))
    assert result.synced == 2, (
        f"phases 1 and 3 must dispatch, got synced={result.synced}, failures={result.failures}"
    )
    assert result.errors == 1
    assert any("No response from MCP server" in f for f in result.failures)


# ── I3: gh rate-limit response → backoff ─────────────────────────────


def test_tick_backs_off_on_gh_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_gh_rate_limit_guard` recognises gh 403 rate-limit stderr and
    skips this tick rather than re-raising — the next cron fire retries
    fresh. A failure metric is pushed with `reason='gh_rate_limited'`."""
    from fr.gh import GhError
    from fr_vk import bridge_cli

    pushed: list[str] = []

    def fake_push(*, reason: str) -> None:
        pushed.append(reason)

    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", fake_push)

    def boom() -> Any:
        raise GhError(
            "API rate limit exceeded",
            stderr="HTTP 403: API rate limit exceeded for user",
            returncode=1,
        )

    result = bridge_cli._gh_rate_limit_guard(boom)
    assert result is None
    assert pushed == ["gh_rate_limited"]


def test_tick_reraises_non_rate_limit_gh_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-rate-limit gh errors are not silently swallowed."""
    from fr.gh import GhError
    from fr_vk import bridge_cli

    def boom() -> Any:
        raise GhError("nope", stderr="permission denied", returncode=1)

    with pytest.raises(GhError):
        bridge_cli._gh_rate_limit_guard(boom)


# ── I4: Lock-file overlap prevention ─────────────────────────────────


def test_second_concurrent_tick_aborts_early(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second `python -m fr_dispatch` invocation while the first holds
    the lock exits 0 with a 'tick already in progress' message and does
    not touch gh / MCP."""
    from fr_vk import bridge_cli

    lock_path = tmp_path / "vk-bridge.lock"
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(lock_path))

    # Acquire the lock externally first.
    held = bridge_cli._acquire_lock(str(lock_path))

    # Stub `_configured_repos` so even if the lock weren't honoured we'd
    # still finish quickly; we want to assert the early-exit, not the
    # downstream tick path.
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [])
    monkeypatch.setattr(
        bridge_cli,
        "_construct_mcp_client",
        lambda: (_ for _ in ()).throw(AssertionError("must not reach MCP construction")),
    )

    try:
        rc = bridge_cli.main([])
    finally:
        held.close()
    assert rc == 0


# ── I6: Plan disappears between ticks → cards untouched, single warn ──


def test_plan_deletion_between_ticks_does_not_purge_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If a plan slug was seen in tick N but discover_plans no longer
    returns it in tick N+1, the bridge logs a single warning and leaves
    every VK card alone."""
    import logging

    from fr_vk import bridge_cli

    seen_file = tmp_path / "seen.json"
    seen_file.write_text('["plan-a", "plan-b"]')
    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", seen_file)
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [])

    class _StubMcp:
        def list_workspaces(self, **kw: Any) -> list[Any]:
            return []

        def list_issues(self, **kw: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())

    class _StubGh:
        pass

    monkeypatch.setattr(bridge_cli, "RealGhClient", lambda: _StubGh())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)

    caplog.set_level(logging.WARNING, logger="fr_dispatch")
    rc = bridge_cli.main([])
    assert rc == 0
    warns = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("plan-a no longer on disk" in w for w in warns)
    assert any("plan-b no longer on disk" in w for w in warns)


# ── I9: One plan's tick raising does not kill the daemon ─────────────


def test_per_plan_exception_does_not_kill_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If `tick()` raises for one plan, the daemon's outer loop logs,
    pushes a metric, and continues to the next plan. Without this guard,
    a single malformed plan would block every other plan in every other
    repo until an operator intervenes."""
    from dataclasses import dataclass

    from fr_vk import bridge_cli

    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "seen.json")

    # Three plans pretend to be discoverable.
    @dataclass
    class _FakePlan:
        dir: Path

    plans = [_FakePlan(dir=Path(name)) for name in ("plan-a", "plan-b", "plan-c")]

    # One configured repo; discover_plans returns all three plans.
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [repo_path])
    monkeypatch.setattr(
        bridge_cli, "_ensure_bridge_checkout", lambda configured, name, base=None: repo_path
    )
    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", lambda p: False)
    monkeypatch.setattr(bridge_cli, "_repo_owner_name", lambda p: "example/repo")
    monkeypatch.setattr(bridge_cli, "discover_plans", lambda repo, gh: plans)

    ticks: list[str] = []

    def fake_tick(plan: Any, gh: Any, mcp: Any, **kw: Any) -> None:
        ticks.append(plan.dir.name)
        if plan.dir.name == "plan-b":
            raise TimeoutError("simulated MCP timeout for plan-b")

    monkeypatch.setattr(bridge_cli, "_tick", fake_tick)

    class _StubMcp:
        def list_workspaces(self, **kw: Any) -> list[Any]:
            return []

        def list_issues(self, **kw: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())

    class _StubGh:
        pass

    monkeypatch.setattr(bridge_cli, "RealGhClient", lambda: _StubGh())

    pushed: list[str] = []

    def fake_push_failure(*, reason: str) -> None:
        pushed.append(reason)

    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", fake_push_failure)

    rc = bridge_cli.main([])
    assert rc == 0
    assert ticks == ["plan-a", "plan-b", "plan-c"], f"all three plans must be ticked; got {ticks!r}"
    assert any(r.startswith("plan_error:plan-b") for r in pushed), (
        f"expected a failure metric for plan-b; got {pushed!r}"
    )


# ── I8: `fr apply` and `fr_dispatch.tick` racing for the same plan ─────


def test_concurrent_apply_and_tick_are_idempotent(tmp_path: Path) -> None:
    """
    GIVEN a plan with steady-state Issues
    WHEN  an operator runs `fr apply --yes` simultaneously with the bridge's
          tick (both call apply() on overlapping mutations)
    THEN  the final gh state matches what either path alone would produce
    AND   no Issue ends up with duplicate labels
    AND   no Issue ends up with conflicting state
    (Both paths use the same render → diff → apply chain; apply() is
    idempotent by construction. This test is a regression guard.)
    """
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.apply import apply
    from fr.diff import diff
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    from tests.unit.fakes import FakeGhClient, FakeMcpClient

    plan = parse(MINIMAL)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/77"}
            )
        }
    )
    plan = dc_replace(
        plan, phases=(phase,), meta=plan.meta.model_copy(update={"target_repo": repo})
    )

    gh = FakeGhClient()
    # Pre-register managed labels so both apply() chains succeed without
    # racing on ensure_labels.
    gh.repo_labels[repo] = {
        "fr:ready",
        "fr:blocked",
        "fr:synced",
        "in-progress",
        "pr-ready",
        "manual",
        "plan:2026-05-09-fixture-minimal",
        "phase:1",
    }
    gh.add_issue(
        repo, 77, state="OPEN", labels={"fr:ready", "phase:1", "plan:2026-05-09-fixture-minimal"}
    )
    mcp = FakeMcpClient()

    # First: the bridge brings the plan to steady state (vk-synced on,
    # body in sync).
    tick(plan, gh, VkRunner(mcp))
    steady_labels = frozenset(gh.issues[(repo, 77)].labels)
    steady_state = gh.issues[(repo, 77)].state
    steady_body = gh.issues[(repo, 77)].body

    # Now race: operator-side `fr apply` projects the same render → diff,
    # which on a steady-state plan emits only the idempotent
    # RepoLabelEnsure (no per-issue diffs).
    rendered = render(plan, observe(plan, gh))
    op_diff = diff(rendered, observe(plan, gh), plan=plan)
    op_result = apply(op_diff, gh, plan=plan)
    assert op_result.failures == (), f"operator apply unexpectedly failed: {op_result.failures}"

    # Then the bridge ticks again, racing on the same plan.
    tick(plan, gh, VkRunner(mcp))

    # Final state matches steady-state byte-for-byte.
    assert frozenset(gh.issues[(repo, 77)].labels) == steady_labels
    assert gh.issues[(repo, 77)].state == steady_state
    assert gh.issues[(repo, 77)].body == steady_body
    # No duplicate vk-synced (set-typed in the fake, so trivially true,
    # but also no `vk-synced` removal occurred between the two apply
    # passes).
    assert "fr:synced" in gh.issues[(repo, 77)].labels
