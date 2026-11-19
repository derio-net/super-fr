"""The approval gate (spec 2026-10-11-merge-train-safety §A, R1-R2, R4).

`approval_verdict` is pure: the batch's events, the PR's number, live head, labels and
patch-id in, one `ApprovalVerdict` out. The walk, the board and every merge path read it,
so a PR is approved the same way everywhere. `settle_approvals` is the one place an
approval is recorded or voided; it reaches the forge only through the `GhClient` passed
in, the judgements file only through the writer passed in, and git only through the
`patch_id_of` reader passed in: this module runs no git.

The verdict rule (spec 2026-11-19-wave-merge-queue R12, §E): approval is pinned to
content. With no `approved-fr` label the PR is `Unlabelled`; with the label and no live
approval it is `First`. A live approval that recorded a patch-id is `Approved` while the
PR's live patch-id equals it, at any head (a merge of `main` with no conflict
resolution, an empty commit), and `Void` once it differs (any change to the PR's own
diff, whitespace and binary edits included). An approval recorded before schema 13 has
no patch-id, and one whose live patch-id cannot be read is judged the old way: it holds
only while fr's own recorded updates lead from the approved head to the live one
(`reaches`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fr.labels import APPROVED_FR, READY_FR
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
    live: int | None = None
    for i, event in enumerate(events):
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            live = None if event.voided_at is not None else i
    if live is None:
        return First(head)
    approved = events[live]
    assert isinstance(approved, ApprovalEvent)
    if approved.patch_id is not None and patch_id is not None:
        return Approved(approved.head) if patch_id == approved.patch_id else Void(approved.head)
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

PatchIdOf = Callable[[int, str], "str | None"]
"""The patch-id of PR *pr* at *head* (`Checkout.patch_id` against the default branch), or
None when it cannot be read: the command layer's reader, so this module runs no git."""


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
) -> dict[str, ApprovalVerdict]:
    """Record a `First` approval at the PR's live head, whatever its checks; void a
    `Void` one (remove the label, then record the void, so a failure between the two
    never leaves a label fr would re-approve at the moved head). Each open PR of
    *batches* (batch, PR number) is read live once. Returns the verdict after
    settling: a recorded `First` is `Approved`, a voided one `Unlabelled`. *dry_run*
    says what it would do and changes nothing (§A "Recording and voiding"). *patch_id_of*
    reads the live head's patch-id, which a `First` approval records and the verdict
    compares (wave-merge-queue R12); without it, approvals are judged by `reaches`."""
    out: dict[str, ApprovalVerdict] = {}
    for batch, number in batches:
        view = client.pr_view(repo, number)
        if view.get("state") != "OPEN":
            continue
        head = str(view.get("head_oid") or "")
        labels = view.get("labels")
        patch_id = (
            patch_id_of(number, head)
            if patch_id_of is not None and labels is not None and APPROVED_FR.name in labels
            else None
        )
        verdict = approval_verdict(batch.events, number, head, labels, patch_id=patch_id)
        voided_head = _voided_head(verdict)
        if isinstance(verdict, First):
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
                say(f"would void approval of PR #{number} at {was[:12]}: head moved to {head[:12]}")
            elif (off := _labels_off(client, repo)) is not None:
                # R9: the label stays, so no void is recorded and nothing is approved
                say(f"approval of PR #{number} at {was[:12]} not voided: {off}")
            else:
                client.edit_issue_labels(
                    repo, number, add=frozenset(), remove=frozenset({APPROVED_FR.name})
                )
                recorded = _live_approval(batch.events, number)
                writer(
                    batch.id,
                    ApprovalEvent(
                        kind="approval", at=now, pr=number, head=was, voided_at=head,
                        patch_id=recorded.patch_id if recorded is not None else None,
                    ),
                )  # fmt: skip
                why = _why_void(recorded, head, patch_id)
                say(f"approval of PR #{number} at {was[:12]} voided: {why}")
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


def _live_approval(events: Sequence[BatchEvent], pr: int) -> ApprovalEvent | None:
    """PR *pr*'s last approval event, when it is live (not voided)."""
    last = None
    for event in events:
        if isinstance(event, ApprovalEvent) and event.pr == pr:
            last = event
    return last if last is not None and last.voided_at is None else None


def _why_void(recorded: ApprovalEvent | None, head: str, patch_id: str | None) -> str:
    """What voided an approval, as said: its diff changed (R12, both patch-ids known), or
    its head moved by a push fr did not make (`reaches`)."""
    if recorded is not None and recorded.patch_id is not None and patch_id is not None:
        return f"its diff changed at {head[:12]}"
    return f"head moved to {head[:12]}"


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
