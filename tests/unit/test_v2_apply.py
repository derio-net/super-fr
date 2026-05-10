from dataclasses import replace as dc_replace
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan_with_extra_label():
    """Helper: parse FIXTURE, attach tracking_issue, return (plan, repo, issue_number)."""
    from vk.v2 import parse

    plan = parse(FIXTURE)
    repo = "derio-net/superpowers-for-vk"
    n = 142
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{n}"}
            )
        }
    )
    return dc_replace(plan, phases=(phase,)), repo, n


def test_apply_dry_run_calls_no_mutation_methods():
    """dry_run=True returns mutations without touching gh."""
    from tests.unit.fakes import FakeGhClient
    from vk.v2 import parse
    from vk.v2.apply import apply
    from vk.v2.diff import diff
    from vk.v2.render import render
    from vk.v2.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh, dry_run=True, yes=True)

    assert result.dry_run is True
    assert len(result.applied) == len(d.mutations)  # all mutations "applied" in dry run
    assert gh.calls == []  # but no real calls
    assert result.failures == ()


def test_apply_creates_issue_and_returns_url():
    from tests.unit.fakes import FakeGhClient
    from vk.v2 import parse
    from vk.v2.apply import apply
    from vk.v2.diff import diff
    from vk.v2.render import render
    from vk.v2.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh, yes=True)

    assert result.dry_run is False
    assert result.failures == ()
    assert 1 in result.created_issues
    assert result.created_issues[1].startswith("https://github.com/")


def test_apply_managed_labels_only_does_not_touch_operator_labels():
    """Pre-existing operator label like 'good-first-issue' must survive apply."""
    from tests.unit.fakes import FakeGhClient
    from vk.v2.apply import apply
    from vk.v2.diff import diff
    from vk.v2.render import render
    from vk.v2.states import GhState, PhaseObservation

    plan, repo, issue_n = _dispatched_plan_with_extra_label()

    # Pre-load an Issue with operator-added "good-first-issue" + a stale managed label
    gh = FakeGhClient()
    gh.add_issue(
        repo,
        issue_n,
        state="OPEN",
        labels={"good-first-issue", "vk-ready", "phase:1"},
        # missing spec:* and plan:* taxonomy labels — apply should add them
    )

    obs = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"good-first-issue", "vk-ready", "phase:1"}),
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )
    rendered = render(plan, obs)
    d = diff(rendered, obs, plan=plan)
    apply(d, gh, yes=True)

    # The unmanaged label survives
    assert "good-first-issue" in gh.issues[(repo, issue_n)].labels


def test_apply_idempotent_re_diff_after_apply_yields_no_mutations():
    """Apply once; re-observe; re-diff; assert empty mutations list."""
    from tests.unit.fakes import FakeGhClient
    from vk.v2 import parse
    from vk.v2.apply import apply
    from vk.v2.diff import RepoLabelEnsure, diff
    from vk.v2.observe import observe
    from vk.v2.render import render

    plan = parse(FIXTURE)
    gh = FakeGhClient()

    # First cycle — observed empty, render+diff+apply should create the Issue
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    result = apply(d, gh, yes=True)
    assert result.failures == ()
    new_url = result.created_issues[1]

    # Second cycle — must inject the new tracking_issue back into the plan model
    # (in production this is a write to the phase yaml; for test, mutate in memory)
    phase = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": new_url})}
    )
    plan2 = dc_replace(plan, phases=(phase,))

    observed2 = observe(plan2, gh)
    rendered2 = render(plan2, observed2)
    d2 = diff(rendered2, observed2, plan=plan2)

    # Only mutation that may remain is RepoLabelEnsure (it's always emitted).
    # No IssueCreate, IssueLabelChange, IssueBodyChange, or IssueStateChange.
    non_label = [m for m in d2.mutations if not isinstance(m, RepoLabelEnsure)]
    assert non_label == []


def test_apply_accumulates_failures_continues_past_one_bad_mutation():
    """Mutation N fails — mutation N+1 still runs; failure is recorded."""
    from tests.unit.fakes import FakeGhClient
    from vk.v2 import parse
    from vk.v2.apply import apply
    from vk.v2.diff import diff
    from vk.v2.render import render
    from vk.v2.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)
    assert len(d.mutations) >= 2  # need at least 2 to test "continue past failure"

    gh = FakeGhClient()
    gh.fail_on_mutation = 1  # second mutation fails

    result = apply(d, gh, yes=True)

    assert len(result.failures) == 1
    # Other mutations still applied
    assert len(result.applied) == len(d.mutations) - 1
