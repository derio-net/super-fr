"""The bridge dispatches a plan at the plan's OWN shape (spec §4.A.1, Phase 12).

`bridge_cli.py` had been byte-unchanged for this whole branch by design;
this is the one authorized change to it. Everything these tests care
about is confined to the `_tick` call site:

- `workflow=` and `required_capabilities=` are now DERIVED from the plan's
  `_meta.yaml` shape reference instead of riding `tick`'s built-in default.
- A plan with no `workflow:` key resolves `FR_GOAL_PHASE_DISPATCH` — the
  live-bridge back-compat that lets the daemon keep ticking every existing
  plan through the upgrade. Tested, not assumed.
- A plan whose shape does not resolve fails THAT PLAN inside the existing
  I9 error boundary. The daemon logs, meters and moves to the next plan;
  it never goes down. That daemon runs in production against real repos.

The flock, the bridge-owned checkout sync (#286), the metrics wire format
and the two state files are untouched, and no test here asserts anything
about them.
"""

from __future__ import annotations

import logging
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.fakes import FakeGhClient
from tests.unit.test_tick_workitem import FakeRunner, _one_phase_plan, _ready

BROWSER_SHAPE_YAML = """\
workflow: browser-dispatch
schema: 1
unit: phase
requires: [git, browser]
steps:
  - id: implement
    kind: agent
    needs: [spec, plan]
    emits: [pr]
"""
"""`requires` deliberately differs from FR_GOAL_PHASE_DISPATCH's
{git, tests, scm} — and from `FakeRunner.capabilities` ({git, scm}) — so a
refusal here can only come from the PLAN's shape being read."""


def _shaped_plan(repo_root: Path, *, workflow: str | None, shape_yaml: str | None = None):
    """The one-phase fixture plan, rooted in `repo_root`, naming `workflow`."""
    plan, repo, number = _one_phase_plan()
    if shape_yaml is not None:
        d = repo_root / "docs" / "superpowers" / "workflows"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{workflow}.yaml").write_text(shape_yaml)
    plan = dc_replace(
        plan,
        repo_root=repo_root,
        meta=plan.meta.model_copy(update={"workflow": workflow}),
    )
    return plan, repo, number


class _StubMcp:
    def list_workspaces(self, **kw: Any) -> list[Any]:
        return []

    def list_issues(self, **kw: Any) -> list[Any]:
        return []

    def close(self) -> None:
        pass


def _run_bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    plans: list[Any],
    gh: Any,
    runner: Any = None,
    tick_impl: Any = None,
    reasons: list[str] | None = None,
) -> int:
    """Drive one whole `bridge_cli.main()` tick over `plans`.

    Everything outside the plan loop is stubbed; `_tick` itself is left
    REAL unless `tick_impl` is given, so the capability refusal under test
    is the production chain, not a re-implementation of it.
    """
    from fr_vk import bridge_cli

    repo_path = tmp_path / "repo"
    repo_path.mkdir(exist_ok=True)

    monkeypatch.setenv("FR_BRIDGE_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(bridge_cli, "_DONE_CLOSED_PATH", tmp_path / "done.json")
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [repo_path])
    monkeypatch.setattr(
        bridge_cli, "_ensure_bridge_checkout", lambda configured, name, base=None: repo_path
    )
    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", lambda p: False)
    monkeypatch.setattr(bridge_cli, "_repo_owner_name", lambda p: "example/repo")
    monkeypatch.setattr(bridge_cli, "discover_plans", lambda repo, g: plans)
    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: gh)
    if runner is not None:
        monkeypatch.setattr(bridge_cli, "VkRunner", lambda mcp, project_id=None: runner)
    if tick_impl is not None:
        monkeypatch.setattr(bridge_cli, "_tick", tick_impl)
    monkeypatch.setattr(bridge_cli, "observe_pr_status", lambda mcp, project_id=None: {})
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda *a, **k: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda *a, **k: None)
    monkeypatch.setattr(bridge_cli, "reconcile_done_issues", lambda *a, **k: set())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    sink = reasons if reasons is not None else []
    monkeypatch.setattr(
        bridge_cli._metrics, "push_failure_total", lambda *, reason: sink.append(reason)
    )
    monkeypatch.setattr(bridge_cli._metrics, "push_sync_total", lambda: None)

    return bridge_cli.main([])


# ── what the bridge now passes ─────────────────────────────────────────


def test_the_bridge_passes_the_plans_own_shape_and_its_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr_dispatch import TickResult

    plan, _, _ = _shaped_plan(tmp_path, workflow="browser-dispatch", shape_yaml=BROWSER_SHAPE_YAML)
    seen: dict[str, Any] = {}

    def _spy(p: Any, gh: Any, runner: Any, **kw: Any) -> TickResult:
        seen.update(kw)
        return TickResult(synced=0, errors=0, skipped=0, failures=())

    rc = _run_bridge(monkeypatch, tmp_path, plans=[plan], gh=FakeGhClient(), tick_impl=_spy)

    assert rc == 0
    assert seen["workflow"].workflow == "browser-dispatch"
    assert seen["workflow"].requires == ("git", "browser")
    assert seen["required_capabilities"] == frozenset({"git", "browser"})
    # Untouched at this call site — the metrics wire is part of the
    # minimal-diff contract.
    assert "metrics" in seen


