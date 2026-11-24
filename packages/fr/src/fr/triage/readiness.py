"""A batch PR's merge readiness, as one pure verdict (spec 2026-11-24-batch-merge-readiness
R1-R6).

`batch_readiness(batch, qs)` is the one place a batch PR's readiness is decided. The wave
merge queue admits a batch entry by its `admits` (`fr.triage.wave_queue._ready`), the
driver's member classification reports by it (`fr.triage.batch_drive._member_reports`) and
the Batches page shows its verdict, so given the same `QueueSnapshot` none of them can
contradict another (R4).

`admits` is the queue's admission rule (wave-merge-queue R3: `pr-open`, eligible, a valid
approval, its own head green, on the default branch, no pre-merge gate) AND delivered (R1,
R2). Delivered means the run cursor read at the PR's live head, folded over every cursor
naming its branch (`fr.triage.cursor.fold_positions`), records `deliver` done; every other
read is a reason it is not (`delivered`).

The verdict is exactly one of R5's, decided in this order, first match wins (`R5_ORDER`,
`_decide`):

1. `queue-held`: Not ready: queue held: <reason>
2. `approved-not-delivered` / `not-delivered`: Approved, not delivered / Not ready: not
   delivered: <R1 reason>
3. `ci-red` / `ci-running`: Not ready: CI red: <failing checks> / Not ready: CI running
4. `gate-held`: Not ready: held by a pre-merge gate
5. `other-base`: Not ready: based on <branch>, not <default>
6. `approval-voided`: Approval voided by a push at <sha>: re-label once Ready for approval
7. `conflicting`: Not ready: conflicting: <paths> (unapproved only: an approved entry's
   conflict is the queue's to find and eject)
8. `ready-for-approval`: Ready for approval (no valid approval)
9. `merges-next` / `queued-behind`: Approved, merges next / Approved, queued behind <entry>
   (`in_queue_order`, from the plan's own entry order)

Merge state (clean, behind, conflicting) never changes `admits`. A batch with no open PR
reads `not-open`, outside R5's list, and is never admitted.

Pure: no git, no forge, no clock read (the time is `QueueSnapshot.now`).
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from fr.labels import pre_merge_held
from fr.triage.approval import (
    ApprovalVerdict,
    Approved,
    First,
    Held,
    Void,
    is_approved,
)
from fr.triage.batch import QueueEntry
from fr.triage.batch_drive import LivePr
from fr.triage.mergeability import conflicting
from fr.triage.model import ApprovalEvent, Batch, ConflictEvent, CursorPosition, CursorRead
from fr.triage.wave_queue import QueueSnapshot, base_refusal, is_deferred, queue_held_reason

DeliveredState = Literal["delivered", "at-step", "no-cursor", "unread", "no-clone", "stale-head"]
VerdictKind = Literal[
    "queue-held",
    "approved-not-delivered",
    "not-delivered",
    "ci-red",
    "ci-running",
    "gate-held",
    "other-base",
    "approval-voided",
    "conflicting",
    "ready-for-approval",
    "merges-next",
    "queued-behind",
    "not-open",
]
R5_ORDER: tuple[tuple[VerdictKind, ...], ...] = (
    ("queue-held",),
    ("approved-not-delivered", "not-delivered"),
    ("ci-red", "ci-running"),
    ("gate-held",),
    ("other-base",),
    ("approval-voided",),
    ("conflicting",),
    ("ready-for-approval",),
    ("merges-next", "queued-behind"),
)
"""R5's verdicts in the order `_decide` tries them, first match wins."""

_LINES: dict[VerdictKind, str] = {
    "queue-held": "Not ready: queue held: {r}",
    "approved-not-delivered": "Approved, not delivered",
    "not-delivered": "Not ready: not delivered: {r}",
    "ci-red": "Not ready: CI red: {r}",
    "ci-running": "Not ready: CI running",
    "gate-held": "Not ready: held by a pre-merge gate",
    "other-base": "Not ready: {r}",
    "approval-voided": "Approval voided by a push at {r}: re-label once Ready for approval",
    "conflicting": "Not ready: conflicting: {r}",
    "ready-for-approval": "Ready for approval",
    "merges-next": "Approved, merges next",
    "queued-behind": "Approved, queued behind {r}",
    "not-open": "Not ready: no open PR",
}

NO_CURSOR_ACTION = "merge it by hand after review, or deliver it through a run"
"""R12: the next action of a batch PR whose head carries no run cursor naming its branch."""

Mover = Literal["session", "driver", "operator"]


@dataclass(frozen=True)
class Delivered:
    """R1: whether the batch PR's run delivered at its live head, and the reason when not."""

    state: DeliveredState
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.state == "delivered"


@dataclass(frozen=True)
class ReadinessFacts:
    """R6: what the verdict came from, one line each, and the next action's link."""

    delivered: str
    ci: str
    merge: str
    approval: str
    whose_move: str
    next_action: str
    link: str


