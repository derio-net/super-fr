"""A gate pass closes the backfill trackers it discharges (spec 2026-11-01-gate-backfill §H, R12).

One helper, called by both pass routes (`fr gate pass` and the triage driver) after
`pass_gate`. It lives here, not in `fr.verification.labels`, which re-exports it, so the
`fr.gatebackfill` -> `fr.verification` direction never turns into a cycle. Forge writes go
through the `GhClient` only; a failure is reported in the result, never raised, and never
reverses the pass that already happened.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fr.archive_followups import OWED_ISSUE_FIELDS, owned_owed_key
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.labels import FR_OWED

OPEN_LIMIT = 500
_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


@dataclass
class CloseReport:
    """What a pass did (or, on a dry run, would do) to the PR's backfill trackers."""

    closed: list[int] = field(default_factory=list)  # fr-owned trackers (closed, or would be)
    adopt_commands: list[str] = field(default_factory=list)  # `gh issue close` for adopted ones
    discharge: list[str] = field(default_factory=list)  # one command per key, §H step 4
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def found(self) -> bool:
        return bool(self.closed or self.adopt_commands)

    def summary(self) -> str:
        """One clause for a one-line caller (the driver)."""
        if not self.found and not self.errors:
            return ""
        verb = "would close" if self.dry_run else "closed"
        parts = (
            [f"{verb} trackers {', '.join(f'#{n}' for n in self.closed)}"] if self.closed else []
        )
        if self.adopt_commands:
            parts.append(f"{len(self.adopt_commands)} adopted issue(s) to close by hand")
        if self.errors:
            parts.append(f"{len(self.errors)} tracker error(s): {'; '.join(self.errors)}")
        return "; ".join(parts)

    def lines(self) -> list[str]:
        out: list[str] = []
        verb = "would close" if self.dry_run else "closed"
        out += [f"{verb} tracker #{n}" for n in self.closed]
        if self.adopt_commands:
            out.append("adopted issues are never closed by fr; close each yourself:")
            out += [f"  {c}" for c in self.adopt_commands]
        if self.discharge:
            out.append("the owed work itself is discharged separately:")
            out += [f"  {line}" for c in self.discharge for line in c.splitlines()]
        out += [f"tracker error: {e}" for e in self.errors]
        return out


def close_gate_trackers(
    client: GhClient,
    repo: str,
    pr: int,
    gate: str,
    notes: str,
    *,
    root: Path | None = None,
    dry_run: bool = False,
) -> CloseReport:
    """Close the open `fr:owed` issues fr owns whose gate marker names PR *pr* and *gate*."""
    from fr.gatebackfill import trackers

    report = CloseReport(dry_run=dry_run)
    try:
        me = client.viewer_login()
        issues = client.list_issues(
            repo, "open", OPEN_LIMIT, OWED_ISSUE_FIELDS, labels=[FR_OWED.name]
        )
    except _FAILURES as exc:
        report.errors.append(f"cannot list the open {FR_OWED.name} issues of {repo}: {exc}")
        return report
    comment = f"Gate {gate} passed on #{pr}: {notes}"
    for issue in issues:
        try:
            _one(client, repo, pr, gate, comment, me, issue, report, root, trackers, dry_run)
        except _FAILURES as exc:
            report.errors.append(f"issue #{issue.get('number')}: {exc}")
    return report


def _discharge(report: CloseReport, key: str, root: Path | None, trackers: Any) -> None:
    if root is None:
        return
    line = trackers.discharge_command(key, repo_root=root)
    if line not in report.discharge:
        report.discharge.append(line)


def _one(
    client: GhClient,
    repo: str,
    pr: int,
    gate: str,
    comment: str,
    me: str,
    issue: dict[str, Any],
    report: CloseReport,
    root: Path | None,
    trackers: Any,
    dry_run: bool,
) -> None:
    number = issue.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        return
    body = str(issue.get("body") or "")
    key = owned_owed_key(issue, me)
    if key is not None:
        if trackers.fr_gate_marker(body) != (gate, pr):
            return
        if not dry_run:
            client.close_issue(repo, number, comment)
        report.closed.append(number)
        _discharge(report, key, root, trackers)
        return
    if trackers.is_ours(issue, me):
        return  # fr's own, but not a backfill tracker (no owed marker): not ours to touch
    for c in client.list_issue_comments(repo, number):  # a foreign issue: one read, adopt only
        if c.get("author") != me:
            continue
        got = trackers.fr_adopt_marker(str(c.get("body") or ""))
        if got is not None and got[1:] == (gate, pr):
            report.adopt_commands.append(
                f"gh issue close {number} --repo {shlex.quote(repo)} --comment {shlex.quote(comment)}"
            )
            _discharge(report, got[0], root, trackers)
            return
