"""The one set-apart predicate (2026-11-22-triage-hardening R6, spec §C).

An issue in a set of its own is never ranked, proposed as work, or offered as a duplicate
candidate: awaiting live, a debt digest, owed, or an open issue intake finds untrusted.
`fr.triage.check` re-exports these names; this module is where they live so `dedupe` can
filter with them without importing `check`.
"""

from __future__ import annotations

from fr.labels import FR_AWAITING_LIVE, FR_OWED
from fr.triage.debt import is_trusted_digest
from fr.triage.intake import issue_reason
from fr.triage.model import Facts, Issue

__all__ = ["is_awaiting_live", "is_debt_digest", "is_owed", "is_set_apart"]


def is_awaiting_live(issue: Issue) -> bool:
    """Whether `issue` is open and carries `fr:awaiting-live`."""
    return issue.state == "open" and FR_AWAITING_LIVE.name in issue.labels


def is_debt_digest(issue: Issue, facts: Facts) -> bool:
    """Whether `issue` is an open debt digest: the marker, current or legacy, as a line
    of its own, written by a trusted author (debt-engine R14; `fr.triage.debt`)."""
    return is_trusted_digest(issue, facts)


def is_owed(issue: Issue) -> bool:
    """Whether `issue` is open and carries `fr:owed` (debt-engine R16)."""
    return issue.state == "open" and FR_OWED.name in issue.labels


def is_set_apart(issue: Issue, facts: Facts) -> bool:
    """Whether `issue` is in a set of its own that is never ranked or proposed as work:
    awaiting live, a debt digest, owed, or an open issue intake finds untrusted."""
    return (
        is_awaiting_live(issue)
        or is_debt_digest(issue, facts)
        or is_owed(issue)
        or (issue.state == "open" and issue_reason(issue, facts) is not None)
    )
