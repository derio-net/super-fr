"""Markers on an owed tracker issue (spec 2026-11-01-gate-backfill §F).

A backfill tracker's body ends with two marker lines, the PR marker before the owed marker, so
`archive_followups.owned_owed_key` (last-line rule) accepts it unchanged:

    <!-- fr-gate:devops pr:41 -->
    <!-- fr-owed:plan:2026-04-02-fleet#p3 -->
"""

from __future__ import annotations

import re
from pathlib import Path

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


_ADOPT_MARKER = re.compile(
    r"^<!-- fr-gate-adopt:(?P<key>\S+) gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$"
)
_PLACEHOLDER = "<what you did>"


def gate_marker(gate: str, pr: int) -> str:
    return f"<!-- fr-gate:{gate} pr:{pr} -->"


def adopt_marker(key: str, gate: str, pr: int) -> str:
    return f"<!-- fr-gate-adopt:{key} gate:{gate} pr:{pr} -->"


def link_marker(key: str, tracker: str) -> str:
    return f"<!-- fr-gate-link:{key} tracker:{tracker} -->"


def fr_adopt_marker(body: str) -> tuple[str, str, int] | None:
    """`(key, gate, pr)` from the LAST line of an adopt comment, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    m = _ADOPT_MARKER.match(lines[-1]) if lines else None
    return (m.group("key"), m.group("gate"), int(m.group("pr"))) if m else None


def run_for_head(root: Path, head_ref: str) -> str | None:
    """The one run whose cursor names *head_ref* as its branch; `None` when none or several do
    (or a cursor cannot be read): the printed command then falls back to `--no-run-evidence`,
    and `fr gate pass` itself refuses if a run does name the branch."""
    from fr.run.cursors import all_cursors
    from fr.run.model import RunStateError, parse_run_state

    if not head_ref:
        return None
    found = []
    for path in all_cursors(root):
        try:
            state = parse_run_state(path.read_text())
        except (RunStateError, OSError):
            continue
        if state.branch == head_ref:
            found.append(state.run)
    return found[0] if len(found) == 1 else None


def pass_command(gate: str, pr: int, *, run_id: str | None = None) -> str:
    """The `fr gate pass` that clears *gate* on PR *pr*; always carries `--notes`, and for
    devops `--run <id>` when a cursor names the PR's head ref, else `--no-run-evidence`."""
    cmd = f'fr gate pass --pr {pr} --gate {gate} --notes "{_PLACEHOLDER}"'
    if gate == "devops":
        cmd += f" --run {run_id}" if run_id else " --no-run-evidence"
    return cmd


def tracker_body(
    key: str, title: str, gate: str, pr: int, *, run_id: str | None = None
) -> str:
    """The backfill tracker's body; its two marker lines end it (PR marker, then owed marker)."""
    from fr.archive_followups import owed_marker

    return "\n".join(
        [
            f"Owed: {title}",
            "",
            f"Delivered by #{pr} (merged). Held by gate:{gate} on that PR; clear it with the "
            "pass command below once done.",
            "",
            f"`{pass_command(gate, pr, run_id=run_id)}`",
            "",
            gate_marker(gate, pr),
            owed_marker(key),
        ]
    )


def adopt_comment(key: str, gate: str, pr: int, *, run_id: str | None = None) -> str:
    return "\n".join(
        [
            f"fr is tracking `{key}` here: PR #{pr} is held by gate:{gate} until it is done.",
            "",
            f"`{pass_command(gate, pr, run_id=run_id)}`",
            "",
            adopt_marker(key, gate, pr),
        ]
    )


def link_comment(key: str, tracker: str) -> str:
    return "\n".join(
        [f"The ask of this issue is tracked by {tracker} (`{key}`).", "", link_marker(key, tracker)]
    )
