from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_render_body_uses_repo_relative_path_not_absolute():
    """Issue body must not leak the dispatcher's absolute filesystem path."""
    from vk import parse
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    rendered = render(plan, GhState(phases={}))
    body = rendered.issue_per_phase[1].body
    # The absolute path of FIXTURE should NOT appear in the body
    assert str(FIXTURE.resolve()) not in body
    # The repo-relative path SHOULD appear in the body
    assert "tests/unit/fixtures/v2_plan_minimal" in body


def test_render_undispatched_phase_yields_create_intent():
    from vk import parse
    from vk.render import render
    from vk.states import GhState

    plan = parse(FIXTURE)
    observed = GhState(phases={})
    rendered = render(plan, observed)

    assert 1 in rendered.issue_per_phase
    issue = rendered.issue_per_phase[1]
    assert issue.state == "OPEN"
    label_names = {ld.name for ld in issue.labels}
    assert "spec:vk-rebuild-state-machine-design" in label_names
    assert "plan:2026-05-09-fixture-minimal" in label_names
    assert "phase:1" in label_names
    assert "vk-ready" in label_names  # agentic, no assignee, no PR, not complete
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
    from vk import parse
    from vk.render import _lifecycle_label
    from vk.states import GhState, PhaseObservation, PrObservation

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
    result = _lifecycle_label(plan.phases[0], obs, plan, GhState(phases={}))
    assert result is not None
    assert result.name == expected_label


def test_agentic_phase_complete_requires_completion_at_and_merged_pr():
    """Agentic phases need BOTH:
      - `completion.at` set (agent's "I'm done" signal)
      - merged PR observed + no open linked PR (operator's "I accepted" signal)
    Either alone is insufficient. Pre-2026-05-18 the code OR-shortcut on
    completion.at alone, which closed Issues prematurely when an agent
    set completion.at before opening its PR.
    """
    from vk import parse
    from vk.render import _phase_complete
    from vk.states import PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    p1 = plan.phases[0]
    # Tick the only step so we isolate the completion.at + PR variables
    ticked = p1.model_copy(
        update={
            "state": p1.state.model_copy(
                update={
                    "steps": {
                        "P1.T1.S1": p1.state.steps["P1.T1.S1"].model_copy(update={"state": "x"})
                    }
                }
            )
        }
    )

    # ── completion.at NOT set ───────────────────────────────────────────
    obs_merged = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),),
    )
    # Steps ticked + merged PR but NO completion.at → not complete (was True pre-fix)
    assert _phase_complete(ticked, obs_merged) is False

    # ── completion.at SET ───────────────────────────────────────────────
    with_completion_at = ticked.model_copy(
        update={
            "state": ticked.state.model_copy(
                update={
                    "completion": ticked.state.completion.model_copy(
                        update={"at": "2026-05-18T12:00:00Z"}
                    )
                }
            )
        }
    )

    # completion.at set, NO PR observed → not complete (was True pre-fix; the premature-close bug)
    obs_no_pr = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(),
    )
    assert _phase_complete(with_completion_at, obs_no_pr) is False

    # completion.at set, OPEN PR (not merged) → not complete (was True pre-fix; same bug)
    obs_open_pr = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),),
    )
    assert _phase_complete(with_completion_at, obs_open_pr) is False

    # completion.at set + merged PR + no open PR → complete (the only happy path)
    assert _phase_complete(with_completion_at, obs_merged) is True

    # completion.at set + merged PR + an unrelated OPEN PR (e.g., follow-up
    # fix branched off the same Issue) → not complete. `has_open_pr` is a
    # blocker regardless of whether a merge already happened.
    obs_merged_plus_open = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(
            PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),
            PrObservation(url="...", state="OPEN", merged=False, draft=False, ci="PASS"),
        ),
    )
    assert _phase_complete(with_completion_at, obs_merged_plus_open) is False

    # completion.at set + obs is None → not complete (can't verify PR state
    # without an observation; conservative skip rather than false-True)
    assert _phase_complete(with_completion_at, None) is False


def test_manual_phase_complete_requires_completion_at_and_note():
    from vk import parse
    from vk.render import _phase_complete

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
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

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
    assert any("ticked" in str(w).lower() and "merged" in str(w).lower() for w in rendered.warnings)
    assert any(w.severity == "warn" for w in rendered.warnings)


