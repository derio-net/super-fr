"""The board's Needs-you lanes (spec 2026-10-14-exit-gates R17, R18, §F).

`lane_of` is the ONE function `kanban.column_of` and `views.needs_you` both call, so
"Needs you now" and the four columns cannot disagree. It reads the run cursor at the
batch PR's head (`PullRequest.cursor`), the approval verdict, a live merge stop and the
merged PR's gate labels; never session status (that stays a secondary hint on the card).
A card leaves a lane through the person's own act: answering, approving, recording a pass.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fr.gatebackfill.trackers import pass_command
from fr.labels import awaiting_devops, held_gates, pre_merge_held
from fr.triage.approval import approval_verdict, is_approved
from fr.triage.batch import batch_pr, derive_batch_stage
from fr.triage.batch_drive import LANDED, closeout_event, fact_ledger_unknown, fact_ledgers
from fr.triage.merge_stops import MergeStop, live_stop
from fr.triage.model import Batch, Facts, PullRequest

Lane = Literal["needs-developer", "needs-reviewer", "needs-tester", "needs-devops"]


@dataclass(frozen=True)
class LaneVerdict:
    lane: Lane
    reason: str  # what the person owes, in the words a Need and a card hint share


def lane_of(batch: Batch, facts: Facts, stop: MergeStop | None = None) -> LaneVerdict | None:
    """The lane *batch* sits in, or None. *stop* is the batch's live merge stop (the
    caller judged it live against the PR head)."""
    if not batch.events:
        return None
    stage = derive_batch_stage(batch, facts)
    pr = batch_pr(batch, facts)
    if stage == "pr-open" and pr is not None:
        cursor = pr.cursor
        if cursor is not None and cursor.kind == "gate":
            return LaneVerdict(
                "needs-developer", f"run {cursor.run} is blocked on the {cursor.step} gate"
            )
        if cursor is not None and cursor.kind == "manual":
            return LaneVerdict(
                "needs-developer",
                f"run {cursor.run} waits on the manual unit {cursor.unit} of {cursor.step}",
            )
        if stop is not None:
            return LaneVerdict("needs-reviewer", f"merge stopped: {stop.reason}")
        if pre_merge_held(pr.labels):  # fr-ops R14: the DevOps stage owns the merge
            return LaneVerdict("needs-devops", awaiting_devops(pr.number))
        if cursor is not None and cursor.kind == "deliver-done":
            verdict = approval_verdict(batch.events, pr.number, pr.head_oid, pr.labels)
            if not is_approved(verdict):
                return LaneVerdict("needs-reviewer", f"PR #{pr.number} is delivered: approve it")
        return None
    if stage in LANDED and closeout_event(batch) is None:
        ledger = fact_ledgers([batch], facts, {batch.id: stage}).get(batch.id)
        if ledger is not None and pr is not None:
            return gated_pr_lane(pr)  # the ledger is this very PR's labels
    return None


def gated_pr_lane(pr: PullRequest) -> LaneVerdict | None:
    """The lane a MERGED PR's held post-merge gate puts it in: Tester first, else DevOps;
    None when no gate is held (none labelled, or each passed) or its labels were never
    read. The ONE held-gate rule: `lane_of`'s landed batches and the board's gate-labelled
    PRs outside batches (gate-backfill R13) both ask it.

    The reason carries `trackers.pass_command`, which names `--notes`; for devops it
    names `--no-run-evidence`, as the board has no checkout to find the run in."""
    held = held_gates(pr.labels or [])
    gates = [g for g in ("tester", "devops") if g in held]
    if not gates:
        return None
    owed = "; ".join(
        f"gate:{g} {'walk its gated rows, or ' if g == 'tester' else ''}"
        f"`{pass_command(g, pr.number)}`"
        for g in gates
    )
    lane: Lane = "needs-tester" if gates[0] == "tester" else "needs-devops"
    return LaneVerdict(lane, f"merged, held by {owed}")


def unlisted_gated_prs(
    batches: Sequence[Batch], facts: Facts, stops: Mapping[str, MergeStop]
) -> list[PullRequest]:
    """The `facts.gated_prs` that are NOT already a Needs-you lane card of their batch: a
    PR whose batch `lane_of` places is listed through that batch, and one whose batch's
    ledger could not be read waits on `ledger-unread` (gate-backfill R13). A closed-out
    batch's PR is `lane_of`-less, so it is listed here."""
    covered: set[tuple[str, int]] = set()
    for b in batches:
        pr = batch_pr(b, facts)
        if pr is None:
            continue
        stage = derive_batch_stage(b, facts)
        unread = b.id in fact_ledger_unknown([b], facts, {b.id: stage})
        if unread or lane_of(b, facts, stops.get(b.id)) is not None:
            covered.add((pr.repo, pr.number))
    return [p for p in facts.gated_prs if (p.repo, p.number) not in covered]


def live_stops(
    batches: Sequence[Batch], facts: Facts, stops: Mapping[str, MergeStop]
) -> dict[str, MergeStop]:
    """The recorded stops that still hold: the batch's PR is open, at the stopped head."""
    out: dict[str, MergeStop] = {}
    for b in batches:
        pr = batch_pr(b, facts)
        if pr is not None and pr.state == "OPEN":
            if (stop := live_stop(stops.get(b.id), pr.head_oid)) is not None:
                out[b.id] = stop
    return out
