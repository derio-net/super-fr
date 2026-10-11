"""The approval gate (spec 2026-10-11-merge-train-safety §A, R1-R2, R4).

`approval_verdict` is pure: the batch's events, the PR's number, live head and labels
in, one `ApprovalVerdict` out. The walk, the board and every merge path read it, so a
PR is approved the same way everywhere. `settle_approvals` is the one place an approval
is recorded or voided; it reaches the forge only through the `GhClient` passed in, and
the judgements file only through the writer passed in.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fr.labels import APPROVED_FR
from fr.triage.model import ApprovalEvent, Batch, BatchEvent, UpdateEvent


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


EventWriter = Callable[[str, BatchEvent], None]
"""Appends one event to batch *id* through the one judgements writer."""


def settle_approvals(
    client: Any,
    writer: EventWriter,
    repo: str,
    batches: Sequence[tuple[Batch, int]],
    say: Callable[[str], None],
    *,
    now: datetime,
    dry_run: bool = False,
) -> dict[str, ApprovalVerdict]:
    """Record a `First` approval at the PR's live head, whatever its checks; void a
    `Void` one (remove the label, then record the void, so a failure between the two
    never leaves a label fr would re-approve at the moved head). Each open PR of
    *batches* (batch, PR number) is read live once. Returns the verdict after
    settling: a recorded `First` is `Approved`, a voided one `Unlabelled`. *dry_run*
    says what it would do and changes nothing (§A "Recording and voiding")."""
    out: dict[str, ApprovalVerdict] = {}
    for batch, number in batches:
        view = client.pr_view(repo, number)
        if view.get("state") != "OPEN":
            continue
        head = str(view.get("head_oid") or "")
        verdict = approval_verdict(batch.events, number, head, view.get("labels"))
        if isinstance(verdict, First):
            if dry_run:
                say(f"would record approval of PR #{number} at {head[:12]}")
            else:
                writer(batch.id, ApprovalEvent(kind="approval", at=now, pr=number, head=head))
                say(f"approval of PR #{number} recorded at {head[:12]}")
                verdict = Approved(head)
        elif isinstance(verdict, Void):
            was = verdict.approved_head
            if dry_run:
                say(f"would void approval of PR #{number} at {was[:12]}: head moved to {head[:12]}")
            else:
                client.edit_issue_labels(
                    repo, number, add=frozenset(), remove=frozenset({APPROVED_FR.name})
                )
                writer(
                    batch.id,
                    ApprovalEvent(kind="approval", at=now, pr=number, head=was, voided_at=head),
                )
                say(f"approval of PR #{number} at {was[:12]} voided: head moved to {head[:12]}")
                verdict = Unlabelled()
        out[batch.id] = verdict
    return out