def test_drift_warning_pr_merged_steps_unticked():
    """Merged PR but steps unticked → warning surfaces."""
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    obs = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),),
    )
    rendered = render(plan, GhState(phases={1: obs}))
    assert any(
        "merged" in str(w).lower() and "unticked" in str(w).lower() for w in rendered.warnings
    )
    assert any(w.severity == "info" for w in rendered.warnings)


def test_drift_warning_issue_closed_plan_incomplete():
    """Issue closed externally while plan still incomplete → warning."""
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    obs = PhaseObservation(
        issue_state="CLOSED",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(),
    )
    rendered = render(plan, GhState(phases={1: obs}))
    assert any(
        "closed" in str(w).lower() and "incomplete" in str(w).lower() for w in rendered.warnings
    )
    assert any(w.severity == "error" for w in rendered.warnings)


def test_archive_decision_true_when_all_phases_complete():
    """All phases complete → archive_decision True.

    Per 2026-05-18 fix to `_phase_complete`, agentic phases need BOTH
    `completion.at` AND a merged PR observed. Manual phases still only
    need `completion.at` + `completion.note`. So this test now also
    seeds an observation with a merged PR for each agentic phase.
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)

    completed_phases = []
    agentic_observations: dict[int, PhaseObservation] = {}
    for p in plan.phases:
        if p.phase.tag == "manual":
            new_completion = p.state.completion.model_copy(
                update={"at": "2026-05-10T12:00:00Z", "note": "done"}
            )
        else:
            new_completion = p.state.completion.model_copy(update={"at": "2026-05-10T12:00:00Z"})
            agentic_observations[p.phase.number] = PhaseObservation(
                issue_state="CLOSED",
                issue_labels=frozenset(),
                issue_assignees=(),
                linked_prs=(
                    PrObservation(
                        url="https://github.com/x/y/pull/1",
                        state="CLOSED",
                        merged=True,
                        draft=False,
                        ci="PASS",
                    ),
                ),
            )
        completed_phases.append(
            p.model_copy(
                update={"state": p.state.model_copy(update={"completion": new_completion})}
            )
        )
    new_plan = dc_replace(plan, phases=tuple(completed_phases))

    rendered = render(new_plan, GhState(phases=agentic_observations))
    assert rendered.archive_decision is True


def test_archive_decision_false_when_any_phase_incomplete():
    from vk import parse
    from vk.render import render
    from vk.states import GhState

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    rendered = render(plan, GhState(phases={}))
    assert rendered.archive_decision is False


def test_manual_phase_label_is_manual():
    """A phase with tag=manual gets the manual lifecycle label, not vk-ready."""
    from vk import parse
    from vk.render import _lifecycle_label
    from vk.states import GhState

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    # Phase 10 in this fixture is tagged manual
    manual_phase = next(p for p in plan.phases if p.phase.tag == "manual")
    result = _lifecycle_label(manual_phase, None, plan, GhState(phases={}))
    assert result is not None
    assert result.name == "manual"


def test_render_body_blocked_by_uses_issue_number_not_phase_number():
    """Regression: `- Blocked by #N` must use the predecessor's tracking-issue
    number, not its phase number. Bridge parses `#N` as an Issue number, so
    using a phase number silently mis-gates dependent phases.
    """
    from vk import parse
    from vk.render import render_body

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    phase2 = next(p for p in plan.phases if p.phase.number == 2)
    # Fixture precondition: phase2 already depends on phase1.
    assert phase2.phase.depends_on == (1,)

    # `phase_to_issue={1: 42}` simulates Phase 1 having tracking_issue
    # `.../issues/42` — we don't need to mutate phase1's model for this
    # unit test since `render_body` consults the map, not the phase.
    body = render_body(phase2, plan, phase_to_issue={1: 42})

    assert "- Blocked by #42" in body
    assert "- Blocked by #1" not in body


def test_render_body_blocked_by_cross_repo_dep():
    """Forward-compat: when phase_to_repo names a different repo, the rendered
    line uses `owner/repo#N`. The bridge already parses this shape (see
    agent-images/kali/scripts/vk-issue-bridge.py dep_re), so making the
    renderer symmetric now avoids a second rework when cross-repo dispatch
    lands.
    """
    from vk import parse
    from vk.render import render_body

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    phase2 = next(p for p in plan.phases if p.phase.number == 2)

    body = render_body(
        phase2,
        plan,
        phase_to_issue={1: 42},
        phase_to_repo={1: "derio-net/other"},
    )

    assert "- Blocked by derio-net/other#42" in body
    # Plain `#42` would be wrong here (cross-repo), but the longer form
    # contains `#42` as a substring, so guard against the bare-form mistake
    # by checking that no line is exactly `- Blocked by #42`.
    assert "- Blocked by #42\n" not in body and not body.endswith("- Blocked by #42")


def test_render_body_blocked_by_missing_predecessor_falls_back_to_phase_number():
    """Fallback: when predecessor's Issue isn't in phase_to_issue (not yet
    dispatched and not in this run's created set), emit the phase-number
    form so the operator sees a broken ref instead of an empty deps block.
    """
    from vk import parse
    from vk.render import render_body

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    phase2 = next(p for p in plan.phases if p.phase.number == 2)

    body = render_body(phase2, plan, phase_to_issue={})

    assert "- Blocked by #1" in body


def test_render_preserves_vk_synced_label_from_observed():
    """`vk-synced` is set by the bridge; the renderer doesn't manage it.
    Without explicit preservation it would be stripped by diff() because
    the `vk-` managed prefix sweep wouldn't see it in rendered.labels.
    """
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    obs = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"vk-ready", "vk-synced", "phase:1"}),
                issue_assignees=(),
                linked_prs=(),
                body="",
            )
        }
    )
    rendered = render(plan, obs)
    assert "vk-synced" in {ld.name for ld in rendered.issue_per_phase[1].labels}


def test_render_omits_vk_synced_when_not_observed():
    """The renderer only preserves vk-synced when it's already on the
    Issue — it never adds the marker on its own."""
    from vk import parse
    from vk.render import render
    from vk.states import GhState, PhaseObservation

    plan = parse(FIXTURE)
    obs = GhState(
        phases={
            1: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"vk-ready", "phase:1"}),
                issue_assignees=(),
                linked_prs=(),
                body="",
            )
        }
    )
    rendered = render(plan, obs)
    assert "vk-synced" not in {ld.name for ld in rendered.issue_per_phase[1].labels}


def test_complete_phase_projects_closed_state():  # C5
    """BDD scenario (spec §C5):
    GIVEN a phase with state.completion.at set, all steps ticked,
          and observed: 1 merged PR, no open non-draft PRs
    WHEN  render(plan, observed) is called
    THEN  rendered.issue_per_phase[N].state == 'CLOSED'

    GIVEN diff(rendered, observed_with_open_issue, plan) is computed
    THEN  an IssueStateChange(repo=..., issue_number=N, new_state='CLOSED')
          mutation is emitted

    Pin-test for the renderer's existing CLOSED projection at
    src/vk/render.py:311 + diff.py's IssueStateChange emission at
    src/vk/diff.py:177. Phase 3 folds the legacy bridge's
    belt-and-braces close into the renderer projection.
    """
    from dataclasses import replace as dc_replace

    from vk import parse
    from vk.diff import IssueStateChange, diff
    from vk.render import render
    from vk.states import GhState, PhaseObservation, PrObservation

    plan = parse(FIXTURE)
    # Set completion.at and tick the only step so _phase_complete fires.
    p1 = plan.phases[0]
    completed = p1.model_copy(
        update={
            "state": p1.state.model_copy(
                update={
                    "completion": p1.state.completion.model_copy(
                        update={"at": "2026-05-17T12:00:00Z"}
                    ),
                    "steps": {
                        "P1.T1.S1": p1.state.steps["P1.T1.S1"].model_copy(update={"state": "x"})
                    },
                }
            ),
            "phase": p1.phase.model_copy(
                update={
                    "tracking_issue": "https://github.com/derio-net/superpowers-for-vk/issues/154"
                }
            ),
        }
    )
    new_plan = dc_replace(plan, phases=(completed,))

    obs_merged = PhaseObservation(
        issue_state="OPEN",
        issue_labels=frozenset(),
        issue_assignees=(),
        linked_prs=(PrObservation(url="...", state="CLOSED", merged=True, draft=False, ci="PASS"),),
        body="",
    )
    observed = GhState(phases={1: obs_merged})

    rendered = render(new_plan, observed)
    assert rendered.issue_per_phase[1].state == "CLOSED"

    # And the diff layer must emit an IssueStateChange against an
    # observation that still shows the Issue OPEN.
    d = diff(rendered, observed, plan=new_plan)
    state_changes = [m for m in d.mutations if isinstance(m, IssueStateChange)]
    assert len(state_changes) == 1
    assert state_changes[0].new_state == "CLOSED"
    assert state_changes[0].issue_number == 154
    assert state_changes[0].repo == "derio-net/superpowers-for-vk"
