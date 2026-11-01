"""Markers on an owed tracker issue (spec 2026-11-01-gate-backfill §F).

A backfill tracker's body ends with two marker lines, the PR marker before the owed marker, so
`archive_followups.owned_owed_key` (last-line rule) accepts it unchanged:

    <!-- fr-gate:devops pr:41 -->
    <!-- fr-owed:plan:2026-04-02-fleet#p3 -->
"""

from __future__ import annotations

import re

_GATE_MARKER = re.compile(r"^<!-- fr-gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$")
_OWED_MARKER = re.compile(r"^<!-- fr-owed:(?P<key>\S+) -->$")


def fr_gate_marker(body: str) -> tuple[str, int] | None:
    """`(gate, pr)` from the second-to-last line of *body*, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    if len(lines) < 2:
        return None
    m = _GATE_MARKER.match(lines[-2])
    return (m.group("gate"), int(m.group("pr"))) if m else None


def owed_marker_key(body: str) -> str | None:
    """The owed key on the LAST line of *body*, when that line is exactly an owed marker."""
    lines = body.rstrip().splitlines()
    if not lines:
        return None
    m = _OWED_MARKER.match(lines[-1].strip())
    return m.group("key") if m else None
