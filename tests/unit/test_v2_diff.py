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

    assert by_name["plan:2026-05-09-fixture-minimal"].color == PLAN_LABEL_COLOR
    assert "fixture-minimal" in by_name["plan:2026-05-09-fixture-minimal"].description

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


def test_diff_cross_repo_emits_one_ensure_per_repo():
    """Phases dispatched to different repos → one RepoLabelEnsure per destination."""
    from dataclasses import replace as dc_replace
    from pathlib import Path

    from vk import parse
    from vk.diff import RepoLabelEnsure, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation
    from vk.types import PhaseDoc

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)

    # Phase 1 → repo-B, Phase 2 → repo-B (target_repo is repo-A via fixture).
    # Phase 10 has no tracking_issue → will land on target_repo (repo-A).
    def _with_tracking(p: PhaseDoc, issue_n: int) -> PhaseDoc:
        url = f"https://github.com/derio-net/repo-b/issues/{issue_n}"
        return p.model_copy(update={"phase": p.phase.model_copy(update={"tracking_issue": url})})

    new_phases = tuple(
        _with_tracking(p, 10 + p.phase.number) if p.phase.number in (1, 2) else p
        for p in plan.phases
    )
    new_plan = dc_replace(plan, phases=new_phases)

    # Phase 1 and Phase 2 both have observed state so no IssueCreate is emitted.
    observed = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(),
            ),
            2: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(),
            ),
        }
    )
    rendered = render(new_plan, observed)
    d = diff(rendered, observed, plan=new_plan)

    ensures = [m for m in d.mutations if isinstance(m, RepoLabelEnsure)]
    assert len(ensures) == 2, f"expected 2 RepoLabelEnsure, got {[e.repo for e in ensures]}"
    repos = {e.repo for e in ensures}

    # repo-b gets labels for phases 1+2; target_repo gets labels for phase 10 (undispatched).
    assert "derio-net/repo-b" in repos
    assert "derio-net/superpowers-for-vk" in repos  # target_repo for phase 10

    # Each ensure carries only labels that belong to its repo's phases.
    repo_b_ensure = next(e for e in ensures if e.repo == "derio-net/repo-b")
    repo_b_label_names = {ld.name for ld in repo_b_ensure.labels}
    assert "phase:1" in repo_b_label_names
    assert "phase:2" in repo_b_label_names
    assert "phase:10" not in repo_b_label_names

    target_ensure = next(e for e in ensures if e.repo == "derio-net/superpowers-for-vk")
    target_label_names = {ld.name for ld in target_ensure.labels}
    assert "phase:10" in target_label_names
    assert "phase:1" not in target_label_names
    assert "phase:2" not in target_label_names
