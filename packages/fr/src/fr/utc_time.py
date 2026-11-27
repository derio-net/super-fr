"""The one reader of a stamp where a naive time is read as UTC.

`parse_as_utc` returns an aware `datetime`, or `None` when the value is missing,
empty, not a string or unparseable. Usage, debt, run liveness and triage claims
read stamps this way, each keeping its own handling of `None`.

`fr.triage.timestamps.parse_aware` is the other contract (a naive time is unknown).
Imports only the standard library.
"""

from __future__ import annotations

from datetime import UTC, datetime


def parse_as_utc(value: object) -> datetime | None:
    """*value* as an aware datetime (naive read as UTC); None when it cannot be read."""
    if not isinstance(value, str) or not value:
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)
