"""Integration tests for bridge resilience properties.

These tests pin invariants that must hold even under operator interference
or concurrent writers: I7 (renderer is source of truth for labels) and I8
(`fr apply` and `fr_dispatch.tick` racing for the same plan).
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

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

    from tests.unit.fakes import FakeGhClient
    from tests.unit.test_tick_workitem import FakeRunner

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

    # First: the bridge brings the plan to steady state (vk-synced on,
    # body in sync).
    tick(plan, gh, FakeRunner())
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
    tick(plan, gh, FakeRunner())

    # Final state matches steady-state byte-for-byte.
    assert frozenset(gh.issues[(repo, 77)].labels) == steady_labels
    assert gh.issues[(repo, 77)].state == steady_state
    assert gh.issues[(repo, 77)].body == steady_body
    # No duplicate vk-synced (set-typed in the fake, so trivially true,
    # but also no `vk-synced` removal occurred between the two apply
    # passes).
    assert "fr:synced" in gh.issues[(repo, 77)].labels
