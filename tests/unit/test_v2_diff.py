from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_diff_undispatched_yields_create():
    from vk import parse
    from vk.diff import IssueCreate, RepoLabelEnsure, diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    observed = GhState(phases={})
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    creates = [m for m in d.mutations if isinstance(m, IssueCreate)]
    assert len(creates) == 1
    assert creates[0].phase_number == 1
    assert "vk-ready" in creates[0].labels
    assert "phase:1" in creates[0].labels

    ensures = [m for m in d.mutations if isinstance(m, RepoLabelEnsure)]
    assert len(ensures) == 1
    assert "vk-ready" in ensures[0].labels


def test_diff_emits_issuebodychange_when_body_drifts():
    """Observed body differs from rendered → IssueBodyChange emitted."""
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import IssueBodyChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/142"}
            )
        }
    )
    new_plan = dc_replace(plan, phases=(phase,))

    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(),
                body="stale body that doesn't match what render produces",
            )
        }
    )
    rendered = render(new_plan, observed)
    d = diff(rendered, observed, plan=new_plan)
    body_changes = [m for m in d.mutations if isinstance(m, IssueBodyChange)]
    assert len(body_changes) == 1
    assert body_changes[0].issue_number == 142


def test_diff_observed_matches_rendered_yields_minimal_diff():
    """Already-dispatched, labels match → only RepoLabelEnsure (always emitted)."""
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import IssueCreate, IssueLabelChange, IssueStateChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/142"}
            )
        }
    )
    new_plan = dc_replace(plan, phases=(phase,))
    rendered = render(
        new_plan,
        GhState(
            phases={
                1: PhaseObservation(
                    issue_state="OPEN",
                    issue_labels=frozenset(
                        {
                            "vk-ready",
                            "spec:vk-rebuild-state-machine-design",
                            "plan:2026-05-09-fixture-minimal",
                            "phase:1",
                        }
                    ),
                    issue_assignees=(),
                    linked_prs=(),
                )
            }
        ),
    )
    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(
                    {
                        "vk-ready",
                        "spec:vk-rebuild-state-machine-design",
                        "plan:2026-05-09-fixture-minimal",
                        "phase:1",
                    }
                ),
                issue_assignees=(),
                linked_prs=(),
                body=rendered.issue_per_phase[1].body,  # in sync
            )
        }
    )
    d = diff(rendered, observed, plan=new_plan)

    # No IssueCreate / IssueLabelChange / IssueStateChange — all in sync
    assert not any(isinstance(m, IssueCreate) for m in d.mutations)
    assert not any(isinstance(m, IssueLabelChange) for m in d.mutations)
    assert not any(isinstance(m, IssueStateChange) for m in d.mutations)