def test_a_plan_with_no_shape_reference_still_ticks_at_todays_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live-bridge upgrade path: every plan merged before Phase 12 has
    no `workflow:` key, and must dispatch exactly as it did yesterday."""
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH
    from fr_dispatch import TickResult

    plan, _, _ = _shaped_plan(tmp_path, workflow=None)
    seen: dict[str, Any] = {}

    def _spy(p: Any, gh: Any, runner: Any, **kw: Any) -> TickResult:
        seen.update(kw)
        return TickResult(synced=1, errors=0, skipped=0, failures=())

    rc = _run_bridge(monkeypatch, tmp_path, plans=[plan], gh=FakeGhClient(), tick_impl=_spy)

    assert rc == 0
    assert seen["workflow"] is FR_GOAL_PHASE_DISPATCH
    # The VK runner's own capabilities are exactly these, so passing them
    # changes nothing for an existing plan — which is the point.
    assert seen["required_capabilities"] == frozenset({"git", "tests", "scm"})


# ── the refusal, through the real tick ─────────────────────────────────


def test_a_runner_lacking_the_shapes_capability_refuses_the_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Real `fr_dispatch.tick`, real capability chain (Phase 5): the plan's
    shape requires `browser`, the runner has {git, scm}, so every eligible
    item fails with one message, synced=0, and `dispatch` is never called."""
    plan, repo, number = _shaped_plan(
        tmp_path, workflow="browser-dispatch", shape_yaml=BROWSER_SHAPE_YAML
    )
    gh = FakeGhClient()
    _ready(gh, plan, repo, (number,))
    runner = FakeRunner()  # capabilities = {"git", "scm"} — no "browser"

    with caplog.at_level("INFO", logger="vk-issue-bridge"):
        rc = _run_bridge(monkeypatch, tmp_path, plans=[plan], gh=gh, runner=runner)

    assert rc == 0
    assert runner.dispatched == []
    # The capability check short-circuits BEFORE preflight (Phase 5's chain).
    assert runner.preflight_items is None
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "synced=0 errors=1 skipped=1" in log, log


def test_a_plan_whose_shape_does_not_resolve_fails_only_that_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """I9: the daemon must survive it. The broken plan is counted as an
    error and the next plan still ticks — a resolution failure is not an
    excuse to take a production daemon down."""
    from fr_dispatch import TickResult

    broken, _, _ = _shaped_plan(tmp_path, workflow="no-such-shape")
    healthy, _, _ = _shaped_plan(tmp_path, workflow=None)
    ticked: list[Any] = []
    reasons: list[str] = []

    def _spy(p: Any, gh: Any, runner: Any, **kw: Any) -> TickResult:
        ticked.append(p)
        return TickResult(synced=1, errors=0, skipped=0, failures=())

    with caplog.at_level("INFO", logger="vk-issue-bridge"):
        rc = _run_bridge(
            monkeypatch,
            tmp_path,
            plans=[broken, healthy],
            gh=FakeGhClient(),
            tick_impl=_spy,
            reasons=reasons,
        )

    assert rc == 0
    # The broken plan never reached tick; the healthy one did.
    assert ticked == [healthy]
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "tick raised; continuing" in log, log
    assert "summary: 1 plan(s) ticked, 1 synced, 1 errors" in log, log
    # Reported through the EXISTING per-plan failure metric — no new
    # channel, and the reason names the shape so an operator can fix it.
    assert len(reasons) == 1, reasons
    assert reasons[0].startswith("plan_error:v2_plan_minimal:"), reasons
    assert "no-such-shape" in reasons[0], reasons


RUN_SHAPE_YAML = """\
workflow: run-dispatch
schema: 1
unit: run
requires: [git]
steps:
  - id: implement
    kind: agent
    emits: [pr]
"""


def test_a_plan_naming_a_run_unit_shape_is_refused_for_want_of_a_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """KNOWN GAP, pinned rather than described.

    Phase 12 makes the dispatcher read the granularity off the plan's
    shape instead of a hardcoded constant — but only `unit: phase` is
    actually reachable through the bridge. A `unit: run` shape needs a run
    id (`fr run start`), and plan discovery has no run identity to give it;
    a `unit: spec` shape needs a `SpecMeta` source, and `discover_plans`
    yields `Plan`s only.

    So the failure below is the honest state of the `unit` axis at the
    bridge: per-plan, counted, dispatch-free — not a silent dispatch at the
    wrong granularity. Whoever gives the bridge a run identity should delete
    this test and flip the `dispatch-unit-declared-by-shape` acceptance row.

    It reaches the bridge as an ACCUMULATED tick failure rather than a raise
    into the I9 boundary (review fix r2-f9): `tick` promises "all failure
    paths accumulate" and `_eligible_items` calls `build_items` outside any
    `try`, so raising there took the whole cron iteration with it instead of
    one plan. The failure STRING is asserted where it is produced
    (`test_item_graph.py`, `test_tick_workitem.py`); what belongs here is
    that a whole `bridge_cli.main()` survives it, dispatches nothing, and
    counts exactly one error against this plan.
    """
    plan, repo, number = _shaped_plan(tmp_path, workflow="run-dispatch", shape_yaml=RUN_SHAPE_YAML)
    gh = FakeGhClient()
    # The plan's phase Issues are in steady state: `tick` runs the GitHub
    # phase projection for ANY `Plan` source before the shape's `unit` is
    # ever consulted, so without this the run-unit failure below would be
    # masked by an observe() KeyError.
    _ready(gh, plan, repo, (number,))
    runner = FakeRunner()

    with caplog.at_level(logging.INFO, logger="vk-issue-bridge"):
        rc = _run_bridge(monkeypatch, tmp_path, plans=[plan], gh=gh, runner=runner)

    assert rc == 0
    assert runner.dispatched == []
    assert [m for m in caplog.messages if "v2_plan_minimal: synced=0 errors=1" in m], (
        caplog.messages
    )
