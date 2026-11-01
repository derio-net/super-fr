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
    other issue is only text (R8)."""
    from fr.labels import FR_OWED

    author = issue.get("author")
    login = author.get("login") if isinstance(author, dict) else author
    labels = {
        str(lab.get("name", "")) if isinstance(lab, dict) else str(lab)
        for lab in (issue.get("labels") or [])  # type: ignore[attr-defined]
    }
    return bool(me) and login == me and FR_OWED.name in labels
