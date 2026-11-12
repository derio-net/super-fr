"""Markers on an owed tracker issue (spec 2026-11-01-gate-backfill §F).

A backfill tracker's body ends with two marker lines, the PR marker before the owed marker, so
`archive_followups.owned_owed_key` (last-line rule) accepts it unchanged:

    <!-- fr-gate:devops pr:41 -->
    <!-- fr-owed:plan:2026-04-02-fleet#p3 -->

A tracker for a PR whose gate already passed (gh#1322) carries `fr-gate-passed:<g> pr:<n>` in
the PR marker's place instead. It is "tracked only": the PR is never re-gated, and
`fr_gate_marker` reads it as `None`, so passing the gate again (§H) never closes it. The item
itself is discharged by its key's own command, and `fr gate backfill` closes the tracker once its
key is (spec 2026-11-08-sweep-fixes R13).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any, Literal

from fr.acceptance.amend import feature_flag

_GATE_MARKER = re.compile(r"^<!-- fr-gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$")
_PASSED_MARKER = re.compile(r"^<!-- fr-gate-passed:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$")


def _second_to_last(body: str, pattern: re.Pattern[str]) -> tuple[str, int] | None:
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    if len(lines) < 2:
        return None
    m = pattern.match(lines[-2])
    return (m.group("gate"), int(m.group("pr"))) if m else None


def fr_gate_marker(body: str) -> tuple[str, int] | None:
    """`(gate, pr)` from the second-to-last line of *body*, exact match only."""
    return _second_to_last(body, _GATE_MARKER)


def fr_passed_marker(body: str) -> tuple[str, int] | None:
    """`(gate, pr)` of a tracked-only tracker (the gate had already passed), else `None`."""
    return _second_to_last(body, _PASSED_MARKER)


def is_ours(issue: dict[str, object], me: str) -> bool:
    """Whether fr wrote this open issue: this account's, labelled `fr:owed`. A marker on any
    other issue is only text (R8). The same author/label rule `owned_owed_key` applies."""
    from fr.archive_followups import is_owned_issue

    return is_owned_issue(issue, me)


_ADOPT_MARKER = re.compile(
    r"^<!-- fr-gate-adopt:(?P<key>\S+) gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$"
)
_ADOPT_PASSED_MARKER = re.compile(
    r"^<!-- fr-gate-adopt-passed:(?P<key>\S+) gate:(?P<gate>[a-z][a-z0-9-]*) pr:(?P<pr>\d+) -->$"
)
_ADOPT_DISCHARGED_MARKER = re.compile(
    r"^<!-- fr-gate-adopt-discharged:(?P<key>\S+) pr:(?P<pr>\d+) -->$"
)
_PLACEHOLDER = "<what you did>"


def gate_marker(gate: str, pr: int) -> str:
    return f"<!-- fr-gate:{gate} pr:{pr} -->"


def adopt_marker(key: str, gate: str, pr: int) -> str:
    return f"<!-- fr-gate-adopt:{key} gate:{gate} pr:{pr} -->"


def passed_marker(gate: str, pr: int) -> str:
    return f"<!-- fr-gate-passed:{gate} pr:{pr} -->"


def adopt_passed_marker(key: str, gate: str, pr: int) -> str:
    return f"<!-- fr-gate-adopt-passed:{key} gate:{gate} pr:{pr} -->"


def adopt_discharged_marker(key: str, pr: int) -> str:
    return f"<!-- fr-gate-adopt-discharged:{key} pr:{pr} -->"


def link_marker(key: str, tracker: str) -> str:
    return f"<!-- fr-gate-link:{key} tracker:{tracker} -->"


def fr_adopt_marker(body: str) -> tuple[str, str, int] | None:
    """`(key, gate, pr)` from the LAST line of an adopt comment, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    m = _ADOPT_MARKER.match(lines[-1]) if lines else None
    return (m.group("key"), m.group("gate"), int(m.group("pr"))) if m else None