@dataclass(frozen=True)
class Readiness:
    """One batch PR's verdict (R5): its *kind*, the line the page leads with (*verdict*),
    the *reason* inside it, the R6 *facts*, R1's *delivered*, whether its approval is valid
    (*approved*) and whether the queue *admits* it."""

    kind: VerdictKind
    verdict: str
    reason: str
    facts: ReadinessFacts
    admits: bool
    delivered: Delivered
    approved: bool = False


def _short(sha: str) -> str:
    return sha[:12] if sha else "an unread head"


def delivered(batch: Batch, pr: LivePr, qs: QueueSnapshot) -> Delivered:
    """R1 from `qs.cursors`: the cursor's read status, the head it was read at and its
    folded position, compared with the PR's live head."""
    read = qs.cursors.get(batch.id)
    if read is None or read[2] is None:
        return Delivered("unread", "the run cursor was not read")
    head, position, status = read
    if status == "no-clone":
        return Delivered("no-clone", f"no clone of {qs.repo} to read the run cursor from")
    if status != "read":
        return Delivered("unread", f"the run cursor at {_short(head)} could not be read")
    if head != pr.head:
        why = f"the run cursor was read at {_short(head)}, the PR is at {_short(pr.head)}"
        return Delivered("stale-head", why)
    if position is None:
        return Delivered("no-cursor", f"no run cursor names {pr.head_ref or 'its branch'}")
    if position.kind != "deliver-done":
        return Delivered("at-step", f"run {position.run} is at {position.step}")
    return Delivered("delivered")


def _admission(batch: Batch, pr: LivePr, qs: QueueSnapshot, approved: bool) -> bool:
    """Wave-merge-queue R3 for a batch entry, before delivered."""
    if qs.stages.get(batch.id) != "pr-open" or is_deferred(batch):
        return False
    if qs.eligible is not None and batch.id not in qs.eligible:
        return False
    return approved and not _gated(batch, pr, qs) and not base_refusal(pr, qs) \
        and pr.checks == "green"  # fmt: skip


def _gated(batch: Batch, pr: LivePr, qs: QueueSnapshot) -> bool:
    """R26: a gate:devops entry waits for the DevOps stage's release."""
    return bool(pre_merge_held(pr.labels)) and batch.id not in qs.released


def _voided_sha(batch: Batch, pr: LivePr, verdict: ApprovalVerdict | None) -> str | None:
    """R3: the push that voided the approval, None when none did. Before settlement
    (`Void`) the live head; after it, the last approval event's `voided_at` (never
    `approval.voided_at()`, which returns the approved head)."""
    if isinstance(verdict, Void):
        return pr.head
    if verdict is not None and is_approved(verdict):
        return None
    last = [e for e in batch.events if isinstance(e, ApprovalEvent) and e.pr == pr.number]
    return last[-1].voided_at if last else None


def _conflict_paths(batch: Batch, pr: LivePr, qs: QueueSnapshot) -> tuple[str, ...]:
    """The paths a conflict at the PR's live head names: the executor's, else the probe's."""
    met = qs.conflicts.get(batch.id)
    if met is not None and met.head == pr.head:
        return met.paths
    for event in reversed(batch.events):
        if isinstance(event, ConflictEvent) and event.head == pr.head:
            return tuple(event.paths)
    return ()


def _ci_fact(pr: LivePr) -> str:
    at = f"at {_short(pr.head)}"
    if pr.checks == "failing":
        return f"red: {', '.join(pr.failing) or 'checks failing'} {at}"
    return f"{'green' if pr.checks == 'green' else 'running'} {at}"


def _merge_fact(batch: Batch, pr: LivePr, qs: QueueSnapshot) -> str:
    if conflicting(pr.mergeable, pr.merge_state):
        paths = _conflict_paths(batch, pr, qs)
        return f"conflicting: {', '.join(paths)}" if paths else "conflicting"
    if pr.merge_state == "BEHIND":
        return "behind"
    return "clean" if pr.mergeable == "MERGEABLE" else "unknown"


def _approval_fact(verdict: ApprovalVerdict | None, voided: str | None) -> str:
    if isinstance(verdict, Approved):
        return f"recorded at {_short(verdict.approved_head)}"
    if isinstance(verdict, First):
        return f"recorded at {_short(verdict.head)}"
    if isinstance(verdict, Held):
        return f"held unreadable: {verdict.why}"
    if voided is not None:
        return f"voided by a push at {_short(voided)}"
    return "none"


def _mover(kind: VerdictKind, state: DeliveredState) -> Mover:
    if kind in ("approved-not-delivered", "not-delivered"):
        if state == "at-step":
            return "session"
        return "driver" if state in ("unread", "stale-head") else "operator"
    if kind in ("ci-red", "conflicting"):
        return "session"
    return "driver" if kind in ("ci-running", "merges-next", "queued-behind") else "operator"


