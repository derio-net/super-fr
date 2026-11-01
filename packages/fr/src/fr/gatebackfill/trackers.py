"""Markers on an owed tracker issue (spec 2026-11-01-gate-backfill §F).

A backfill tracker's body ends with two marker lines, the PR marker before the owed marker, so
`archive_followups.owned_owed_key` (last-line rule) accepts it unchanged:

    <!-- fr-gate:devops pr:41 -->
    <!-- fr-owed:plan:2026-04-02-fleet#p3 -->
"""

from __future__ import annotations

import re

_GATE_MARKER = re.compile(r"^<!-- fr-gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$")


def fr_gate_marker(body: str) -> tuple[str, int] | None:
    """`(gate, pr)` from the second-to-last line of *body*, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    if len(lines) < 2:
        return None
    m = _GATE_MARKER.match(lines[-2])
    return (m.group("gate"), int(m.group("pr"))) if m else None


def is_ours(issue: dict[str, object], me: str) -> bool:
    """Whether fr wrote this open issue: this account's, labelled `fr:owed`. A marker on any
    other issue is only text (R8). The same author/label rule `owned_owed_key` applies."""
    from fr.archive_followups import is_owned_issue

    return is_owned_issue(issue, me)
