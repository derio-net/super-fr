from dataclasses import replace as dc_replace
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan_with_extra_label():
    """Helper: parse FIXTURE, attach tracking_issue, return (plan, repo, issue_number)."""
    from vk import parse

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
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh, dry_run=True)

    assert result.dry_run is True
    assert len(result.applied) == len(d.mutations)  # all mutations "applied" in dry run
    assert gh.calls == []  # but no real calls
    assert result.failures == ()


def test_apply_creates_issue_and_returns_url():
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    result = apply(d, gh)

    assert result.dry_run is False
    assert result.failures == ()
    assert 1 in result.created_issues
    assert result.created_issues[1].startswith("https://github.com/")


def test_apply_ensures_labels_with_registry_colors():
    """E2E: LabelDef objects with registry colors survive the trip through
    render → diff → apply → gh.ensure_labels. Diff-layer coverage is in
    test_v2_diff.test_repo_label_ensure_carries_registry_colors; this test
    catches a future regression where apply() or its sort/projection
    strips the colors off before handing them to the GhClient.
    """
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.labels import (
        PHASE_LABEL_COLOR,
        PLAN_LABEL_COLOR,
        SPEC_LABEL_COLOR,
        VK_READY,
        LabelDef,
    )
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    gh = FakeGhClient()
    apply(d, gh)

    ensure_calls = [c for c in gh.calls if c[0] == "ensure_labels"]
    assert len(ensure_calls) == 1
    [(_, kwargs)] = ensure_calls
    passed = kwargs["labels"]

    assert passed, "apply() called ensure_labels with an empty label list"
    non_defs = [ld for ld in passed if not isinstance(ld, LabelDef)]
    assert not non_defs, f"non-LabelDef in ensure_labels call: {non_defs}"

    by_name = {ld.name: ld for ld in passed}
    assert by_name["vk-ready"].color == VK_READY.color
    assert by_name["phase:1"].color == PHASE_LABEL_COLOR
    assert by_name["plan:2026-05-09-fixture-minimal"].color == PLAN_LABEL_COLOR
    assert by_name["spec:vk-rebuild-state-machine-design"].color == SPEC_LABEL_COLOR

    # Sort key invariant: apply() sorts by name (LabelDef has no natural order).
    passed_names = [ld.name for ld in passed]
    assert passed_names == sorted(passed_names)


def test_apply_managed_labels_only_does_not_touch_operator_labels():
    """Pre-existing operator label like 'good-first-issue' must survive apply."""
    from tests.unit.fakes import FakeGhClient
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

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
    apply(d, gh)

    final_labels = gh.issues[(repo, issue_n)].labels
    # The unmanaged label survives
    assert "good-first-issue" in final_labels
    # Managed labels were added (positive case)
    assert "spec:vk-rebuild-state-machine-design" in final_labels
    assert "plan:2026-05-09-fixture-minimal" in final_labels


def test_apply_idempotent_after_url_fillin_cycle():
    """Three cycles: create → fill-in URL body → no-op."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueBodyChange, RepoLabelEnsure, diff
    from vk.observe import observe
    from vk.render import render

    plan = parse(FIXTURE)
    gh = FakeGhClient()

    # Cycle 1 — observed empty, render+diff+apply creates the Issue
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    result = apply(d, gh)
    assert result.failures == ()
    new_url = result.created_issues[1]

    # Inject the now-known tracking_issue back into the plan model
    # (in production this is a write to the phase yaml; for test, mutate in memory)
    phase = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": new_url})}
    )
    plan2 = dc_replace(plan, phases=(phase,))

    # Cycle 2 — body now contains the real URL (was placeholder); diff
    # emits IssueBodyChange to bring observed up to date. This is the
    # URL-fill-in case from the diff.py docstring.
    observed2 = observe(plan2, gh)
    rendered2 = render(plan2, observed2)
    d2 = diff(rendered2, observed2, plan=plan2)
    body_changes = [m for m in d2.mutations if isinstance(m, IssueBodyChange)]
    assert len(body_changes) == 1, "Cycle 2 should fill in the URL via IssueBodyChange"
    apply(d2, gh)

    # Cycle 3 — true idempotent no-op. Only RepoLabelEnsure remains
    # (always emitted; no Issue mutations).
    observed3 = observe(plan2, gh)
    rendered3 = render(plan2, observed3)
    d3 = diff(rendered3, observed3, plan=plan2)
    non_label = [m for m in d3.mutations if not isinstance(m, RepoLabelEnsure)]
    assert non_label == [], f"Cycle 3 should be a no-op; got: {non_label}"


def test_apply_propagates_unhandled_mutation_type():
    """Programmer-error sentinel must NOT be swallowed as a failure."""
    import pytest

    from tests.unit.fakes import FakeGhClient
    from vk.apply import _UnhandledMutationError, apply
    from vk.diff import Diff

    class NovelMutation:
        """A mutation type apply() doesn't know about."""

        repo = "x/y"

    gh = FakeGhClient()
    d = Diff(mutations=(NovelMutation(),))  # type: ignore[arg-type]
    with pytest.raises(_UnhandledMutationError, match="NovelMutation"):
        apply(d, gh)


