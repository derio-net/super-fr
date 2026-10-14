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

from fr.labels import held_gates
from fr.triage.approval import approval_verdict, is_approved
from fr.triage.batch import batch_pr, derive_batch_stage
from fr.triage.batch_drive import LANDED, closeout_event, fact_ledger_unknown, fact_ledgers
from fr.triage.merge_stops import MergeStop, live_stop
from fr.triage.model import Batch, Facts

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
        if cursor is not None and cursor.kind == "deliver-done":
            verdict = approval_verdict(batch.events, pr.number, pr.head_oid, pr.labels)
            if not is_approved(verdict):
                return LaneVerdict("needs-reviewer", f"PR #{pr.number} is delivered: approve it")
        return None
    if stage in LANDED and closeout_event(batch) is None:
        stages = {batch.id: stage}
        if batch.id in fact_ledger_unknown([batch], facts, stages):
            return LaneVerdict(
                "needs-developer",
                "its merged PR's gate labels could not be read, so which gate holds it is "
                "unknown; the next collect retries",
            )
        ledger = fact_ledgers([batch], facts, stages).get(batch.id)
        held = held_gates(ledger.labels) if ledger is not None else frozenset()
        if "tester" in held:
            return LaneVerdict("needs-tester", "landed; the tester gate is unpassed")
        if "devops" in held:
            return LaneVerdict("needs-devops", "landed; the devops gate is unpassed")
    return None


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