def fr_adopt_passed_marker(body: str) -> tuple[str, str, int] | None:
    """`(key, gate, pr)` from the LAST line of a tracked-only adopt comment, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    m = _ADOPT_PASSED_MARKER.match(lines[-1]) if lines else None
    return (m.group("key"), m.group("gate"), int(m.group("pr"))) if m else None


def fr_adopt_discharged_marker(body: str) -> tuple[str, int] | None:
    """`(key, pr)` from the LAST line of an evidence comment, exact match only."""
    lines = [ln.strip() for ln in body.rstrip().splitlines()]
    m = _ADOPT_DISCHARGED_MARKER.match(lines[-1]) if lines else None
    return (m.group("key"), int(m.group("pr"))) if m else None


def adopt_states(
    comments: list[dict[str, Any]], me: str
) -> dict[tuple[str, str, int], Literal["held", "passed"]]:
    """`(key, gate, pr)` -> what THIS account's latest adopt comment on it says: `held`
    (`fr-gate-adopt:`) or `passed` (`fr-gate-adopt-passed:`). Anyone else's comment is only text
    (R8). *comments* are in the forge's order, oldest first, so a later comment wins."""
    states: dict[tuple[str, str, int], Literal["held", "passed"]] = {}
    for c in comments:
        if not me or c.get("author") != me:
            continue
        body = str(c.get("body") or "")
        held, passed = fr_adopt_marker(body), fr_adopt_passed_marker(body)
        if held is not None:
            states[held] = "held"
        elif passed is not None:
            states[passed] = "passed"
    return states


def adopt_discharged(comments: list[dict[str, Any]], me: str) -> set[tuple[str, int]]:
    """`(key, pr)` of this account's evidence comments: a second run writes nothing (R13)."""
    found = (
        fr_adopt_discharged_marker(str(c.get("body") or ""))
        for c in comments
        if me and c.get("author") == me
    )
    return {m for m in found if m is not None}


def runs_by_head(root: Path) -> dict[str, list[str]]:
    """Every readable cursor's run id, by the branch it names: read once, then asked per entry."""
    from fr.run.cursors import all_cursors
    from fr.run.model import RunStateError, parse_run_state

    index: dict[str, list[str]] = {}
    for path in all_cursors(root):
        try:
            state = parse_run_state(path.read_text())
        except (RunStateError, OSError):
            continue
        if state.branch:
            index.setdefault(state.branch, []).append(state.run)
    return index


def run_for_head(
    root: Path, head_ref: str, *, index: dict[str, list[str]] | None = None
) -> str | None:
    """The one run whose cursor names *head_ref* as its branch; `None` when none or several do
    (or a cursor cannot be read): the printed command then falls back to `--no-run-evidence`,
    and `fr gate pass` itself refuses if a run does name the branch. *index* is `runs_by_head`'s,
    for a caller asking about many heads."""
    if not head_ref:
        return None
    found = (index if index is not None else runs_by_head(root)).get(head_ref, [])
    return found[0] if len(found) == 1 else None


def pass_command(
    gate: str, pr: int, *, run_id: str | None = None, resolve_run: bool = False
) -> str:
    """The `fr gate pass` that clears *gate* on PR *pr*; always carries `--notes`, and for
    devops `--run <id>` when a cursor names the PR's head ref, else `--no-run-evidence`.
    *resolve_run* omits both: a batch PR's run cursor exists, `--no-run-evidence` would be
    refused, and `fr gate pass` finds the run from the checkout by head ref itself."""
    cmd = f'fr gate pass --pr {pr} --gate {gate} --notes "{_PLACEHOLDER}"'
    if gate == "devops" and not resolve_run:
        cmd += f" --run {run_id}" if run_id else " --no-run-evidence"
    return cmd


def _journal_resolve(root: Path, key: str) -> str | None:
    """The `fr journal resolve` that discharges the open `owed` journal entry holding *key*."""
    from fr.journal.model import (
        IMPLEMENTED_JOURNALS_REL,
        JOURNALS_REL,
        SCOPE_DIRS,
        JournalParseError,
        open_owed_ids,
        owed_key,
        parse_journal,
    )

    for base in (JOURNALS_REL, IMPLEMENTED_JOURNALS_REL):
        for scope, sub in SCOPE_DIRS.items():
            d = root / base / sub
            if not d.is_dir():
                continue
            for path in sorted(d.glob("*.md")):
                try:
                    entries = parse_journal(path.read_text())
                except (JournalParseError, OSError, UnicodeDecodeError):
                    continue
                still = set(open_owed_ids(entries))
                for e in entries:
                    if e.kind == "owed" and e.id in still and owed_key(e) == key:
                        return (
                            f"fr journal resolve --scope {scope} --slug {shlex.quote(path.stem)} "
                            f'--id {shlex.quote(e.id)} --state fixed --note "<why it is done>"'
                        )
    return None


