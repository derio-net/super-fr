"""Integration tests for bridge resilience properties.

These tests pin invariants that must hold even under operator interference
or partial failures. Phase 1 covers I7 (renderer is source of truth for
labels). Later phases add I1-I6, I8.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

MULTI_PHASE = Path(__file__).parent.parent / "unit" / "fixtures" / "v2_plan_multi_phase"


def test_renderer_reverses_manual_label_change():
    """
    GIVEN a phase whose Issue has been observed in steady state with vk-ready
    AND   an operator manually removes vk-ready via `gh issue edit`
    WHEN  render() + diff() run again (simulating next bridge tick)
    THEN  the renderer projects vk-ready (state-machine says it's still ready)
    AND   the diff layer emits IssueLabelChange(add={vk-ready})
    AND   apply restores the label
    (Renderer projection IS the source of truth. If operators want a phase
    out of the dispatch queue, they update plan state — not labels.)
    """
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueLabelChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

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
    rendered_ref = render(plan, GhState(phases={}))
    ref_labels = {ld.name for ld in rendered_ref.issue_per_phase[1].labels}

    # Operator manually removes vk-ready from the observed state
    observed_after_op = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(ref_labels - {"vk-ready"}),  # vk-ready gone
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )

    # Simulate next tick: render from plan state (not operator-edited observed)
    rendered = render(plan, observed_after_op)

    # Renderer still projects vk-ready (plan state is authoritative)
    label_names = {ld.name for ld in rendered.issue_per_phase[1].labels}
    assert "vk-ready" in label_names

    # diff sees the gap and emits a label change to restore vk-ready
    d = diff(rendered, observed_after_op, plan=plan)
    label_changes = [m for m in d.mutations if isinstance(m, IssueLabelChange)]
    assert any("vk-ready" in m.add for m in label_changes), (
        "expected IssueLabelChange adding vk-ready back"
    )

    # apply restores it
    gh = FakeGhClient()
    gh.ensure_labels("derio-net/superpowers-for-vk", ["vk-ready"])
    gh.add_issue(
        "derio-net/superpowers-for-vk", 500, state="OPEN", labels=ref_labels - {"vk-ready"}
    )
    result = apply(d, gh, plan=plan)
    assert result.failures == (), f"unexpected failures: {result.failures}"
    assert "vk-ready" in gh.issues[("derio-net/superpowers-for-vk", 500)].labels
