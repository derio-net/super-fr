from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
CROSS_REPO = Path(__file__).parent / "fixtures" / "v2_plan_cross_repo"


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
    assert "vk-ready" in {ld.name for ld in ensures[0].labels}


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


def test_diff_passes_phase_to_issue_map_to_render():
    """End-to-end: when Phase 1 has a tracking_issue ending in /issues/100
    and Phase 2 depends_on=[1] but has no Issue yet, the IssueCreate body
    for Phase 2 must contain `- Blocked by #100`, NOT `- Blocked by #1`.
    """
    from dataclasses import replace as dc_replace
    from pathlib import Path

    from vk import parse
    from vk.diff import IssueCreate, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    phase1 = next(p for p in plan.phases if p.phase.number == 1)
    phase1_with_issue = phase1.model_copy(
        update={
            "phase": phase1.phase.model_copy(
                update={
                    "tracking_issue": "https://github.com/derio-net/superpowers-for-vk/issues/100"
                }
            )
        }
    )
    # Replace phase 1; leave phase 2 (depends_on=[1]) and phase 10 untouched
    new_phases = tuple(phase1_with_issue if p.phase.number == 1 else p for p in plan.phases)
    new_plan = dc_replace(plan, phases=new_phases)

    # Phase 1's Issue exists; Phase 2 + Phase 10 don't yet exist.
    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )
    rendered = render(new_plan, observed)
    d = diff(rendered, observed, plan=new_plan)

    creates = [m for m in d.mutations if isinstance(m, IssueCreate)]
    phase2_create = next(m for m in creates if m.phase_number == 2)
    assert "- Blocked by #100" in phase2_create.body
    assert "- Blocked by #1\n" not in phase2_create.body


def test_diff_swaps_stale_dated_labels_for_normalized_ones():
    """One-time churn on live Issues: an Issue still carrying the old dated /
    leading-dash labels (`plan:2026-…`, `spec:-…`) gets them removed and the
    normalized shapes added — both are under the vk-managed `plan:`/`spec:`
    prefixes, so the swap is safe and automatic at the next apply/tick."""
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import IssueLabelChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    plan = dc_replace(
        plan,
        meta=plan.meta.model_copy(
            update={
                "plan": "2026-05-27--auto--awx-deployment",
                "spec": "docs/superpowers/specs/2026-05-27--auto--awx-deployment-design.md",
            }
        ),
    )
    repo = "derio-net/superpowers-for-vk"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/142"}
            )
        }
    )
    plan = dc_replace(plan, phases=(phase,))

    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(
                    {
                        "plan:2026-05-27--auto--awx-deployment",
                        "spec:-auto--awx-deployment-design",
                        "phase:1",
                        "vk-ready",
                    }
                ),
                issue_assignees=(),
                linked_prs=(),
            )
        }
    )
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    label_changes = [m for m in d.mutations if isinstance(m, IssueLabelChange)]
    assert len(label_changes) == 1
    change = label_changes[0]
    assert "plan:auto--awx-deployment" in change.add
    assert "spec:auto--awx-deployment-design" in change.add
    assert "plan:2026-05-27--auto--awx-deployment" in change.remove
    assert "spec:-auto--awx-deployment-design" in change.remove


def test_repo_label_ensure_carries_registry_colors():
    """RepoLabelEnsure must carry LabelDef objects with the canonical registry
    colors / descriptions so gh.ensure_labels can paint each label correctly.

    Regression: v2 dispatch was creating every label as grey (`ededed`) with
    empty description because the diff layer passed plain strings to
    ensure_labels and the GhClient fallback wrapped them as default-grey
    LabelDefs.
    """
    from vk import parse
    from vk.diff import RepoLabelEnsure, diff
    from vk.labels import (
        IN_PROGRESS,
        MANUAL,
        PHASE_LABEL_COLOR,
        PLAN_LABEL_COLOR,
        PR_READY,
        SPEC_LABEL_COLOR,
        VK_READY,
        LabelDef,
    )
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    d = diff(rendered, GhState(phases={}), plan=plan)

    ensures = [m for m in d.mutations if isinstance(m, RepoLabelEnsure)]
    assert len(ensures) == 1
    [ensure] = ensures

    # Every label flowing into ensure_labels must be a fully-typed LabelDef,
    # not a bare string (which would force the GhClient to default to grey).
    assert all(isinstance(ld, LabelDef) for ld in ensure.labels), (
        f"non-LabelDef entries: {[ld for ld in ensure.labels if not isinstance(ld, LabelDef)]}"
    )

    by_name = {ld.name: ld for ld in ensure.labels}

    # Templated labels resolve through the factories: registry colors.
    assert by_name["phase:1"].color == PHASE_LABEL_COLOR
    assert "1" in by_name["phase:1"].description

    assert by_name["plan:fixture-minimal"].color == PLAN_LABEL_COLOR
    assert "fixture-minimal" in by_name["plan:fixture-minimal"].description

    assert by_name["spec:vk-rebuild-state-machine-design"].color == SPEC_LABEL_COLOR

    # Lifecycle constant: matches the registry singleton's color exactly.
    assert by_name["vk-ready"].color == VK_READY.color
    assert by_name["vk-ready"].description == VK_READY.description

    # Registry constants for unused lifecycle slots are not pulled in.
    for unused in (MANUAL, IN_PROGRESS, PR_READY):
        assert unused.name not in by_name


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
                            "plan:fixture-minimal",
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
                        "plan:fixture-minimal",
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


# ---------------------------------------------------------------------------
# Group H — Multi-repo (cross-repo dispatch)
# ---------------------------------------------------------------------------


