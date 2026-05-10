from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_render_undispatched_phase_yields_create_intent():
    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState

    plan = parse(FIXTURE)
    observed = GhState(phases={})
    rendered = render(plan, observed)

    assert 1 in rendered.issue_per_phase
    issue = rendered.issue_per_phase[1]
    assert issue.state == "OPEN"
    assert "spec:vk-rebuild-state-machine-design" in issue.labels
    assert "plan:2026-05-09-fixture-minimal" in issue.labels
    assert "phase:1" in issue.labels
    assert "vk-ready" in issue.labels  # agentic, no assignee, no PR, not complete
    assert rendered.archive_decision is False


@pytest.mark.parametrize(
    "obs_kwargs,expected_label",
    [
        # No observation (phase undispatched) -> vk-ready
        (None, "vk-ready"),
        # Empty observation -> vk-ready
        (
            {
                "issue_state": "OPEN",
                "issue_labels": frozenset(),
                "issue_assignees": (),
                "linked_prs": (),
            },
            "vk-ready",
        ),
        # Has assignee -> in-progress
        (
            {
                "issue_state": "OPEN",
                "issue_labels": frozenset(),
                "issue_assignees": ("claude-bot",),
                "linked_prs": (),
            },
            "in-progress",
        ),
        # Open draft PR -> in-progress
        (
            {
                "issue_state": "OPEN",
                "issue_labels": frozenset(),
                "issue_assignees": (),
                "linked_prs": (
                    ("https://gh/...", "OPEN", False, True, "PASS"),  # draft
                ),
            },
            "in-progress",
        ),
        # Open non-draft PR -> pr-ready
        (
            {
                "issue_state": "OPEN",
                "issue_labels": frozenset(),
                "issue_assignees": (),
                "linked_prs": (
                    ("https://gh/...", "OPEN", False, False, "PASS"),  # ready
                ),
            },
            "pr-ready",
        ),
    ],
)
def test_lifecycle_label_projection(obs_kwargs, expected_label):
    from vk.v2 import parse
    from vk.v2.render import _lifecycle_label
    from vk.v2.states import PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    obs = None
    if obs_kwargs is not None:
        prs = tuple(PrObservation(*pr) for pr in obs_kwargs["linked_prs"])
        obs = PhaseObservation(
            issue_state=obs_kwargs["issue_state"],
            issue_labels=obs_kwargs["issue_labels"],
            issue_assignees=obs_kwargs["issue_assignees"],
            linked_prs=prs,
        )
    assert _lifecycle_label(plan.phases[0], obs) == expected_label


def test_agentic_phase_complete_when_all_steps_ticked_and_pr_merged():
    from vk.v2 import parse
    from vk.v2.render import _phase_complete
    from vk.v2.states import PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    # No PR observed → not complete
    obs_no_pr = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(),
    )
    assert _phase_complete(plan.phases[0], obs_no_pr) is False

    # Open PR → not complete (PR still in flight)
    obs_open_pr = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),),
    )
    assert _phase_complete(plan.phases[0], obs_open_pr) is False

    # Steps ticked + merged PR + no open PR → complete
    ticked = plan.phases[0].model_copy(
        update={
            "state": plan.phases[0].state.model_copy(
                update={
                    "steps": {
                        "P1.T1.S1": plan.phases[0]
                        .state.steps["P1.T1.S1"]
                        .model_copy(update={"state": "x"})
                    }
                }
            )
        }
    )
    obs_merged = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),),
    )
    assert _phase_complete(ticked, obs_merged) is True


def test_manual_phase_complete_requires_completion_at_and_note():
    from vk.v2 import parse
    from vk.v2.render import _phase_complete

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    manual = next(p for p in plan.phases if p.phase.tag == "manual")

    # No completion → not complete
    assert _phase_complete(manual, None) is False

    # Set completion.at but no note → not complete
    with_at_only = manual.model_copy(
        update={
            "state": manual.state.model_copy(
                update={
                    "completion": manual.state.completion.model_copy(
                        update={"at": "2026-05-10T12:00:00Z"}
                    )
                }
            )
        }
    )
    assert _phase_complete(with_at_only, None) is False

    # Set both at + note → complete (steps don't matter for manual)
    full = manual.model_copy(
        update={
            "state": manual.state.model_copy(
                update={
                    "completion": manual.state.completion.model_copy(
                        update={"at": "2026-05-10T12:00:00Z", "note": "ran the runbook"}
                    )
                }
            )
        }
    )
    assert _phase_complete(full, None) is True


def test_drift_warning_steps_ticked_pr_not_merged():
    """All steps ticked but no merged PR → warning surfaces."""
    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState, PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    ticked = plan.phases[0].model_copy(
        update={
            "state": plan.phases[0].state.model_copy(
                update={
                    "steps": {
                        "P1.T1.S1": plan.phases[0]
                        .state.steps["P1.T1.S1"]
                        .model_copy(update={"state": "x"})
                    }
                }
            )
        }
    )
    from dataclasses import replace as dc_replace

    new_plan = dc_replace(plan, phases=(ticked,))
    obs = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),),
    )
    rendered = render(new_plan, GhState(phases={1: obs}))
    assert any("ticked" in w.lower() and "merged" in w.lower() for w in rendered.warnings)


def test_drift_warning_pr_merged_steps_unticked():
    """Merged PR but steps unticked → warning surfaces."""
    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState, PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    obs = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),),
    )
    rendered = render(plan, GhState(phases={1: obs}))
    assert any("merged" in w.lower() and "unticked" in w.lower() for w in rendered.warnings)


def test_drift_warning_issue_closed_plan_incomplete():
    """Issue closed externally while plan still incomplete → warning."""
    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    obs = PhaseObservation(
        issue_state="CLOSED",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(),
    )
    rendered = render(plan, GhState(phases={1: obs}))
    assert any("closed" in w.lower() and "incomplete" in w.lower() for w in rendered.warnings)


def test_archive_decision_true_when_all_phases_complete():
    """All phases complete → archive_decision True."""
    from dataclasses import replace as dc_replace

    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)

    completed_phases = []
    for p in plan.phases:
        if p.phase.tag == "manual":
            new_completion = p.state.completion.model_copy(
                update={"at": "2026-05-10T12:00:00Z", "note": "done"}
            )
        else:
            new_completion = p.state.completion.model_copy(update={"at": "2026-05-10T12:00:00Z"})
        completed_phases.append(
            p.model_copy(
                update={"state": p.state.model_copy(update={"completion": new_completion})}
            )
        )
    new_plan = dc_replace(plan, phases=tuple(completed_phases))

    rendered = render(new_plan, GhState(phases={}))
    assert rendered.archive_decision is True


def test_archive_decision_false_when_any_phase_incomplete():
    from vk.v2 import parse
    from vk.v2.render import render
    from vk.v2.states import GhState

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    rendered = render(plan, GhState(phases={}))
    assert rendered.archive_decision is False


def test_manual_phase_label_is_manual():
    """A phase with tag=manual gets the manual lifecycle label, not vk-ready."""
    from vk.v2 import parse
    from vk.v2.render import _lifecycle_label

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    # Phase 10 in this fixture is tagged manual
    manual_phase = next(p for p in plan.phases if p.phase.tag == "manual")
    assert _lifecycle_label(manual_phase, None) == "manual"
