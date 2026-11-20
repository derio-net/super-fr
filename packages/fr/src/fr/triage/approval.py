"""The approval gate (spec 2026-10-11-merge-train-safety §A, R1-R2, R4).

`approval_verdict` is pure: the batch's events, the PR's number, live head, labels and
patch-id in, one `ApprovalVerdict` out. The walk, the board and every merge path read it,
so a PR is approved the same way everywhere. `settle_approvals` is the one place an
approval is recorded or voided; it reaches the forge only through the `GhClient` passed
in, the judgements file only through the writer passed in, and git only through the
`patch_id_of` reader passed in: this module runs no git.

The verdict rule (spec 2026-11-19-wave-merge-queue R12, §E): approval is pinned to
content. With no `approved-fr` label the PR is `Unlabelled`; with the label and no live
approval it is `First`. A live approval is `Approved` while the PR's live patch-id equals
one fr recorded since it (`approved_patch_ids`: the approval's own, and each of fr's own
updates' after it), at any head (a merge of `main` with no conflict resolution, an empty
commit). Otherwise, and for an approval recorded before schema 13 (no patch-id) or a live
patch-id that cannot be read, it is `Approved` only while fr's own recorded updates lead
from the approved head to the live one (`reaches`): the approved head itself, or an update
the retired merge train recorded. Nothing writes an `update` event any more (the queue never
touches a PR branch, R22): `reaches` and the pinned ids of `UpdateEvent` stay only so that a
`judgements.yaml` written before that still judges its open PRs as it did. Anything else is `Void`:
a push fr did not make that changes the PR's own diff, whitespace and binary edits
included. `git patch-id` drops hunk line numbers, so a push that moves an otherwise
identical hunk within a file keeps the id, and the approval: R12 states that limit.

`judge_approval` is the one reading every call site makes: it reads the live patch-id
only for a labelled PR, and reads it once more against a refetched default branch before
a mismatch voids (a merge base newer than the clone's copy of the default branch moves
the id; the re-read tells that from a real change).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from fr.labels import APPROVED_FR, READY_FR
from fr.triage.model import (
    ApprovalEvent,
    Batch,
    BatchEvent,
    Facts,
    PullRequest,
    QueueApprovalEvent,
    QueueEntryRef,
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
    events: Sequence[BatchEvent],
    pr: int,
    head: str,
    labels: Sequence[str] | None,
    *,
    patch_id: str | None = None,
) -> ApprovalVerdict:
    """Whether PR #*pr* at *head*, whose live patch-id is *patch_id* (None when unread),
    carries a valid approval: the rule in this module's docstring."""
    if labels is None or APPROVED_FR.name not in labels:
        return Unlabelled()
    live = _live_index(events, pr)
    if live is None:
        return First(head)
    approved = events[live]
    assert isinstance(approved, ApprovalEvent)
    if patch_id is not None and patch_id in _pinned_ids(events[live:], pr):
        return Approved(approved.head)
    if reaches(events[live + 1 :], pr, approved.head, head):
        return Approved(approved.head)
    return Void(approved.head)


def approved_patch_ids(events: Sequence[BatchEvent], pr: int) -> frozenset[str]:
    """The patch-ids PR *pr*'s live approval holds at (R12): the one it recorded and each
    one fr's own updates recorded after it. Empty with no live approval, or none known."""
    live = _live_index(events, pr)
    return frozenset() if live is None else _pinned_ids(events[live:], pr)


def _live_index(events: Sequence[BatchEvent], pr: int) -> int | None:
    live: int | None = None
    for i, event in enumerate(events):
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            live = None if event.voided_at is not None else i
    return live


def _pinned_ids(since: Sequence[BatchEvent], pr: int) -> frozenset[str]:
    """The ids recorded by *since*'s first event (the live approval) and the updates after."""
    ids = {
        e.patch_id
        for e in since
        if isinstance(e, ApprovalEvent | UpdateEvent) and e.pr == pr and e.patch_id is not None
    }
    return frozenset(ids)


def void_reason(events: Sequence[BatchEvent], pr: int, head: str, patch_id: str | None) -> str:
    """What voids PR *pr*'s live approval at *head*, as said: its diff changed (a recorded
    patch-id and the live one known, and different), or its head moved by a push fr did
    not make (judged by `reaches`)."""
    if patch_id is not None and approved_patch_ids(events, pr):
        return f"its diff changed at {head[:12]}"
    return f"head moved to {head[:12]}"


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


class PatchIdOf(Protocol):
    """The patch-id of PR *pr* at *head* (`Checkout.patch_id` against the default branch), or
    None when it cannot be read: the command layer's reader, so this module runs no git.
    *fresh* fetches the default branch first (at most once per reader), for the re-read
    `judge_approval` makes before a mismatch voids."""

    def __call__(self, pr: int, head: str, *, fresh: bool = False) -> str | None: ...