def test_diff_emits_ensure_per_destination_repo():
    """
    GIVEN a plan with target_repo='derio-net/repo-a'
    AND   phase 2 has tracking_issue='https://github.com/derio-net/repo-b/issues/100'
    AND   phase 1 and 3 have no tracking_issue (undispatched)
    WHEN  diff(rendered, observed, plan) is computed
    THEN  exactly two RepoLabelEnsure mutations are emitted
    AND   one targets 'derio-net/repo-a' (for undispatched phases)
    AND   one targets 'derio-net/repo-b' (for phase 2's tracking issue)
    """
    from vk import parse
    from vk.diff import RepoLabelEnsure, diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(CROSS_REPO)
    observed = GhState(phases={})
    rendered = render(plan, observed)
    mutations = diff(rendered, observed, plan=plan).mutations

    ensures = [m for m in mutations if isinstance(m, RepoLabelEnsure)]
    ensure_repos = {m.repo for m in ensures}
    assert ensure_repos == {"derio-net/repo-a", "derio-net/repo-b"}


def test_diff_routes_per_issue_mutations_to_tracking_repo():
    """
    GIVEN a plan with target_repo='derio-net/repo-a'
    AND   phase 2 dispatched to 'derio-net/repo-b' with a drifted body,
          vk-ready, and an extra stale label
    WHEN  diff(rendered, observed, plan) is computed
    THEN  every IssueLabelChange / IssueBodyChange for phase 2
          carries repo='derio-net/repo-b' (NEVER 'derio-net/repo-a')
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import IssueBodyChange, IssueLabelChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(CROSS_REPO)

    # Phase 1 needs to be complete so phase 2's deps are satisfied
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
    plan = dc_replace(
        plan,
        phases=tuple(p1_complete if p.phase.number == 1 else p for p in plan.phases),
    )

    # Phase 2 is already dispatched on repo-b (in the fixture).
    # Observe it with a stale extra label and stale body.
    observed = GhState(
        phases={
            2: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"vk-ready", "stale-label"}),
                issue_assignees=(),
                linked_prs=(),
                body="stale body",
            )
        }
    )
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    label_changes = [m for m in d.mutations if isinstance(m, IssueLabelChange)]
    body_changes = [m for m in d.mutations if isinstance(m, IssueBodyChange)]

    # All per-issue mutations for phase 2 must target repo-b
    for m in label_changes + body_changes:
        assert m.repo == "derio-net/repo-b", f"expected repo-b, got {m.repo!r} in {m}"
        assert m.repo != "derio-net/repo-a"


def test_diff_single_repo_plan_emits_one_ensure():
    """
    GIVEN a single-repo plan (target_repo == every phase's tracking_issue repo)
    WHEN  diff(rendered, observed, plan) is computed
    THEN  exactly one RepoLabelEnsure mutation is emitted
    AND   its repo == plan.meta.target_repo
    """
    from vk import parse
    from vk.diff import RepoLabelEnsure, diff
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    observed = GhState(phases={})
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    ensures = [m for m in d.mutations if isinstance(m, RepoLabelEnsure)]
    assert len(ensures) == 1
    assert ensures[0].repo == plan.meta.target_repo


def test_diff_fully_cross_repo_plan_skips_target_repo_ensure():
    """
    GIVEN a plan where every phase is dispatched on a foreign repo
          (none on plan.meta.target_repo) and no phases are undispatched
    WHEN  diff(rendered, observed, plan) is computed
    THEN  no RepoLabelEnsure mutation targets plan.meta.target_repo
    AND   one RepoLabelEnsure exists per distinct foreign destination repo
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import RepoLabelEnsure, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(CROSS_REPO)

    # Mark phase 1 complete and give it a tracking_issue on repo-b too
    # so ALL phases are dispatched on repo-b (none on target_repo repo-a)
    foreign_url_p1 = "https://github.com/derio-net/repo-b/issues/99"
    foreign_url_p3 = "https://github.com/derio-net/repo-b/issues/101"

    phases = []
    for p in plan.phases:
        if p.phase.number == 1:
            p = p.model_copy(
                update={
                    "phase": p.phase.model_copy(update={"tracking_issue": foreign_url_p1}),
                    "state": p.state.model_copy(
                        update={
                            "completion": p.state.completion.model_copy(
                                update={"at": "2026-05-17T10:00:00Z", "note": "done"}
                            )
                        }
                    ),
                }
            )
        elif p.phase.number == 3:
            p = p.model_copy(
                update={"phase": p.phase.model_copy(update={"tracking_issue": foreign_url_p3})}
            )
        phases.append(p)
    plan = dc_replace(plan, phases=tuple(phases))

    merged_pr = PrObservation(
        url="https://github.com/derio-net/repo-b/pull/1",
        state="CLOSED",
        merged=True,
        draft=False,
        ci="PASS",
    )
    obs_closed = PhaseObservation(
        issue_state="CLOSED",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(merged_pr,),
    )
    obs_open = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset({"vk-ready"}),
        issue_assignees=(),
        linked_prs=(),
    )
    observed = GhState(phases={1: obs_closed, 2: obs_open, 3: obs_open})
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    ensures = [m for m in d.mutations if isinstance(m, RepoLabelEnsure)]
    ensure_repos = {m.repo for m in ensures}

    # No ensure for target_repo (repo-a) — all phases on repo-b
    assert "derio-net/repo-a" not in ensure_repos
    # Only repo-b gets an ensure
    assert "derio-net/repo-b" in ensure_repos
