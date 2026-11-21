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
updates' after it), at a head that follows the approved one only by moves that cannot change
the diff (`Checkout.clean_succession`: the approved head is an ancestor and every commit
between is an empty non-merge commit or a merge whose tree is the automatic merge of its
parents, so a conflict-free merge of `main` and an empty commit keep it; l-security-r1).
`git patch-id` drops hunk line numbers, so it alone would pass a push that moves an
otherwise identical hunk; the succession check is what refuses that. Otherwise, and for an approval recorded before schema 13 (no patch-id) or a live
patch-id that cannot be read, it is `Approved` only while fr's own recorded updates lead
from the approved head to the live one (`reaches`): the approved head itself, or an update
the retired merge train recorded. Nothing writes an `update` event any more (the queue never
touches a PR branch, R22): `reaches` and the pinned ids of `UpdateEvent` stay only so that a
`judgements.yaml` written before that still judges its open PRs as it did. Anything else is `Void`:
a push fr did not make that changes the PR's own diff, whitespace and binary edits
included, a moved hunk, a hand-edited merge resolution, a rewrite of the branch. A live
patch-id or succession that git cannot read is `Held`, never `Void` (l-errors-r4): the
label stays, nothing is recorded, and the entry waits for a pass that can read.

`judge_approval` is the one reading every call site makes: it reads the live patch-id
only for a labelled PR, and reads it once more against a refetched default branch before
a mismatch voids (a merge base newer than the clone's copy of the default branch moves
the id; the re-read tells that from a real change).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from fr.labels import APPROVED_FR, QUEUE_POSTMERGE_DONE, QUEUE_RELEASE, READY_FR
from fr.triage.model import (
    ApprovalEvent,
    Batch,
    BatchEvent,
    Facts,
    PullRequest,
    QueueApprovalEvent,
    QueueEntryRef,
    QueuePostmergeDoneEvent,
    QueueReleaseEvent,
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


@dataclass(frozen=True)
class Held:
    """The label is on and an approval is live, but git could not say whether the head is
    still the approved diff (*why*), and `reaches` does not prove it: neither approved nor
    voided this pass (l-errors-r4)."""

    approved_head: str
    why: str


ApprovalVerdict = Approved | Unlabelled | First | Void | Held


def approval_verdict(
    events: Sequence[BatchEvent],
    pr: int,
    head: str,
    labels: Sequence[str] | None,
    *,
    patch_id: str | None = None,
    clean_since: Callable[[str], bool | None] | None = None,
) -> ApprovalVerdict:
    """Whether PR #*pr* at *head*, whose live patch-id is *patch_id* (None when unread),
    carries a valid approval: the rule in this module's docstring. *clean_since* answers,
    for an approved head, whether the live head follows it by diff-neutral moves only
    (None when git cannot say); without it a patch-id match stands alone."""
    if labels is None or APPROVED_FR.name not in labels:
        return Unlabelled()
    live = _live_index(events, pr)
    if live is None:
        return First(head)
    approved = events[live]
    assert isinstance(approved, ApprovalEvent)
    if reaches(events[live + 1 :], pr, approved.head, head):
        return Approved(approved.head)
    if patch_id is not None and patch_id in _pinned_ids(events[live:], pr):
        clean = True if clean_since is None else clean_since(approved.head)
        if clean:
            return Approved(approved.head)
        if clean is None:
            return Held(approved.head, f"could not read how {head[:12]} follows the approved head")
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
    """`Approved` or `First`: a queue member once it is green (§A "The walk"; R3)."""
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
    since = getattr(patch_id_of, "clean_since", None)

    def verdict_of(patch_id: str | None) -> ApprovalVerdict:
        def clean(approved: str) -> bool | None:
            return None if since is None else since(pr, approved, head)

        verdict = approval_verdict(
            events, pr, head, labels, patch_id=patch_id,
            clean_since=None if since is None else clean,
        )  # fmt: skip
        if isinstance(verdict, Void) and patch_id is None:
            # l-errors-r4: an unreadable patch-id is no change; never void on it
            return Held(verdict.approved_head, f"could not read the patch-id of {head[:12]}")
        return verdict

    patch_id = patch_id_of(pr, head)
    verdict = verdict_of(patch_id)
    if isinstance(verdict, Void) and patch_id is not None and approved_patch_ids(events, pr):
        patch_id = patch_id_of(pr, head, fresh=True)
        verdict = verdict_of(patch_id)
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
        elif isinstance(verdict, Held):
            say(f"warning: approval of PR #{number} at {verdict.approved_head[:12]} held this "
                f"pass, label kept: {verdict.why}")  # fmt: skip
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
    if isinstance(verdict, Held):
        say(f"warning: approval of PR #{number} at {verdict.approved_head[:12]} held this "
            f"pass, label kept: {verdict.why}")  # fmt: skip
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


RELEASE_MARKER_PREFIX = "<!-- fr-queue:release"
_RELEASE_MARKER = re.compile(
    r"<!-- fr-queue:release head=(?P<head>[0-9a-f]+) patch-id=(?P<patch>[0-9a-f]*) -->"
)
_TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def release_marker(head: str, patch_id: str) -> str:
    """The comment the DevOps stage's stage 2 writes on the PR it releases (R26): the head
    and patch-id it verified, which the driver records the release at (never a live head)."""
    return f"{RELEASE_MARKER_PREFIX} head={head} patch-id={patch_id} -->"


def read_release_marker(comments: Sequence[dict[str, Any]]) -> tuple[str, str] | None:
    """The `(head, patch_id)` of the last `fr-queue:release` marker comment written by a
    repo owner, member or collaborator, or None."""
    found: tuple[str, str] | None = None
    for c in comments:
        if str(c.get("association") or "") not in _TRUSTED_ASSOCIATIONS:
            continue
        m = _RELEASE_MARKER.search(str(c.get("body") or ""))
        if m is not None:
            found = (m["head"], m["patch"])
    return found


def settle_release(
    client: Any,
    record: Callable[[QueueReleaseEvent], None],
    repo: str,
    entry: QueueEntryRef,
    number: int,
    events: Sequence[QueueReleaseEvent],
    view: dict[str, Any],
    say: Callable[[str], None],
    *,
    now: datetime,
    dry_run: bool = False,
    patch_id_of: PatchIdOf | None = None,
    marker: tuple[str, str] | None = None,
) -> bool:
    """Settle the DevOps stage's `fr-queue:release` label on the open PR in *view* into a
    `queue_release` (R26, as `approved-fr` is settled): whether the entry (whose PR is
    *number*) is released now. *events* are this entry's `queue_release` events, in order;
    *marker* is `(head, patch_id)` of the stage's marker comment (`read_release_marker`).

    A label with no live event (none, or the last one voided) is a new release only at what
    stage 2 verified: the marker's patch-id must equal the live one (an unreadable live
    patch-id falls back to the marker's head being the live head), and it is recorded at
    that patch-id. A label with no marker, or a marker for another diff, is no release: the
    stage must run again. A label whose live event pinned another patch-id is stale: the
    PR's diff moved after the release, so the label is removed (R9: only while labels are
    on) and a void is recorded (`voided`), and the stage must run again. An unreadable
    patch-id keeps a recorded release only at the head it was recorded at. Nothing is
    written under *dry_run*."""
    if QUEUE_RELEASE.name not in {str(n) for n in view.get("labels") or ()}:
        return False
    head = str(view.get("head_oid") or "")
    patch_id = patch_id_of(number, head) if patch_id_of is not None else None
    last = events[-1] if events else None
    live = last if last is not None and not last.voided else None
    if live is not None:
        if patch_id is None:
            return head == live.head  # cannot read the diff: only the recorded head stands
        if live.patch_id == patch_id:
            return True
        # the diff moved since the release: re-read once against a fresh default branch
        patch_id_fresh = patch_id_of(number, head, fresh=True) if patch_id_of else None
        if patch_id_fresh == live.patch_id:
            return True
        if dry_run:
            say(f"would void the release of {entry_key(entry)}: its diff changed after it")
        elif (off := _labels_off(client, repo)) is not None:
            say(f"release of {entry_key(entry)} not voided: {off}")
            return False
        else:
            client.edit_issue_labels(
                repo, number, add=frozenset(), remove=frozenset({QUEUE_RELEASE.name})
            )
            record(QueueReleaseEvent(kind="queue_release", at=now, entry=entry, head=head,
                                     patch_id=live.patch_id, voided=True))  # fmt: skip
            say(f"release of {entry_key(entry)} voided: its diff changed after the DevOps "
                f"stage released it; run `fr ops gate` again")  # fmt: skip
        return False
    if marker is None:
        say(f"{entry_key(entry)} carries {QUEUE_RELEASE.name} but no release marker from the "
            "DevOps stage: not released; run `fr ops gate` for its run")  # fmt: skip
        return False
    m_head, m_patch = marker
    if patch_id is None:
        verified = head == m_head
    else:
        verified = patch_id == m_patch
        if not verified and patch_id_of is not None:
            verified = patch_id_of(number, head, fresh=True) == m_patch
    if not verified:
        say(f"{entry_key(entry)} was pushed to after the DevOps stage verified it at "
            f"{m_head[:12]}: not released; run `fr ops gate` again")  # fmt: skip
        return False
    if dry_run:
        say(f"would record the release of {entry_key(entry)} at {head[:12]}")
        return True
    record(QueueReleaseEvent(kind="queue_release", at=now, entry=entry, head=head,
                             patch_id=m_patch))  # fmt: skip
    say(f"release of {entry_key(entry)} recorded at {head[:12]}")
    return True


def settle_postmerge_done(
    record: Callable[[QueuePostmergeDoneEvent], None],
    entry: QueueEntryRef,
    view: dict[str, Any],
    say: Callable[[str], None],
    *,
    now: datetime,
    dry_run: bool = False,
) -> bool:
    """Settle `fr-queue:postmerge-done` on a landed *entry*'s merged PR into a
    `queue_postmerge_done` (R26): whether the label was there. Recorded once; the caller
    asks only for entries with none."""
    if QUEUE_POSTMERGE_DONE.name not in {str(n) for n in view.get("labels") or ()}:
        return False
    if dry_run:
        say(f"would record the post-merge ops of {entry_key(entry)} as done")
        return True
    record(QueuePostmergeDoneEvent(kind="queue_postmerge_done", at=now, entry=entry))
    say(f"post-merge ops of {entry_key(entry)} recorded as done: the barrier lifts")
    return True


def entry_key(ref: QueueEntryRef) -> str:
    """A queue entry's name: its batch id, or `<kind>#<pr>`."""
    return ref.batch if ref.batch is not None else f"{ref.kind}#{ref.pr}"


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
