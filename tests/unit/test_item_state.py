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


def test_dispatch_stamp_is_typed_separately_from_item_state() -> None:
    from fr.item_state import DISPATCH_STAMP, ItemState, project_github
    from fr.labels import FR_SYNCED

    assert DISPATCH_STAMP is FR_SYNCED
    assert DISPATCH_STAMP.name not in set(get_args(ItemState))
    for state in get_args(ItemState):
        assert FR_SYNCED.name not in {ld.name for ld in project_github(state)}


# --- The renderer's per-phase state decision, in ItemState terms ------------
#
# Same fixture shape as the characterization net: `phase_item_state` is the
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
def test_phase_item_state_decides_in_tracker_neutral_terms(
    tmp_path: Path, phase_number: int, expected: str
) -> None:
    from fr import parse
    from fr.render import phase_item_state

    plan = parse(build_plan_dir(tmp_path))
    assert phase_item_state(plan, build_observed(), phase_number) == expected


def test_phase_item_state_reports_in_review_for_an_open_nondraft_pr(tmp_path: Path) -> None:
    from dataclasses import replace

    from fr import parse
    from fr.render import phase_item_state
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
    assert phase_item_state(plan, observed, 2) == "in_review"


def test_phase_item_state_reports_queued_for_an_undispatched_phase(tmp_path: Path) -> None:
    """Phase 1 has no observation at all.

    The tracker-neutral decision is still `queued` — "not yet dispatched" is
    a *projection* concern (the GitHub renderer withholds the lifecycle label
    for a tracking-only Issue), not a sixth item state.
    """
    from fr import parse
    from fr.render import phase_item_state

    plan = parse(build_plan_dir(tmp_path))
    assert phase_item_state(plan, build_observed(), 1) == "queued"
