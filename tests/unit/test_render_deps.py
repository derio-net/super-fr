"""Tests for renderer dependency gating (Group A from the v2 bridge rebuild spec).

All six tests are INITIALLY RED — `_lifecycle_label` doesn't know about deps yet.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

MULTI_PHASE = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"


def _make_plan_with_phases(phases_data):
    """Build a plan in-memory from the multi-phase fixture, replacing phases."""
    from vk import parse

    plan = parse(MULTI_PHASE)
    return dc_replace(plan, phases=tuple(phases_data))


def _complete_phase_1(plan):
    """Return plan with phase 1 marked complete (completion.at set)."""
    p1 = next(p for p in plan.phases if p.phase.number == 1)
    p1_complete = p1.model_copy(
        update={
            "state": p1.state.model_copy(
                update={
                    "completion": p1.state.completion.model_copy(
                        update={"at": "2026-05-17T10:00:00Z", "note": "done"}
                    )
                }
            )
        }
    )
    return dc_replace(
        plan, phases=tuple(p1_complete if p.phase.number == 1 else p for p in plan.phases)
    )


def test_phase_with_unsatisfied_deps_projects_vk_blocked():
    """
    GIVEN a plan with two phases — phase 1 (depends_on=[]) and phase 2
          (depends_on=[1]) — neither dispatched
    WHEN  render(plan, observed=empty) is called
    THEN  rendered.issue_per_phase[1].labels contains 'vk-ready'
    AND   rendered.issue_per_phase[2].labels contains 'vk-blocked'
    AND   rendered.issue_per_phase[2].labels does NOT contain 'vk-ready'
    """
    from vk import parse
    from vk.render import render
    from vk.states import GhState

    plan = parse(MULTI_PHASE)
    observed = GhState(phases={})
    rendered = render(plan, observed)

    label_names_1 = {ld.name for ld in rendered.issue_per_phase[1].labels}
    label_names_2 = {ld.name for ld in rendered.issue_per_phase[2].labels}

    assert "vk-ready" in label_names_1
    assert "vk-blocked" in label_names_2
    assert "vk-ready" not in label_names_2


def test_phase_with_satisfied_deps_projects_vk_ready():
    """
    GIVEN a plan with phases 1 (depends_on=[]) and 2 (depends_on=[1])
    AND   phase 1's tracking_issue is observed as CLOSED with a merged PR
    AND   phase 1's state.completion.at is set
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[2].labels contains 'vk-ready'
    AND   does NOT contain 'vk-blocked'
    """
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(MULTI_PHASE)
    plan = _complete_phase_1(plan)

    # Phase 1 observed as closed with a merged PR
    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="CLOSED",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(
                    PrObservation(
                        url="https://github.com/derio-net/superpowers-for-vk/pull/99",
                        state="CLOSED",
                        merged=True,
                        draft=False,
                        ci="PASS",
                    ),
                ),
            )
        }
    )
    rendered = render(plan, observed)

    label_names_2 = {ld.name for ld in rendered.issue_per_phase[2].labels}
    assert "vk-ready" in label_names_2
    assert "vk-blocked" not in label_names_2


def test_blocked_to_ready_transition_when_dep_completes():
    """
    GIVEN phase 2 currently labelled vk-blocked (because phase 1 was incomplete)
    WHEN  phase 1 completes (observed: closed + merged PR; state.completion.at set)
    AND   diff(rendered, observed, plan) is computed
    THEN  the mutation list contains an IssueLabelChange that removes
          'vk-blocked' AND adds 'vk-ready' on phase 2's tracking issue
    """
    from vk import parse
    from vk.diff import IssueLabelChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(MULTI_PHASE)
    plan = _complete_phase_1(plan)

    # Give phase 2 a tracking_issue so diff emits IssueLabelChange (not IssueCreate)
    p2 = next(p for p in plan.phases if p.phase.number == 2)
    p2_with_issue = p2.model_copy(
        update={
            "phase": p2.phase.model_copy(
                update={
                    "tracking_issue": "https://github.com/derio-net/superpowers-for-vk/issues/200"
                }
            )
        }
    )
    plan = dc_replace(
        plan,
        phases=tuple(p2_with_issue if p.phase.number == 2 else p for p in plan.phases),
    )

    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="CLOSED",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(
                    PrObservation(
                        url="https://github.com/derio-net/superpowers-for-vk/pull/99",
                        state="CLOSED",
                        merged=True,
                        draft=False,
                        ci="PASS",
                    ),
                ),
            ),
            2: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"vk-blocked"}),
                issue_assignees=(),
                linked_prs=(),
            ),
        }
    )

    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    label_changes = [m for m in d.mutations if isinstance(m, IssueLabelChange)]
    phase2_changes = [m for m in label_changes if m.issue_number == 200]
    assert phase2_changes, "expected IssueLabelChange for phase 2"
    change = phase2_changes[0]
    assert "vk-ready" in change.add
    assert "vk-blocked" in change.remove


def test_fan_in_phase_blocked_until_all_deps_complete():
    """
    GIVEN a plan where phase 4 has depends_on=[1, 2, 3]
    AND   phases 1 and 2 are complete; phase 3 is in-progress
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[4].labels contains 'vk-blocked'

    GIVEN the same state but with phase 3 now complete
    WHEN  render(plan, observed) is called again
    THEN  rendered.issue_per_phase[4].labels contains 'vk-ready'
    """
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(MULTI_PHASE)

    def _make_phase(number, depends_on, complete=False, tag="agentic"):
        step_id = f"P{number}.T1.S1"
        from vk.types import (
            Completion,
            PhaseDoc,
            PhaseHeader,
            PhaseStateBlock,
            Step,
            StepState,
            Task,
        )

        return PhaseDoc(
            schema_version=2,
            phase=PhaseHeader(
                number=number,
                title=f"Phase {number}",
                tag=tag,
                depends_on=tuple(depends_on),
                tracking_issue=None,
            ),
            tasks=(
                Task(
                    number=1,
                    title="t",
                    steps=(Step(id=step_id, text="s"),),
                ),
            ),
            state=PhaseStateBlock(
                steps={
                    step_id: StepState(
                        state="-" if complete else " ",
                        ticked_at=None,
                        note=None,
                    )
                },
                completion=Completion(
                    at="2026-05-17T10:00:00Z" if complete else None,
                    note="done" if complete else None,
                    observed_prs=(),
                ),
            ),
        )

    phases = (
        _make_phase(1, [], complete=True),
        _make_phase(2, [1], complete=True),
        _make_phase(3, [1, 2], complete=False),
        _make_phase(4, [1, 2, 3], complete=False),
    )
    plan = dc_replace(plan, phases=phases)

    merged_pr = PrObservation(
        url="https://github.com/x/y/pull/1",
        state="CLOSED",
        merged=True,
        draft=False,
        ci="PASS",
    )
    obs_complete = PhaseObservation(
        issue_state="CLOSED",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(merged_pr,),
    )
    obs_inprogress = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset({"in-progress"}),
        issue_assignees=("agent",),
        linked_prs=(),
    )

    # phase 3 incomplete → phase 4 blocked
    observed = GhState(phases={1: obs_complete, 2: obs_complete, 3: obs_inprogress})
    rendered = render(plan, observed)
    label_names_4 = {ld.name for ld in rendered.issue_per_phase[4].labels}
    assert "vk-blocked" in label_names_4

    # phase 3 also complete → phase 4 ready
    plan3_complete = dc_replace(
        plan,
        phases=tuple(
            _make_phase(p.phase.number, list(p.phase.depends_on), complete=True)
            if p.phase.number == 3
            else p
            for p in plan.phases
        ),
    )
    obs3_complete = PhaseObservation(
        issue_state="CLOSED",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(merged_pr,),
    )
    observed2 = GhState(phases={1: obs_complete, 2: obs_complete, 3: obs3_complete})
    rendered2 = render(plan3_complete, observed2)
    label_names_4b = {ld.name for ld in rendered2.issue_per_phase[4].labels}
    assert "vk-ready" in label_names_4b
    assert "vk-blocked" not in label_names_4b


def test_manual_phase_unaffected_by_dep_gating():
    """
    GIVEN a manual-tagged phase with depends_on=[1] and phase 1 incomplete
    WHEN  render() is called
    THEN  the phase projects 'manual' lifecycle label (not 'vk-blocked')
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.render import render
    from vk.states import GhState
    from vk.types import (
        Completion,
        PhaseDoc,
        PhaseHeader,
        PhaseStateBlock,
        Step,
        StepState,
        Task,
    )

    plan = parse(MULTI_PHASE)

    # Replace phase 2 with a manual-tagged phase that depends on phase 1
    manual_phase = PhaseDoc(
        schema_version=2,
        phase=PhaseHeader(
            number=2,
            title="Manual review step",
            tag="manual",
            depends_on=(1,),
            tracking_issue=None,
        ),
        tasks=(
            Task(
                number=1,
                title="t",
                steps=(Step(id="P2.T1.S1", text="s"),),
            ),
        ),
        state=PhaseStateBlock(
            steps={"P2.T1.S1": StepState(state="-", ticked_at=None, note=None)},
            completion=Completion(at=None, note=None, observed_prs=()),
        ),
    )
    plan = dc_replace(
        plan,
        phases=tuple(manual_phase if p.phase.number == 2 else p for p in plan.phases),
    )

    # Phase 1 incomplete (no completion.at)
    observed = GhState(phases={})
    rendered = render(plan, observed)

    label_names_2 = {ld.name for ld in rendered.issue_per_phase[2].labels}
    assert "manual" in label_names_2
    assert "vk-blocked" not in label_names_2


def test_bad_dep_reference_treated_as_blocked():
    """
    GIVEN a plan with phase 2 having depends_on=[99] (no phase 99 exists)
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[2].labels contains 'vk-blocked'
          (conservative: bad reference = treat as never-satisfiable)
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.render import render
    from vk.states import GhState

    plan = parse(MULTI_PHASE)

    p2 = next(p for p in plan.phases if p.phase.number == 2)
    p2_bad_dep = p2.model_copy(update={"phase": p2.phase.model_copy(update={"depends_on": (99,)})})
    plan = dc_replace(
        plan,
        phases=tuple(p2_bad_dep if p.phase.number == 2 else p for p in plan.phases),
    )

    observed = GhState(phases={})
    rendered = render(plan, observed)

    label_names_2 = {ld.name for ld in rendered.issue_per_phase[2].labels}
    assert "vk-blocked" in label_names_2
