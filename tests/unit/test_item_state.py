"""`fr.item_state` — the tracker-neutral queue vocabulary (spec §4.C).

`ItemState` is the closed enum a tracker adapter must be able to express;
`project_github` is the GitHub *projection* of it, and `state_from_labels`
its inverse. `fr:synced` is deliberately outside the enum — it is dispatch
bookkeeping, not an item state.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from tests.unit.test_render_characterization import build_observed, build_plan_dir


def test_item_state_is_the_closed_five_member_enum() -> None:
    from fr.item_state import ItemState

    assert set(get_args(ItemState)) == {
        "queued",
        "blocked",
        "in_progress",
        "in_review",
        "done",
    }


def test_project_github_maps_every_state_to_its_label_set() -> None:
    from fr.item_state import project_github
    from fr.labels import FR_BLOCKED, FR_IN_PROGRESS, FR_PR_READY, FR_READY

    assert project_github("queued") == frozenset({FR_READY})
    assert project_github("blocked") == frozenset({FR_BLOCKED})
    assert project_github("in_progress") == frozenset({FR_IN_PROGRESS})
    assert project_github("in_review") == frozenset({FR_PR_READY})
    # `done` is expressed by the Issue state (CLOSED), not by a label.
    assert project_github("done") == frozenset()


def test_state_from_labels_is_the_inverse_for_every_state() -> None:
    from fr.item_state import ItemState, project_github, state_from_labels

    for state in get_args(ItemState):
        labels = frozenset(ld.name for ld in project_github(state))
        if state == "done":
            # `done` projects to no label, so it has no label-side inverse.
            continue
        assert state_from_labels(labels) == state


def test_state_from_labels_returns_none_for_unrecognized_or_empty() -> None:
    from fr.item_state import state_from_labels

    assert state_from_labels(frozenset()) is None
    assert state_from_labels(frozenset({"manual", "phase:3"})) is None


def test_state_from_labels_ignores_the_dispatch_stamp() -> None:
    from fr.item_state import state_from_labels

    # `fr:synced` alone says nothing about the item's state.
    assert state_from_labels(frozenset({"fr:synced"})) is None
    # …and it never perturbs a state that IS expressed.
    assert state_from_labels(frozenset({"fr:synced", "fr:in-progress"})) == "in_progress"


# --- Multi-label resolution: lifecycle precedence, not sort order -----------
#
# An Issue can carry a stale `fr:ready` alongside the label for work that has
# actually started (the renderer projects one lifecycle label, but observed
# label sets are whatever GitHub says, and `fr apply` is not the only writer).
# `fr_dispatch.tick` gates dispatch on `state_from_labels(...) == "queued"`, so
# "which label wins" IS the question of whether the bridge dispatches work an
# agent already holds.


@pytest.mark.parametrize(
    ("other_label", "expected"),
    [
        ("fr:in-progress", "in_progress"),
        ("fr:blocked", "blocked"),
        ("fr:pr-ready", "in_review"),
    ],
)
def test_any_lifecycle_label_beats_a_stale_ready_label(other_label: str, expected: str) -> None:
    """`queued` loses to every other lifecycle signal.

    Not because of how the names sort — because `queued` is the only state
    that permits dispatch, so any other signal must win.
    """
    from fr.item_state import state_from_labels

    assert state_from_labels(frozenset({"fr:ready", other_label})) == expected


def test_ready_never_wins_over_any_other_lifecycle_label() -> None:
    """The property, not the cases — derived from the label table so a
    lifecycle label added tomorrow is covered without editing this test.

    This is the test that would have caught the alphabetical scan: it fails
    for any label that sorts after `fr:ready` (a hypothetical `fr:working`,
    or a rename of an existing one).
    """
    from fr.item_state import _STATE_BY_LABEL_NAME, state_from_labels

    others = set(_STATE_BY_LABEL_NAME) - {"fr:ready"}
    assert others, "no non-ready lifecycle labels — the property would be vacuous"
    for label in others:
        assert state_from_labels(frozenset({"fr:ready", label})) != "queued", label


def test_precedence_does_not_depend_on_label_names_sorting_favourably(monkeypatch) -> None:
    """Directly pins the mechanism.

    `fr:ready` currently sorts last among the lifecycle labels
    (`fr:blocked` < `fr:in-progress` < `fr:pr-ready` < `fr:ready`), which is
    the naming coincidence that made an alphabetical scan look correct. Add a
    lifecycle label that sorts AFTER `fr:ready` — a rename away, and exactly
    what a repo with its own label vocabulary would hit — and the alphabetical
    scan resolves the pair to `queued`, i.e. dispatches over an agent already
    working the item.
    """
    import fr.item_state as item_state

    monkeypatch.setitem(item_state._STATE_BY_LABEL_NAME, "fr:working", "in_progress")
    assert "fr:working" > "fr:ready"  # the trap: sorts after, so a scan misses it

    assert item_state.state_from_labels(frozenset({"fr:ready", "fr:working"})) == "in_progress"


def test_resolution_is_independent_of_iteration_order() -> None:
    """Same label set, any order in — same state out."""
    from fr.item_state import state_from_labels

    labels = ("fr:ready", "fr:in-progress", "fr:blocked")
    assert state_from_labels(set(labels)) == "in_progress"
    assert state_from_labels(set(reversed(labels))) == "in_progress"
    assert state_from_labels(frozenset(labels)) == "in_progress"


def test_every_label_bearing_state_has_a_declared_precedence() -> None:
    """Tripwire: a new lifecycle state must be ranked explicitly.

    An unranked state still resolves fail-closed (it outranks everything, so
    the item is never treated as dispatchable), but silence is not the
    contract — the ordering is a decision someone has to make.
    """
    from fr.item_state import _PRECEDENCE, _STATE_BY_LABEL_NAME

    assert set(_STATE_BY_LABEL_NAME.values()) <= set(_PRECEDENCE)
    # The invariant the dispatch gate rests on.
    assert _PRECEDENCE[-1] == "queued"


def test_attributes_and_the_dispatch_stamp_never_perturb_precedence() -> None:
    """Phase 1's contract, restated against a multi-label set.

    `manual` is a routing attribute and `fr:synced` is dispatch bookkeeping —
    neither is an ItemState, so neither may change which state is read.
    """
    from fr.item_state import state_from_labels

    noise = {"fr:synced", "manual", "phase:3", "runner:vk", "plan:some-plan"}
    assert state_from_labels(frozenset({"fr:ready", "fr:in-progress"} | noise)) == "in_progress"
    assert state_from_labels(frozenset({"fr:ready"} | noise)) == "queued"
    assert state_from_labels(frozenset(noise)) is None


def test_dispatch_stamp_is_typed_separately_from_item_state() -> None:
    from fr.item_state import DISPATCH_STAMP, ItemState, project_github
    from fr.labels import FR_SYNCED

    assert DISPATCH_STAMP is FR_SYNCED
    assert DISPATCH_STAMP.name not in set(get_args(ItemState))
    for state in get_args(ItemState):
        assert FR_SYNCED.name not in {ld.name for ld in project_github(state)}


# --- The renderer's per-phase state decision, in ItemState terms ------------
#
# Same fixture shape as the characterization net: `phase_item_decision` is the
# tracker-neutral seam the GitHub projection is derived FROM, so the two must
# agree phase for phase.


@pytest.mark.parametrize(
    ("phase_number", "expected"),
    [
        (2, "queued"),
        (3, "blocked"),
        (4, "in_progress"),
        (5, "done"),
    ],
)
def test_phase_item_decision_decides_in_tracker_neutral_terms(
    tmp_path: Path, phase_number: int, expected: str
) -> None:
    from fr import parse
    from fr.render import phase_item_decision

    plan = parse(build_plan_dir(tmp_path))
    assert phase_item_decision(plan, build_observed(), phase_number).state == expected


def test_phase_item_decision_reports_in_review_for_an_open_nondraft_pr(tmp_path: Path) -> None:
    from dataclasses import replace

    from fr import parse
    from fr.render import phase_item_decision
    from fr.states import PrObservation

    plan = parse(build_plan_dir(tmp_path))
    observed = build_observed()
    observed.phases[2] = replace(
        observed.phases[2],
        linked_prs=(
            PrObservation(
                url="https://github.com/derio-net/super-fr/pull/9",
                state="OPEN",
                merged=False,
                draft=False,
                ci="PASS",
            ),
        ),
    )
    assert phase_item_decision(plan, observed, 2).state == "in_review"


def test_phase_item_decision_reports_queued_for_an_undispatched_phase(tmp_path: Path) -> None:
    """Phase 1 has no observation at all.

    The tracker-neutral decision is still `queued` — "not yet dispatched" is
    a *projection* concern (the GitHub renderer withholds the lifecycle label
    for a tracking-only Issue), not a sixth item state.
    """
    from fr import parse
    from fr.render import phase_item_decision

    plan = parse(build_plan_dir(tmp_path))
    assert phase_item_decision(plan, build_observed(), 1).state == "queued"


# --- Routability rides alongside the state, not inside it -------------------
#
# `manual` is a routing ATTRIBUTE, not a sixth ItemState (spec §4.C). The
# GitHub projection has always short-circuited on it, but the tracker-neutral
# seam used to return a bare `ItemState`, so a caller gating dispatch on
# `... == "queued"` — exactly what `fr_dispatch._is_dispatchable` does with the
# label-side vocabulary — would hand a human-only phase to an agent runner.
# The seam therefore returns a DECISION carrying both.

_FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _manual_plan_dir(tmp_path: Path) -> Path:
    """`v2_plan_minimal` with its single phase forced to `tag: manual`."""
    import shutil

    plan_dir = tmp_path / "plan"
    shutil.copytree(_FIXTURE_MINIMAL, plan_dir)
    phase = plan_dir / "01.yaml"
    phase.write_text(phase.read_text().replace("tag: agentic", "tag: manual"))
    return plan_dir


def test_item_decision_pairs_a_state_with_routability() -> None:
    """`dispatchable` is the ONE question a dispatcher asks — and it needs
    both halves. Neither alone is the answer."""
    from fr.item_state import ItemDecision

    assert ItemDecision(state="queued", routable=True).dispatchable is True
    # Human-only work is still `queued` — it is just not an agent's to take.
    assert ItemDecision(state="queued", routable=False).dispatchable is False
    # Routable but claimed/blocked/done is not dispatchable either.
    for state in ("blocked", "in_progress", "in_review", "done"):
        assert ItemDecision(state=state, routable=True).dispatchable is False, state


def test_manual_phase_is_queued_but_not_routable(tmp_path: Path) -> None:
    """The reproducer for the dropped routing attribute.

    A `tag: manual` phase with no observation decides `queued` — correct, and
    deliberately so: `manual` is not a state. What the neutral seam must ALSO
    carry is that no agent may take it, so a second tracker gating on the
    seam cannot dispatch it. GitHub's `manual` label is the projection of the
    same fact.
    """
    from fr import parse
    from fr.render import phase_item_decision, render
    from fr.states import GhState

    plan = parse(_manual_plan_dir(tmp_path))
    assert plan.phases[0].phase.tag == "manual"
    observed = GhState(phases={})

    decision = phase_item_decision(plan, observed, 1)
    assert decision.state == "queued"  # `manual` is an attribute, not a state
    assert decision.routable is False
    assert decision.dispatchable is False

    # …and the GitHub projection still says `manual`, unchanged.
    rendered = render(plan, observed)
    assert "manual" in {ld.name for ld in rendered.issue_per_phase[1].labels}


def test_an_agentic_queued_phase_is_routable_and_dispatchable(tmp_path: Path) -> None:
    """The other half of the pair — without it the fix could be `routable`
    hardwired to False."""
    from fr import parse
    from fr.render import phase_item_decision

    plan = parse(build_plan_dir(tmp_path))
    decision = phase_item_decision(plan, build_observed(), 2)
    assert (decision.state, decision.routable, decision.dispatchable) == ("queued", True, True)


def test_github_manual_label_is_projected_from_the_decision_not_the_phase_tag() -> None:
    """The projection takes the neutral decision and nothing else.

    Pinning the signature is the point: if `MANUAL` were re-injected by
    re-reading `PhaseDoc.tag` at projection time, the neutral seam could keep
    silently dropping routability and GitHub would still look right.
    """
    from fr.item_state import ItemDecision
    from fr.render import _lifecycle_label_for_decision

    unroutable = _lifecycle_label_for_decision(ItemDecision(state="queued", routable=False))
    assert unroutable is not None and unroutable.name == "manual"
    # `done` outranks the attribute: a finished manual phase closes, unlabelled.
    assert _lifecycle_label_for_decision(ItemDecision(state="done", routable=False)) is None
    routable = _lifecycle_label_for_decision(ItemDecision(state="queued", routable=True))
    assert routable is not None and routable.name == "fr:ready"
