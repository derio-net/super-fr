"""The hand-back budget and the conflict and red decisions, moved out of `batch_drive`
(spec 2026-11-24-wave-queue-gaps §E) and re-exported there by name; and the batch conflict
lookups, the archive-conflict decisions (merge-truth R12) and the collected close-out
hand-back decision (exit-gates R27), moved the same way (spec 2026-11-27-triage-leaves-split
R3).

Pure: no git, no forge, no clock.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from fr.triage.model import (
    ArchiveConflictEvent,
    Batch,
    CloseoutEvent,
    CloseoutHandbackEvent,
    ConflictEvent,
    DispatchEvent,
    RedHandbackEvent,
)
from fr.triage.queue_handback import reissue_due

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


def spends_handback(event: object) -> bool:
    """A conflict hand-back that spends the budget (R22): delivered, and not a re-issue
    (spec 2026-11-24-wave-queue-gaps R3)."""
    return isinstance(event, ConflictEvent) and event.delivered != "held" and not event.reissue


ConflictKind = Literal["skip", "reissue", "wait-behind", "held", "handback"]


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
    leads: bool | None = None,
) -> ConflictDecision:
    """The pure decision on a conflict at *head* refusing *paths* (R21, R22).

    `skip`: a `conflict` event already exists for this head, so a restarted driver
    does not hand the same head back again (only a `reissue`, below, briefs it once more,
    free). `wait-behind`: a refused path is shared
    with a conflict met earlier in this pass (*earlier_in_pass*, `(batch, paths)` in
    train order), which is fixed first. `held`: two `session|fresh` hand-backs were
    made since the batch's latest `dispatch` event (held ones never count). Else
    `handback`.

    `reissue` (spec 2026-11-24-wave-queue-gaps R2, R3): the head's latest `conflict` event
    named a commit (`onto`) that no longer leads to `main` (*leads* False): the brief goes
    out again, free. Any other head with a `conflict` event is a `skip`.
    """
    if any(isinstance(e, ConflictEvent) and e.head == head for e in events):
        return ConflictDecision("reissue" if reissue_due(events, head, leads) else "skip")
    mine = set(paths)
    for batch_id, theirs in earlier_in_pass:
        if mine.intersection(theirs):
            return ConflictDecision("wait-behind", behind=batch_id)
    handed = handbacks_since(events, spends_handback)
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


def conflict_at(batch: Batch, head: str) -> ConflictEvent | None:
    """The batch's latest `conflict` event at PR head *head*, whatever it delivered
    (batch-train-truth R18): a PR so recorded is never one to approve."""
    for event in reversed(batch.events):
        if isinstance(event, ConflictEvent) and event.head == head:
            return event
    return None


def fresh_conflicts(batch: Batch, *, since_dispatch: bool) -> int:
    """How many fresh conflict sessions the batch started: all of them (the next one's
    number), or only since its latest dispatch (whether one is the message target)."""
    return handbacks_since(
        batch.events,
        lambda e: isinstance(e, ConflictEvent) and e.delivered == "fresh",
        reset=since_dispatch,
    )


def conflict_item_id(repo: str, batch_id: str, n: int) -> str:
    """`<OWNER>/<REPO>/run/conflict-<batch-id>-<n>`: the *n*th fresh conflict session."""
    return f"{repo}/run/conflict-{batch_id}-{n}"


# ------------------------------------------ archive conflicts (merge-truth R12, §E)

ARCHIVE_HANDBACKS_PER_CLOSEOUT = 2
"""R12: hand-backs a conflicting archive PR gets per close-out before it is the operator's."""

ArchiveConflictKind = Literal["skip", "held", "handback"]


def archive_conflict_decision(events: Sequence[object], head: str) -> ArchiveConflictKind:
    """The pure decision on an archive PR conflicting at *head* (R12).

    `skip`: an `archive_conflict` event exists for this head, so a restarted driver
    does not hand the same head back again (an archive PR has no free re-issue; that is
    the batch PR's `conflict_decision`). `held`: two `session|fresh` hand-backs were
    made since the batch's latest close-out event (held ones never count; a batch PR's
    `conflict` events are another counter). Else `handback`."""
    if any(isinstance(e, ArchiveConflictEvent) and e.head == head for e in events):
        return "skip"
    handed = 0
    for event in reversed(events):
        if isinstance(event, CloseoutEvent):
            break
        if isinstance(event, ArchiveConflictEvent) and event.delivered != "held":
            handed += 1
    return "held" if handed >= ARCHIVE_HANDBACKS_PER_CLOSEOUT else "handback"


def held_archive_conflict(batch: Batch) -> ArchiveConflictEvent | None:
    """The batch's latest `archive_conflict` event when it is `held` and no close-out
    event came after it (R12): the operator owns that conflict."""
    for event in reversed(batch.events):
        if isinstance(event, CloseoutEvent):
            return None
        if isinstance(event, ArchiveConflictEvent):
            return event if event.delivered == "held" else None
    return None


def _held_archive_conflict(batch: Batch, head: str) -> bool:
    held = held_archive_conflict(batch)
    return held is not None and held.head == head


def archive_conflict_item_id(repo: str, batch_id: str, n: int) -> str:
    """`<OWNER>/<REPO>/run/archive-conflict-<batch-id>-<n>`: the *n*th fresh session
    started for the batch's conflicting archive PR."""
    return f"{repo}/run/archive-conflict-{batch_id}-{n}"


# ------------------------------------------- collected close-out hand-back (R27)

CLOSEOUT_HANDBACKS = 1
"""R27: hand-backs a collected close-out gets, counted per close-out item across its
members; apart from conflict and red hand-backs, which count per batch dispatch."""

CloseoutDecisionKind = Literal["skip", "handback", "stuck"]


def closeout_handback_decision(
    events: Iterable[object], item: str, head: str, handed: Iterable[str] = ()
) -> CloseoutDecisionKind:
    """What the driver does with collected close-out *item*'s PR failing at *head*, from
    every member's events (R27): `skip`, its session was handed it at this head already;
    `stuck`, no session could take the hand-back at this head, or the one hand-back went
    out at an earlier head (a second failure); else `handback`."""
    mine = [e for e in events if isinstance(e, CloseoutHandbackEvent) and e.item == item]
    here = [e for e in mine if e.head == head]
    if here:
        return "stuck" if all(e.delivered == "none" for e in here) else "skip"
    heads = {e.head for e in mine} | set(handed)  # the marker's own count (p6b-r10)
    if head in heads:
        return "skip"
    return "stuck" if len(heads) >= CLOSEOUT_HANDBACKS else "handback"
