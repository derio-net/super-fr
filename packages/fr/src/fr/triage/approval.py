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
from fr.triage.model import (
    ApprovalEvent,
    Batch,
    BatchEvent,
    EnqueueEvent,
    Facts,
    PullRequest,
    UpdateEvent,
)


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
    if reaches(events[live + 1 :], pr, approved.head, head):
        return Approved(approved.head)
    return Void(approved.head)


def reaches(events: Sequence[BatchEvent], pr: int, start: str, head: str) -> bool:
    """Whether fr's own recorded updates of PR *pr*, in order, lead from *start* to
    *head* (*start* itself included): a move fr made, never one a push made."""
    reached = start
    if reached == head:
        return True
    for event in events:
        if isinstance(event, UpdateEvent) and event.pr == pr and event.head_before == reached:
            reached = event.head_after
            if reached == head:
                return True
    return False


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
        voided_head = _voided_head(verdict)
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
        _dequeue_unapproved(
            client, writer, repo, batch, number, {head, voided_head}, verdict, say, now, dry_run
        )
        out[batch.id] = verdict
    return out


def _dequeue_unapproved(
    client: Any, writer: EventWriter, repo: str, batch: Batch, number: int, heads: set[str],
    verdict: ApprovalVerdict, say: Callable[[str], None], now: datetime, dry_run: bool,
) -> None:  # fmt: skip
    """A PR fr enqueued whose approval is gone is taken out of the queue (merge-train-safety
    §D, R13: GitHub would otherwise merge a PR the operator un-approved). Its last event is
    an `enqueued` one at the current head, or at the head a void names; a `dequeued` event
    supersedes it, so a later re-label enqueues it afresh. A forge that cannot dequeue is
    said, never fatal."""
    if is_approved(verdict):
        return
    last = next(
        (e for e in reversed(batch.events) if isinstance(e, EnqueueEvent) and e.pr == number),
        None,
    )
    if last is None or last.outcome != "enqueued" or last.head not in heads:
        return
    if dry_run:
        say(f"would dequeue PR #{number}: its {APPROVED_FR.name} approval is gone")
        return
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    soft: tuple[type[Exception], ...] = (UnsupportedForgeOperation, *FORGE_ERRORS)
    try:
        client.pr_dequeue(repo, number)
    except soft as exc:
        say(f"cannot dequeue PR #{number} though its {APPROVED_FR.name} approval is gone: {exc}")
        return
    writer(
        batch.id,
        EnqueueEvent(kind="enqueue", at=now, pr=number, head=last.head, base=last.base,
                     outcome="dequeued"),
    )  # fmt: skip
    say(f"dequeued PR #{number}: its {APPROVED_FR.name} approval is gone")


def _voided_head(verdict: ApprovalVerdict) -> str:
    return verdict.approved_head if isinstance(verdict, Void) else ""


def facts_without_label(facts: Facts, prs: set[tuple[str, int]], name: str) -> Facts:
    """*facts* with label *name* dropped from each PR in *prs* (`(OWNER/REPO, number)`),
    wherever the facts hold it: what the forge says once fr removed a voided approval's
    label, so a view rendered from this pass's facts never shows it (p1-r9)."""

    def drop(pr: PullRequest) -> PullRequest:
        if (pr.repo, pr.number) not in prs or pr.labels is None:
            return pr
        return pr.model_copy(update={"labels": [x for x in pr.labels if x != name]})

    return facts.model_copy(
        update={
            "prs": [drop(p) for p in facts.prs],
            "batch_prs": [drop(p) for p in facts.batch_prs],
            "judged_prs": [drop(p) for p in facts.judged_prs],
            "issues": [
                i.model_copy(update={"prs": [drop(p) for p in i.prs]}) for i in facts.issues
            ],
        }
    )


def voided_at(events: Sequence[BatchEvent], pr: int) -> str | None:
    """The approved head of PR *pr*'s last approval when that approval was voided, else
    None: after fr removed a voided label the verdict is `Unlabelled`, and the board
    still asks for a re-label naming that head (§A, R5)."""
    last = None
    for event in events:
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            last = event
    return last.head if last is not None and last.voided_at is not None else None


def ensure_approval_label(
    client: Any, repo: str, say: Callable[[str], None], *, seen: set[str]
) -> None:
    """Create the `approved-fr` label on *repo* when it is missing, saying so (§A "Label
    creation", R4). At most one check per repo per *seen* (a pass or a command). A
    forge that cannot check or create labels is a warning, never a failure."""
    if repo in seen:
        return
    seen.add(repo)
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    soft: tuple[type[Exception], ...] = (UnsupportedForgeOperation, *FORGE_ERRORS)
    try:
        if client.label_exists(repo, APPROVED_FR.name):
            return
        client.ensure_labels(repo, [APPROVED_FR])
    except soft as exc:
        say(f"warning: cannot ensure label {APPROVED_FR.name} on {repo}: {exc}")
        return
    say(f"created label {APPROVED_FR.name} on {repo}")
