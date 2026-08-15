"""Tracker-neutral queue vocabulary — the abstract transition set.

`ItemState` is the closed set of states a work item can be in, expressed
without reference to any tracker. `labels.py` stays the *GitHub* vocabulary;
this module is the neutral one and depends on it, never the reverse — the
dependency direction is what makes a second tracker adapter possible without
touching either.

GitHub projection (spec 2026-08-14-workflow-shapes-and-workitem-dispatch §4.C):

    queued      → fr:ready
    blocked     → fr:blocked
    in_progress → fr:in-progress
    in_review   → fr:pr-ready
    done        → no label; the Issue is CLOSED

`done` deliberately projects to the empty label set: completion is carried by
the tracker's own item state (GitHub's CLOSED), not by a lifecycle label. A
tracker without a closed/open notion would project `done` differently; the
enum does not presume one.

**`fr:synced` is not an `ItemState`.** It is *dispatch bookkeeping* — "this
item was handed to a runner, don't re-dispatch it" — that lives on the Issue
only because there is nowhere more durable to put it (a run file on a feature
branch is invisible to a bridge reading `main`). Typing it separately as
`DISPATCH_STAMP` keeps it out of the state vocabulary, so a tracker that
cannot express the stamp is still a usable tracker: it loses idempotency
bookkeeping, not the ability to represent an item's state.
"""

from __future__ import annotations

from typing import Literal, get_args

from fr.labels import (
    FR_BLOCKED,
    FR_IN_PROGRESS,
    FR_PR_READY,
    FR_READY,
    FR_SYNCED,
    LabelDef,
)

ItemState = Literal["queued", "blocked", "in_progress", "in_review", "done"]

ITEM_STATES: tuple[ItemState, ...] = get_args(ItemState)

# Dispatch bookkeeping, NOT a state — see the module docstring.
DISPATCH_STAMP: LabelDef = FR_SYNCED

_GITHUB_PROJECTION: dict[ItemState, frozenset[LabelDef]] = {
    "queued": frozenset({FR_READY}),
    "blocked": frozenset({FR_BLOCKED}),
    "in_progress": frozenset({FR_IN_PROGRESS}),
    "in_review": frozenset({FR_PR_READY}),
    # Expressed by Issue state CLOSED, not by a label.
    "done": frozenset(),
}

_STATE_BY_LABEL_NAME: dict[str, ItemState] = {
    label.name: state
    for state, labels in _GITHUB_PROJECTION.items()
    for label in labels  # `done` contributes nothing — it has no label form
}


def project_github(state: ItemState) -> frozenset[LabelDef]:
    """The GitHub label set expressing `state`.

    A frozenset (not a single LabelDef) so a future state that needs two
    labels — or a tracker that needs none, like `done` — does not change the
    signature.
    """
    return _GITHUB_PROJECTION[state]


def state_from_labels(observed_labels: frozenset[str] | set[str]) -> ItemState | None:
    """Inverse of `project_github`: read an ItemState off observed labels.

    Returns None when no lifecycle label is present — an empty set, a
    tracking-only Issue, or one carrying only attributes (`manual`,
    `phase:<n>`, `runner:<name>`). `fr:synced` is ignored entirely: it is
    the dispatch stamp, not a state, so it neither yields a state on its own
    nor perturbs one that is expressed.

    `done` has no label form, so it is never returned here; completion is
    read from the tracker's item state instead.
    """
    for name in sorted(observed_labels):
        state = _STATE_BY_LABEL_NAME.get(name)
        if state is not None:
            return state
    return None
