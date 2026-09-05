"""Capability negotiation — §4.F of the 2026-08-14 workflow-shapes spec.

`CAPABILITIES` is the closed vocabulary a shape's `requires:` and a
`Runner.capabilities` both draw from (a typo is a validation error in
`fr workflow check`, Phase 6 — not exercised here). `missing_capabilities`
is the pure shortfall computation `fr_dispatch.tick` uses to refuse a
dispatch *before* `runner.preflight` runs, reusing the SAME per-item
failure-accumulation path preflight blockers already use (one message,
every eligible item fails, `synced=0`, `dispatch` never called).

Phase 6 seam (manifests do not exist yet): `tick(..., required_capabilities=
frozenset({...}))` is a keyword-only, empty-by-default parameter — Phase 6
resolves a shape's `requires:` and passes it through here. Phase 5 ships no
manifest reader; this test constructs the required set directly, as any
Phase-6 caller eventually will.
"""

from __future__ import annotations

from fr_dispatch.capabilities import CAPABILITIES, missing_capabilities

from tests.unit.fakes import FakeGhClient
from tests.unit.test_tick_workitem import FakeRunner, RecordingMetrics, _one_phase_plan, _ready

# ── (a) the closed set ──────────────────────────────────────────────────


def test_capabilities_is_the_closed_set():
    assert CAPABILITIES == frozenset({"git", "tests", "scm", "browser", "network", "devcontainer"})


def test_capabilities_is_immutable():
    assert isinstance(CAPABILITIES, frozenset)


# ── (b) missing_capabilities — pure shortfall ───────────────────────────


def test_missing_capabilities_returns_the_sorted_shortfall():
    assert missing_capabilities({"network", "browser", "git"}, {"git"}) == (
        "browser",
        "network",
    )


def test_missing_capabilities_is_empty_when_provided_is_a_superset():
    assert missing_capabilities({"git"}, {"git", "tests", "scm"}) == ()


def test_missing_capabilities_is_empty_when_nothing_is_required():
    assert missing_capabilities(set(), {"git"}) == ()


# ── (c) tick refuses EVERY eligible item with ONE message, synced=0 ────


def test_tick_refuses_when_the_runner_lacks_a_required_capability():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner()  # capabilities = {"git", "scm"} — no "browser"

    result = tick(plan, gh, runner, required_capabilities=frozenset({"browser"}), metrics=m)

    assert result.synced == 0
    assert result.errors == 1
    assert len(result.failures) == 1
    assert "browser" in result.failures[0]
    assert runner.name in result.failures[0]
    assert result.skipped == 1
    assert runner.dispatched == []
    # The capability check runs BEFORE runner.preflight — a capability
    # mismatch is a capability problem, not a config one, and preflight is
    # never reached (nor is dispatch).
    assert runner.preflight_items is None
    assert m.reasons == ["preflight"]
    assert m.heartbeats == 1


def test_tick_refusal_names_every_missing_capability_in_one_message():
    from fr_dispatch import tick

    from tests.unit.test_tick_workitem import REPO, _two_phase_plan

    plan = _two_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, REPO, (101, 102))
    m = RecordingMetrics()
    runner = FakeRunner()  # {"git", "scm"}

    result = tick(
        plan,
        gh,
        runner,
        required_capabilities=frozenset({"browser", "network"}),
        metrics=m,
    )

    assert result.synced == 0
    assert result.errors == 2
    assert len(result.failures) == 2
    for failure in result.failures:
        assert "browser" in failure
        assert "network" in failure
        assert runner.name in failure
    assert runner.dispatched == []
    assert m.reasons == ["preflight", "preflight"]


def test_a_missing_capability_is_reported_before_a_preflight_error_would_be():
    """Even a runner that WOULD also fail its own preflight() is refused
    on the capability message — preflight is never called to produce one."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner(preflight_error="unrelated runner config problem")

    result = tick(plan, gh, runner, required_capabilities=frozenset({"devcontainer"}))

    assert "devcontainer" in result.failures[0]
    assert "unrelated runner config problem" not in result.failures[0]
    assert runner.preflight_items is None


# ── (d) a superset of capabilities dispatches normally ──────────────────


def test_tick_dispatches_normally_when_runner_capabilities_are_a_superset():
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()  # {"git", "scm"} is a superset of {"git"}

    result = tick(plan, gh, runner, required_capabilities=frozenset({"git"}))

    assert result.synced == 1
    assert [i.id for i in runner.dispatched]
    assert runner.preflight_items is not None  # preflight DID run — no blocker


def test_tick_default_required_capabilities_is_empty_and_never_refuses():
    """No caller passing `required_capabilities` (every pre-Phase-6 caller,
    including the live bridge) must see no behavior change at all."""
    from fr_dispatch import tick

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    runner = FakeRunner()

    result = tick(plan, gh, runner)

    assert result.synced == 1
