from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_observe_undispatched_phase_returns_no_observation():
    from fr import parse
    from fr.observe import observe

    from tests.unit.fakes import FakeGhClient

    plan = parse(FIXTURE)
    gh = FakeGhClient()
    observed = observe(plan, gh)
    assert observed.phases == {}


def test_observe_dispatched_phase_returns_observation():
    """Phase with tracking_issue → observe builds PhaseObservation from gh state."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.observe import observe

    from tests.unit.fakes import FakeGhClient

    plan = parse(FIXTURE)
    # Inject a tracking_issue into phase 1
    repo = "derio-net/superpowers-for-vk"
    issue_url = f"https://github.com/{repo}/issues/142"
    phase = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": issue_url})}
    )
    new_plan = dc_replace(plan, phases=(phase,))

    gh = FakeGhClient()
    gh.add_issue(
        repo,
        142,
        state="OPEN",
        labels={"vk-ready", "phase:1"},
        assignees=("claude-bot",),
        linked_prs=[
            {
                "number": 200,
                "url": f"https://github.com/{repo}/pull/200",
                "state": "OPEN",
                "merged": False,
                "draft": False,
                "ci": "PASS",
            }
        ],
    )

    observed = observe(new_plan, gh)
    assert 1 in observed.phases
    obs = observed.phases[1]
    assert obs.issue_state == "OPEN"
    assert "vk-ready" in obs.issue_labels
    assert obs.issue_assignees == ("claude-bot",)
    assert len(obs.linked_prs) == 1
    pr = obs.linked_prs[0]
    assert pr.state == "OPEN"
    assert pr.merged is False
    assert pr.draft is False


def test_observe_populates_body_field():
    """PhaseObservation.body comes from gh's view_issue body field."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.observe import observe

    from tests.unit.fakes import FakeGhClient

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/77"}
            )
        }
    )
    new_plan = dc_replace(plan, phases=(phase,))

    gh = FakeGhClient()
    gh.add_issue(repo, 77, body="some body content")

    observed = observe(new_plan, gh)
    assert observed.phases[1].body == "some body content"


def test_observe_rejects_unexpected_issue_state():
    """gh returning a state outside OPEN/CLOSED → boundary validation error."""
    from dataclasses import replace as dc_replace

    import pytest
    from fr import parse
    from fr.observe import observe

    from tests.unit.fakes import FakeGhClient

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/77"}
            )
        }
    )
    new_plan = dc_replace(plan, phases=(phase,))

    gh = FakeGhClient()
    gh.add_issue(repo, 77, state="WEIRD_STATE")

    with pytest.raises(ValueError, match="unexpected Issue state"):
        observe(new_plan, gh)


def test_observe_skips_phases_without_tracking_issue():
    """Mixed dispatch state — observe returns only the dispatched phase."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.observe import observe

    from tests.unit.fakes import FakeGhClient

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    repo = "derio-net/superpowers-for-vk"
    # Only dispatch phase 2
    phases = list(plan.phases)
    phases[1] = phases[1].model_copy(
        update={
            "phase": phases[1].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/501"}
            )
        }
    )
    new_plan = dc_replace(plan, phases=tuple(phases))

    gh = FakeGhClient()
    gh.add_issue(repo, 501, state="OPEN", labels={"vk-ready"})

    observed = observe(new_plan, gh)
    assert set(observed.phases.keys()) == {2}