def test_fakegh_failed_mutation_not_recorded_in_calls():
    """When fail_on_mutation fires, the call is NOT recorded in .calls."""
    from tests.unit.fakes import FakeGhClient

    gh = FakeGhClient()
    gh.add_issue("o/r", 1)
    gh.fail_on_mutation = 0  # fail the first attempted mutation

    try:
        gh.edit_issue_labels("o/r", 1, add=frozenset({"x"}), remove=frozenset())
    except Exception:
        pass

    # Failed mutation NOT in .calls; attempted_mutations counts it
    assert gh.calls == []
    assert gh.attempted_mutations == 1


def test_apply_in_flight_dep_body_uses_predecessor_issue_number():
    """Two phases both being created in the same apply() run. After Phase 1's
    IssueCreate succeeds and returns URL .../issues/N, the IssueCreate that
    creates Phase 2 must use a body containing `- Blocked by #N` — the real
    Issue number, not the phase-number fallback.

    diff() ran when neither Phase had a tracking_issue, so the diff's
    initial Phase 2 IssueCreate body says `- Blocked by #1` (phase-number
    fallback). apply() must re-render that body after Phase 1's create
    lands and before Phase 2's create runs.
    """
    from pathlib import Path

    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueCreate, diff
    from vk.render import render
    from vk.states import GhState

    # Use the multi-phase fixture: Phase 2 depends on Phase 1.
    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)

    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    # Sanity: diff currently emits Phase 2 IssueCreate with the broken
    # phase-number fallback body, because no tracking_issue is set yet.
    creates_pre = [m for m in d.mutations if isinstance(m, IssueCreate)]
    phase2_pre = next(m for m in creates_pre if m.phase_number == 2)
    assert "- Blocked by #1" in phase2_pre.body, "fixture precondition"

    gh = FakeGhClient()
    # Make Phase 1's issue number ≠ 1 so the assertion isn't ambiguous with
    # the phase-number fallback `#1`.
    gh._next_issue_number[plan.meta.target_repo] = 50
    result = apply(d, gh, plan=plan)

    assert result.failures == ()
    phase1_url = result.created_issues[1]
    phase1_issue_n = int(phase1_url.rsplit("/", 1)[-1])
    assert phase1_issue_n == 50

    # The body Phase 2 was actually CREATED with (look at the create_issue
    # call recorded by the fake) must reference Phase 1's real Issue number.
    create_calls = [c for c in gh.calls if c[0] == "create_issue"]
    # Phase 1 is created first, Phase 2 second (mutations preserve order).
    phase2_create_call = next(c for c in create_calls if "Phase 2" in c[1]["title"])
    body_used = phase2_create_call[1]["body"]
    assert "- Blocked by #50" in body_used
    assert "- Blocked by #1" not in body_used


def test_apply_accumulates_failures_continues_past_one_bad_mutation():
    """Mutation N fails — mutation N+1 still runs; failure is recorded."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)
    assert len(d.mutations) >= 2  # need at least 2 to test "continue past failure"

    gh = FakeGhClient()
    gh.fail_on_mutation = 1  # second mutation fails

    result = apply(d, gh)

    assert len(result.failures) == 1
    # Other mutations still applied
    assert len(result.applied) == len(d.mutations) - 1
