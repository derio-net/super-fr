"""Historical review evidence — spec 2026-10-05-run-upgrade-midflight §D.

A phase reviewed BEFORE the cursor that now holds it existed (a run started on
an older `fr`, superseded or re-adopted after an upgrade) has a real review in
its plan journal and a reviewer whose dispatch lives in a transcript this
cursor never opened. `reviewer=historical` is the one reserved value that says
so — and it is accepted only inside the bound below, never as a way around the
separate-context reviewer check every other value still gets (#430/#497).

Pure, and importable by both `fr.commands.run_cmd` (the by-hand resolve) and
`fr.run.adopt` (adoption's inference) without a cycle: it imports neither.

**Trust model.** The bound reads `JournalEntry.created`, a stamp the journal's
author writes. fr cannot rule out an agent that writes a review entry and then
supersedes the run, so the human control is visibility: every historical review
is listed by name in the PR body (`fr.record.pr_body`) — `deliver` refuses a live
PR body missing any of those lines, not only the heading — and the operator's
review ok is given against that list.

`started` anchors clause 1, and it sits in a tracked, hand-editable cursor. Two
checks keep moving it from buying a pass (review p2-r2): a `started` later than
now is refused, and so is a review unit this cursor briefed BEFORE `started` —
a legitimate historical review is always briefed by the cursor that holds it,
after it began (a superseded hold is closed and re-briefed; an adopted unit is
briefed by the first `advance`). What remains — a cursor edited to a past
`started` and the unit re-briefed after it — is a visible diff to a tracked
file, and the PR-body list still names the review.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from fr.journal.model import JournalEntry, journal_stamp_as_utc
from fr.run import units
from fr.run.model import RunState
from fr.run.telemetry import parse_timestamp

__all__ = [
    "HISTORICAL_HEADING",
    "HISTORICAL_REVIEWER",
    "findings_witness",
    "historical_review_refusal",
    "historical_review_lines",
    "historical_reviews",
    "historical_sentence",
    "implement_returned",
]

HISTORICAL_REVIEWER = "historical"
"""The reserved `reviewer` evidence value — phase review units only."""

HISTORICAL_HEADING = "## Historical reviews"
"""The PR-body section listing every historically-reviewed phase (R9)."""


def findings_witness(states: Mapping[str, str]) -> str:
    """The `findings` evidence value for a set of closed findings: their ids in
    raise order, or `none`. ONE spelling for the resolve gate and adoption."""
    return ",".join(states) or "none"


def implement_returned(state: RunState, phase: int, *, review_key: str | None) -> datetime | None:
    """The latest `returned` of any attempt this cursor holds on a `phase/N/*`
    unit other than `review_key` — the phase's implement work, by the same
    "every other member of the phase" rule the reviewer check uses."""
    latest: datetime | None = None
    prefix = f"phase/{phase}/"
    for record in state.steps.values():
        for key in record.units or {}:
            if not key.startswith(prefix) or key == review_key:
                continue
            for attempt in units.attempts(record, key):
                at = parse_timestamp(attempt.returned) if attempt.returned else None
                if at is not None and (latest is None or at > latest):
                    latest = at
    return latest


def historical_review_refusal(
    state: RunState,
    phase: int,
    entry: JournalEntry,
    *,
    owes_visual: bool,
    review_key: str | None = None,
    review_dispatched: str | None = None,
    now: datetime | None = None,
) -> str | None:
    """Why `entry` is NOT a historical review of `phase` for this cursor — the
    failed clause, worded — or `None` when it is (spec §D, clauses 1-3, plus
    the two anchors on `started` the module docstring explains).

    `review_dispatched` is when this cursor briefed the review unit (the
    by-hand path always has one; adoption briefs nothing yet). `now` defaults
    to the clock — passed in by tests."""
    created = parse_timestamp(journal_stamp_as_utc(entry.created))
    started = parse_timestamp(state.started)
    if created is None or started is None:
        return (
            f"review {entry.id} was created {entry.created!r} and this run started "
            f"{state.started!r} — fr cannot order them, so it cannot call the review historical"
        )
    current = now if now is not None else datetime.now(UTC)
    if started > current:
        return (
            f"this run's `started` ({state.started}) is in the future — fr will not "
            "measure a review against it"
        )
    if review_dispatched is not None:
        opened = parse_timestamp(review_dispatched)
        if opened is None or opened < started.replace(microsecond=0):
            return (
                f"this cursor briefed the review at {review_dispatched}, before the run "
                f"started at {state.started} — a cursor cannot brief a unit before it began"
            )
    # Clause 1: it predates this cursor. Journal stamps carry whole seconds, so
    # the same second as `started` is not "before" it.
    if created >= started.replace(microsecond=0):
        return (
            f"review {entry.id} was created {entry.created}, not before this run started "
            f"at {state.started} — a review made under this cursor names its reviewer"
        )
    # Clause 2: it follows the work it reviews.
    returned = implement_returned(state, phase, review_key=review_key)
    # Same second as the return is not "after" it (journal stamps are whole seconds).
    if returned is not None and created <= returned.replace(microsecond=0):
        return (
            f"review {entry.id} was created {entry.created}, before phase {phase}'s "
            f"implementation last returned at {returned.isoformat()} — it reviews earlier work"
        )
    # Clause 3: a visual phase needs screenshots a reviewer opened where fr can read it.
    if owes_visual:
        return (
            f"phase {phase} owes `visual` evidence, which a historical reviewer cannot "
            "carry — dispatch a reviewer for it"
        )
    return None


def historical_reviews(state: RunState) -> list[tuple[str, str, str]]:
    """`(step id, unit key, journal entry id)` for every unit resolved with
    `reviewer=historical`, in cursor order."""
    out: list[tuple[str, str, str]] = []
    for step_id, record in state.steps.items():
        for key in units.unit_keys(record):
            evidence = units.evidence_of(record, key)
            if evidence.get("reviewer") == HISTORICAL_REVIEWER:
                out.append((step_id, key, evidence.get("review", "?")))
    return out


def historical_review_lines(state: RunState) -> list[str]:
    """The PR-body lines naming every historical review, phase order — the ONE
    spelling `fr.record.pr_body` renders and `deliver` requires on the live PR."""

    def phase_of(key: str) -> int:
        part = key.split("/")[1] if key.startswith("phase/") else ""
        return int(part) if part.isdigit() else 0

    found = sorted(historical_reviews(state), key=lambda h: (phase_of(h[1]), h[1]))
    return [
        f"- phase {phase_of(key)} — journal {entry} (reviewed before this run's cursor "
        "existed; reviewer not observed)"
        for _, key, entry in found
    ]


def historical_sentence(entry_id: str) -> str:
    """How a historical review reads in `fr run status`/`check` (R9)."""
    return f"reviewed before this cursor existed (journal {entry_id}) — reviewer not observed"