def judge_approval(
    events: Sequence[BatchEvent],
    pr: int,
    head: str,
    labels: Sequence[str] | None,
    patch_id_of: PatchIdOf | None,
) -> tuple[ApprovalVerdict, str | None]:
    """The verdict for PR *pr* at *head*, and the live patch-id it read (None when unread):
    read only for a labelled PR, and read again against a refetched default branch before
    a patch-id mismatch voids (p1-r3: a stale `origin/<default>` moves the merge base)."""
    if patch_id_of is None or labels is None or APPROVED_FR.name not in labels:
        return approval_verdict(events, pr, head, labels), None
    patch_id = patch_id_of(pr, head)
    verdict = approval_verdict(events, pr, head, labels, patch_id=patch_id)
    if isinstance(verdict, Void) and patch_id is not None and approved_patch_ids(events, pr):
        patch_id = patch_id_of(pr, head, fresh=True)
        verdict = approval_verdict(events, pr, head, labels, patch_id=patch_id)
    return verdict, patch_id


def settle_approvals(
    client: Any,
    writer: EventWriter,
    repo: str,
    batches: Sequence[tuple[Batch, int]],
    say: Callable[[str], None],
    *,
    now: datetime,
    dry_run: bool = False,
    patch_id_of: PatchIdOf | None = None,
    landed: Collection[str] = frozenset(),
) -> dict[str, ApprovalVerdict]:
    """Record a `First` approval at the PR's live head, whatever its checks; void a
    `Void` one (remove the label, then record the void, so a failure between the two
    never leaves a label fr would re-approve at the moved head). Each open PR of
    *batches* (batch, PR number) is read live once. Returns the verdict after
    settling: a recorded `First` is `Approved`, a voided one `Unlabelled`. *dry_run*
    says what it would do and changes nothing (§A "Recording and voiding"). *patch_id_of*
    reads the live head's patch-id, which a `First` approval records and the verdict
    compares (wave-merge-queue R12); without it, approvals are judged by `reaches`.
    A batch in *landed* (the merge queue landed it) is skipped: its PR is merged, and its
    approval is never read again, even while the forge still reads it open (R12, R35)."""
    out: dict[str, ApprovalVerdict] = {}
    for batch, number in batches:
        if batch.id in landed:
            continue
        view = client.pr_view(repo, number)
        if view.get("state") != "OPEN":
            continue
        head = str(view.get("head_oid") or "")
        verdict, patch_id = judge_approval(
            batch.events, number, head, view.get("labels"), patch_id_of
        )
        if isinstance(verdict, Approved) and _unpinned(batch.events, number, patch_id):
            # p1-r8: an approval recorded with no patch-id gains the one its head reads now,
            # so R12 applies from here on rather than `reaches` for the approval's life.
            assert patch_id is not None
            if dry_run:
                say(f"would pin approval of PR #{number} at {head[:12]} to its patch-id")
            else:
                writer(
                    batch.id,
                    ApprovalEvent(kind="approval", at=now, pr=number, head=head, patch_id=patch_id),
                )
                say(f"approval of PR #{number} at {head[:12]} pinned to its patch-id")
                verdict = Approved(head)
        elif isinstance(verdict, First):
            if dry_run:
                say(f"would record approval of PR #{number} at {head[:12]}")
            else:
                writer(
                    batch.id,
                    ApprovalEvent(kind="approval", at=now, pr=number, head=head, patch_id=patch_id),
                )
                say(f"approval of PR #{number} recorded at {head[:12]}")
                verdict = Approved(head)
        elif isinstance(verdict, Void):
            was = verdict.approved_head
            if dry_run:
                why = void_reason(batch.events, number, head, patch_id)
                say(f"would void approval of PR #{number} at {was[:12]}: {why}")
            elif (off := _labels_off(client, repo)) is not None:
                # R9: the label stays, so no void is recorded and nothing is approved
                say(f"approval of PR #{number} at {was[:12]} not voided: {off}")
            else:
                client.edit_issue_labels(
                    repo, number, add=frozenset(), remove=frozenset({APPROVED_FR.name})
                )
                why = void_reason(batch.events, number, head, patch_id)
                recorded = _live_approval(batch.events, number)
                writer(
                    batch.id,
                    ApprovalEvent(
                        kind="approval", at=now, pr=number, head=was, voided_at=head,
                        patch_id=recorded.patch_id if recorded is not None else None,
                    ),
                )  # fmt: skip
                say(f"approval of PR #{number} at {was[:12]} voided: {why}")
                verdict = Unlabelled()
        out[batch.id] = verdict
    return out


