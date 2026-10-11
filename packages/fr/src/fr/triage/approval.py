"""The approval gate's verdict (spec 2026-10-11-merge-train-safety §A, R1-R2).

`approval_verdict` is pure: the batch's events, the PR's number, live head and labels
in, one `ApprovalVerdict` out. The walk, the board and every merge path read it, so a
PR is approved the same way everywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fr.labels import APPROVED_FR
from fr.triage.model import ApprovalEvent, BatchEvent, UpdateEvent


@dataclass(frozen=True)
class Approved:
    """The label is on, and fr's own updates lead from *approved_head* to the head."""

    approved_head: str


@dataclass(frozen=True)
class Unlabelled:
    """The label is absent: a recorded approval does not outlive its label."""


@dataclass(frozen=True)
class First:
    """The label is on and no approval is live: *head* is the one to record."""

    head: str


@dataclass(frozen=True)
class Void:
    """The label is on, but the head moved away from *approved_head* by a push fr did
    not make."""

    approved_head: str


ApprovalVerdict = Approved | Unlabelled | First | Void


def approval_verdict(
    events: Sequence[BatchEvent], pr: int, head: str, labels: Sequence[str] | None
) -> ApprovalVerdict:
    """Whether PR #*pr* at *head* carries a valid approval (§A "The verdict")."""
    if labels is None or APPROVED_FR.name not in labels:
        return Unlabelled()
    live: int | None = None
    for i, event in enumerate(events):
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            live = None if event.voided_at is not None else i
    if live is None:
        return First(head)
    approved = events[live]
    assert isinstance(approved, ApprovalEvent)
    reached = approved.head
    if reached == head:
        return Approved(approved.head)
    for event in events[live + 1 :]:
        if isinstance(event, UpdateEvent) and event.pr == pr and event.head_before == reached:
            reached = event.head_after
            if reached == head:
                return Approved(approved.head)
    return Void(approved.head)


def is_approved(verdict: ApprovalVerdict) -> bool:
    """`Approved` or `First`: a train member fr may merge once it is green (§A "The walk")."""
    return isinstance(verdict, Approved | First)