def discharge_command(key: str, *, repo_root: Path) -> str:
    """The command(s) that discharge the owed *key* itself (spec §H step 4), one per line. Pure
    over the checkout; never raises: a key it has no command for says how to close it by hand."""
    from fr.gatebackfill.candidates import PLANS_REL, find_spec, split_key
    from fr.gatebackfill.render import _unticked

    journal = _journal_resolve(repo_root, key)
    if journal is not None:
        return journal
    kind, name, n = split_key(key)
    if kind == "row":
        return (
            f"fr acceptance set-status --id {shlex.quote(name)} --status walked "
            '--walk "<walk log>" --harness "<harness>" --model "<model>" '
            '--strategy "<strategy>" --notes "<what passed>" ' + feature_flag(repo_root, name)
        )
    if kind == "spec" and n is not None:
        spec = find_spec(repo_root, name) or "<spec>"
        return (
            f"fr closeout outcome --spec {shlex.quote(spec)} --step {n} --ran "
            '--evidence "<what>" --supersede'
        )
    if kind == "plan" and n is not None:
        steps, why = _unticked(repo_root, name, n)
        if steps:
            plan_dir = shlex.quote((PLANS_REL / name).as_posix())
            return "\n".join(f"fr plan edit {plan_dir} --tick {sid}" for sid in steps)
        return f"{key}: nothing to tick ({why or 'every step is ticked'}); close it by hand"
    ref = key.partition(":")[2]
    return f"close {ref or key} by hand"


def tracker_body(key: str, title: str, gate: str, pr: int, *, run_id: str | None = None) -> str:
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


# No gate pass reaches a tracked-only tracker, so its text says what closes it (gh#1328, R13). The
# wording names no `fr` command: the backfill's two steps are in the operator doc.
_OWNED_CLOSE_LINE = (
    "Once it is discharged, the next gate backfill (dry run, then --yes) closes this issue."
)
_ADOPTED_CLOSE_LINE = (
    "Once it is discharged, the next gate backfill (dry run, then --yes) says so here and prints "
    "the close command; fr never closes this issue, so closing it is yours."
)


def _discharge_block(key: str, repo_root: Path) -> list[str]:
    return ["```", discharge_command(key, repo_root=repo_root), "```"]


def passed_tracker_body(key: str, title: str, gate: str, pr: int, *, repo_root: Path) -> str:
    """A tracked-only tracker's body (gh#1322): PR *pr* already carries `gate:<gate>-passed`, so
    it is never re-gated; the item is still owed and is discharged by its own command."""
    from fr.archive_followups import owed_marker

    return "\n".join(
        [
            f"Owed: {title}",
            "",
            f"Delivered by #{pr} (merged). Its gate:{gate} already passed, so the PR is not "
            "held again; this item is still owed and is tracked here only. Discharge it once "
            "done:",
            "",
            *_discharge_block(key, repo_root),
            "",
            _OWNED_CLOSE_LINE,
            "",
            passed_marker(gate, pr),
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


def adopt_passed_comment(
    key: str, gate: str, pr: int, *, repo_root: Path, discharged: str | None = None
) -> str:
    """The tracked-only adopt comment (gh#1322): no pass command, the key's discharge instead.
    *discharged*: the evidence, when a `--keep` names a key that already reads as discharged."""
    reads_as = [f"It already reads as discharged: {discharged}.", ""] if discharged else []
    return "\n".join(
        [
            f"fr is tracking `{key}` here. PR #{pr}'s gate:{gate} already passed, so the PR is "
            "not held again; the item itself is still owed. Discharge it once done:",
            "",
            *_discharge_block(key, repo_root),
            "",
            *reads_as,
            _ADOPTED_CLOSE_LINE,
            "",
            adopt_passed_marker(key, gate, pr),
        ]
    )


def adopt_discharged_comment(key: str, pr: int, evidence: str) -> str:
    """The one comment an adopted issue gets once its key is discharged (R13)."""
    return "\n".join(
        [
            f"`{key}` is discharged: {evidence}. fr never closes this issue, so closing it is "
            "yours.",
            "",
            adopt_discharged_marker(key, pr),
        ]
    )