def settle_entry_approval(
    client: Any,
    record: Callable[[QueueApprovalEvent], None],
    repo: str,
    entry: QueueEntryRef,
    events: Sequence[QueueApprovalEvent],
    view: dict[str, Any],
    say: Callable[[str], None],
    *,
    now: datetime,
    dry_run: bool = False,
    patch_id_of: PatchIdOf | None = None,
) -> tuple[ApprovalVerdict, datetime | None]:
    """`settle_approvals` for a non-batch queue entry (R32: a DevOps housekeeping PR, whose
    `approved-fr` is recorded as a queue `approval` event instead of a batch's): the verdict
    for the open PR in *view* after settling, and when its live approval was recorded (None
    when it holds none). *events* are the queue's `approval` events of this entry, in order;
    the same rule judges them (R12: pinned to the patch-id; a push that changes the diff
    voids it, label removed first), and nothing is written under *dry_run*."""
    number = entry.pr
    assert number is not None
    as_batch: list[BatchEvent] = [
        ApprovalEvent(kind="approval", at=e.at, pr=number, head=e.head, voided_at=e.voided_at,
                      patch_id=e.patch_id)
        for e in events
        if e.entry.pr == number and e.entry.kind == entry.kind
    ]  # fmt: skip
    head = str(view.get("head_oid") or "")
    verdict, patch_id = judge_approval(as_batch, number, head, view.get("labels"), patch_id_of)
    if isinstance(verdict, First):
        if dry_run:
            say(f"would record approval of PR #{number} at {head[:12]}")
            return verdict, None
        record(QueueApprovalEvent(kind="approval", at=now, entry=entry, head=head,
                                  patch_id=patch_id))  # fmt: skip
        say(f"approval of {entry.kind} PR #{number} recorded at {head[:12]}")
        return Approved(head), now
    if isinstance(verdict, Void):
        was = verdict.approved_head
        why = void_reason(as_batch, number, head, patch_id)
        if dry_run:
            say(f"would void approval of PR #{number} at {was[:12]}: {why}")
        elif (off := _labels_off(client, repo)) is not None:
            say(f"approval of PR #{number} at {was[:12]} not voided: {off}")  # R9
        else:
            client.edit_issue_labels(
                repo, number, add=frozenset(), remove=frozenset({APPROVED_FR.name})
            )
            recorded = _live_approval(as_batch, number)
            record(QueueApprovalEvent(
                kind="approval", at=now, entry=entry, head=was, voided_at=head,
                patch_id=recorded.patch_id if recorded is not None else None))  # fmt: skip
            say(f"approval of {entry.kind} PR #{number} at {was[:12]} voided: {why}")
            verdict = Unlabelled()
    live = _live_approval(as_batch, number) if is_approved(verdict) else None
    return verdict, live.at if live is not None else None


def _live_approval(events: Sequence[BatchEvent], pr: int) -> ApprovalEvent | None:
    """PR *pr*'s last approval event, when it is live (not voided)."""
    last = None
    for event in events:
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            last = event
    return last if last is not None and last.voided_at is None else None


def _unpinned(events: Sequence[BatchEvent], pr: int, patch_id: str | None) -> bool:
    """Whether PR *pr* has a live approval that no patch-id pins yet, and one was read."""
    return (
        patch_id is not None
        and _live_approval(events, pr) is not None
        and not approved_patch_ids(events, pr)
    )


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


def _labels_off(client: Any, repo: str) -> str | None:
    """Why fr writes no label on *repo* (R9: its `.fr/settings.yaml` at the default
    branch, through *client*), or why that policy is unknown; None when it may."""
    from fr.settings import SettingsError
    from fr.settings.remote import client_policy

    try:
        return client_policy(client, repo).block("labels")
    except SettingsError as exc:
        return str(exc)


def approval_label_missing(client: Any, repo: str) -> bool:
    """Whether *repo* lacks the `approved-fr` label that fr would create there: a READ
    (gh#1268). `fr triage collect` reports it and writes nothing; the first batch
    dispatch to the repo creates it (R4's other call sites). A repo whose labels are off,
    or a forge that cannot say, is never reported missing."""
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    soft: tuple[type[Exception], ...] = (UnsupportedForgeOperation, *FORGE_ERRORS)
    if _labels_off(client, repo) is not None:
        return False
    try:
        return not client.label_exists(repo, APPROVED_FR.name)
    except soft:
        return False


def ensure_approval_label(
    client: Any, repo: str, say: Callable[[str], None], *, seen: set[str]
) -> None:
    """Create the operator labels on *repo* when they are missing, saying so: `approved-fr`
    (§A "Label creation", R4) and `ready-fr`, which admits an outside author's issue
    (spec 2026-11-17-triage-intake R8). Each is checked and created on its own, so one that
    cannot be created never hides the other. At most one check per repo per *seen* (a pass or
    a command). A forge that cannot check or create labels is a warning per label, never a
    failure. fr only creates `ready-fr`; it never applies it."""
    if repo in seen:
        return
    seen.add(repo)
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    soft: tuple[type[Exception], ...] = (UnsupportedForgeOperation, *FORGE_ERRORS)
    off = _labels_off(client, repo)
    for label in (APPROVED_FR, READY_FR):
        if off is not None:
            say(f"label {label.name} not ensured on {repo}: {off}")
            continue
        try:
            if client.label_exists(repo, label.name):
                continue
            client.ensure_labels(repo, [label])
        except soft as exc:
            say(f"warning: cannot ensure label {label.name} on {repo}: {exc}")
            continue
        say(f"created label {label.name} on {repo}")
