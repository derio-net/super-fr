"""The hand-back budget and the conflict and red decisions, moved out of `batch_drive`
(spec 2026-11-24-wave-queue-gaps §E) and re-exported there by name.

Pure: no git, no forge, no clock.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from fr.triage.model import Batch, ConflictEvent, DispatchEvent, RedHandbackEvent

# ------------------------------------------------- conflict hand-back (§G)

HANDBACKS_PER_DISPATCH = 2
"""R22: hand-backs a batch gets per dispatch; the next conflict is held."""


def handbacks_since(
    events: Sequence[object], counted: Callable[[object], bool], *, reset: bool = True
) -> int:
    """The hand-back budget's one count: the events *counted* accepts, newest first, back
    to the batch's latest `dispatch` (*reset*), or all of them. Conflict (R22) and red
    (R10) hand-backs count per dispatch here; a collected close-out's (R27) counts per
    close-out item across its members, which no single batch's dispatch resets, so it
    counts distinct heads instead (`closeout_handback_decision`)."""
    n = 0
    for event in reversed(events):
        if reset and isinstance(event, DispatchEvent):
            break
        n += counted(event)
    return n


ConflictKind = Literal["skip", "wait-behind", "held", "handback"]


@dataclass(frozen=True)
class ConflictDecision:
    """What drive does with a real merge conflict (spec 2026-10-06-verification-
    strategies §G): `behind` names the batch a `wait-behind` waits on."""

    kind: ConflictKind
    behind: str | None = None


def conflict_decision(
    events: Sequence[object],
    head: str,
    paths: Sequence[str],
    earlier_in_pass: Sequence[tuple[str, Sequence[str]]],
) -> ConflictDecision:
    """The pure decision on a conflict at *head* refusing *paths* (R21, R22).

    `skip`: a `conflict` event already exists for this head, so a restarted driver
    never hands the same head back twice. `wait-behind`: a refused path is shared
    with a conflict met earlier in this pass (*earlier_in_pass*, `(batch, paths)` in
    train order), which is fixed first. `held`: two `session|fresh` hand-backs were
    made since the batch's latest `dispatch` event (held ones never count). Else
    `handback`.
    """
    if any(isinstance(e, ConflictEvent) and e.head == head for e in events):
        return ConflictDecision("skip")
    mine = set(paths)
    for batch_id, theirs in earlier_in_pass:
        if mine.intersection(theirs):
            return ConflictDecision("wait-behind", behind=batch_id)
    handed = handbacks_since(
        events, lambda e: isinstance(e, ConflictEvent) and e.delivered != "held"
    )
    if handed >= HANDBACKS_PER_DISPATCH:
        return ConflictDecision("held")
    return ConflictDecision("handback")


# ------------------------------------------------- red recovery (merge-train-safety §C)

RED_HANDBACKS_PER_DISPATCH = 2
"""R10: red hand-backs a batch gets per dispatch, counted apart from conflict ones."""

RedDecisionKind = Literal["handback", "wait", "needs_you", "skip"]


def red_decision(
    events: Sequence[object],
    pr: int,
    head: str,
    failing: Sequence[str],
    status: str,
) -> RedDecisionKind:
    """What the driver does with PR *pr* red at *head* (*failing* names the checks), by the
    first rule that applies (R10, R11):

    1. a `red_handback` event exists for (pr, head): `skip`;
    2. `RED_HANDBACKS_PER_DISPATCH` delivered hand-backs have gone out since the latest
       dispatch: `needs_you`;
    3. the session's *status*: `idle` is a `handback`, `absent` or `done` a `needs_you`,
       anything else `wait`.

    The rule that updated a red head fr itself made (R9's `reupdate`) is gone: the wave
    merge queue never updates a PR branch (spec 2026-11-19-wave-merge-queue R13, R22).
    """
    red = [e for e in events if isinstance(e, RedHandbackEvent)]
    if any(e.pr == pr and e.head == head for e in red):
        return "skip"
    handed = handbacks_since(
        events, lambda e: isinstance(e, RedHandbackEvent) and e.delivered == "session"
    )
    if handed >= RED_HANDBACKS_PER_DISPATCH:
        return "needs_you"
    if status == "idle":
        return "handback"
    return "needs_you" if status in ("absent", "done") else "wait"


def held_conflict(batch: Batch) -> ConflictEvent | None:
    """The batch's latest `conflict` event when it is `held` and no `dispatch` came after
    it (R22): the operator owns that conflict. A new dispatch resets the count."""
    for event in reversed(batch.events):
        if isinstance(event, DispatchEvent):
            return None
        if isinstance(event, ConflictEvent):
            return event if event.delivered == "held" else None
    return None