def _whose_move(mover: Mover, batch: Batch, qs: QueueSnapshot) -> str:
    if mover != "session":
        return "the driver" if mover == "driver" else "the operator"
    status = qs.sessions.get(batch.id)
    if status == "idle":
        since = qs.head_changed.get(batch.id)
        if since is None:
            return "the session, idle"
        return f"the session, idle for {int((qs.now - since).total_seconds() // 60)} minutes"
    if status in ("absent", "done"):
        return f"the operator (the session is {status})"
    return "the session, working"


def _next(kind: VerdictKind, d: Delivered, mover: Mover, batch: Batch, pr: LivePr,
          qs: QueueSnapshot) -> tuple[str, str]:  # fmt: skip
    """R6's next action and its link: the PR, its checks tab, or the pane focus command."""
    if d.state == "no-cursor":
        return NO_CURSOR_ACTION, pr.url
    if kind in ("ci-red", "ci-running"):
        what = "fix the failing checks" if kind == "ci-red" else "wait for CI"
        return what, f"{pr.url}/checks" if pr.url else ""
    if mover == "session":
        focus = shlex.join(["fr", "triage", "batch", "focus", batch.id, *qs.scope_args])
        return "let the session finish, or focus it", focus
    actions: dict[str, str] = {
        "approval-voided": "re-label `approved-fr` once the PR reads Ready for approval",
        "ready-for-approval": "review the PR and label it `approved-fr`",
        "merges-next": "none: the queue merges it",
        "queued-behind": "none: the queue merges it",
        "gate-held": "pass the DevOps stage",
    }
    return actions.get(kind, "look at the PR"), pr.url


def _decide(batch: Batch, pr: LivePr, qs: QueueSnapshot, d: Delivered,
            approved: bool, voided: str | None) -> tuple[VerdictKind, str]:  # fmt: skip
    """R5, in `R5_ORDER`: the first verdict that applies, and its reason."""
    held = queue_held_reason(qs)
    if held:
        return "queue-held", held
    if not d.ok:
        return ("approved-not-delivered", d.reason) if approved else ("not-delivered", d.reason)
    if pr.checks == "failing":
        return "ci-red", ", ".join(pr.failing) or "checks failing"
    if pr.checks != "green":
        return "ci-running", ""
    if _gated(batch, pr, qs):
        return "gate-held", ""
    refused = base_refusal(pr, qs)
    if refused:
        return "other-base", refused.removeprefix("is ")
    if voided is not None:
        return "approval-voided", _short(voided)
    if not approved and conflicting(pr.mergeable, pr.merge_state):
        return "conflicting", ", ".join(_conflict_paths(batch, pr, qs)) or "paths unknown"
    return ("merges-next", "") if approved else ("ready-for-approval", "")


def batch_readiness(batch: Batch, qs: QueueSnapshot) -> Readiness:
    """*batch*'s verdict, facts and admission over *qs* (R1-R6)."""
    pr = qs.live.get(batch.id)
    verdict = qs.approvals.get(batch.id)
    if pr is None or pr.state != "OPEN":
        facts = ReadinessFacts("unknown", "unknown", "unknown", "none", "the driver", "", "")
        return Readiness("not-open", _LINES["not-open"], "", facts, False,
                         Delivered("unread", "no open PR"))  # fmt: skip
    d = delivered(batch, pr, qs)
    approved = verdict is not None and is_approved(verdict)
    voided = _voided_sha(batch, pr, verdict)
    kind, reason = _decide(batch, pr, qs, d, approved, voided)
    mover = _mover(kind, d.state)
    action, link = _next(kind, d, mover, batch, pr, qs)
    facts = ReadinessFacts(
        delivered="yes" if d.ok else d.reason,
        ci=_ci_fact(pr),
        merge=_merge_fact(batch, pr, qs),
        approval=_approval_fact(verdict, voided),
        whose_move=_whose_move(mover, batch, qs),
        next_action=action,
        link=link,
    )
    admits = d.ok and _admission(batch, pr, qs, approved)
    return Readiness(kind, _LINES[kind].format(r=reason), reason, facts, admits, d, approved)


def fact_cursors(
    queue: Iterable[QueueEntry],
) -> dict[str, tuple[str, CursorPosition | None, CursorRead | None]]:
    """Each queued batch's run cursor as collect read it (R1): the head it was read at, its
    folded position and the read status. The driver and the board both build
    `Snapshot.cursors` with it, so the verdict reads one input path."""
    return {e.batch.id: (e.pr.head_oid, e.pr.cursor, e.pr.cursor_read) for e in queue}


def in_queue_order(r: Readiness, key: str, order: Sequence[str]) -> Readiness:
    """An approved verdict placed in the plan's entry *order* (R5's last pair): merges next
    when *key* leads it (or is not in it), else queued behind the entry before it."""
    if r.kind not in ("merges-next", "queued-behind") or key not in order:
        return r
    at = list(order).index(key)
    if at == 0:
        return replace(r, kind="merges-next", verdict=_LINES["merges-next"], reason="")
    ahead = order[at - 1]
    return replace(r, kind="queued-behind", reason=ahead,
                   verdict=_LINES["queued-behind"].format(r=ahead))  # fmt: skip
