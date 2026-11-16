"""The one reader of a forge or fact timestamp that must be timezone-aware.

`parse_aware` returns an aware `datetime`, or `None` when the stamp is missing,
unparseable or naive. Callers skip a time they cannot compare; none raises.

Readers that treat a naive time as UTC (usage, debt) are a different contract and
do not belong here.
"""

from __future__ import annotations

from datetime import datetime


def parse_aware(stamp: str | None) -> datetime | None:
    """*stamp* as an aware datetime; None when it is missing, unparseable or naive."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
