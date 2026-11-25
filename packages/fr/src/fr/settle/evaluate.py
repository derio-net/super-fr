"""The pure settle engine (spec 2026-11-23-pr-readiness-wait R2, R4, R11).

`evaluate` reads one PR view and its checks and returns a `Verdict`. It reaches no forge,
no git and no clock of its own: the caller passes the head's commit time and `now`.

States (R2). Conflicts: `clean`, `conflicting` (`fr.triage.mergeability.conflicting`:
`CONFLICTING` or `DIRTY`; `BLOCKED` is branch protection, so clean), `unknown` (the forge
has not computed mergeability or the merge state yet). CI: `green`, `red` (with the
failing check names), `pending` (a check has not finished, or none has reported, or a
declared gate has not, and the head is younger than `NO_CI_WAIT_SECONDS`), `missing` (none
reported after that, or a gate still absent then, each with its own hint), `unrunnable`
(a conflicting PR: the forge runs no pull-request workflow for it), `none` (the repo's
services say `ci none`). A concern under `off` is not evaluated and reads `off`.

The exit code (R4), stated once. Only a concern whose mode is `fix` decides it:

    any fix concern conflicting | red | missing | unrunnable   -> 4
    else any fix concern unknown | pending                     -> 75
    otherwise                                                  -> 0

A `report` concern's state is printed and never changes the code; an `off` concern is
not read. `unsupported` (R11) and `managed` (R5) verdicts exit 0 (`unsupported_verdict`,
`managed_verdict`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from fr.checkstate import bucket_verdict
from fr.run.ci_evidence import NO_CI_WAIT_SECONDS
from fr.settle.model import (
    EXIT_FAILING,
    EXIT_OK,
    EXIT_PENDING,
    FAILING,
    UNSETTLED,
    CiState,
    ConflictState,
    KeyMode,
    Modes,
    Verdict,
)
from fr.triage.mergeability import conflicting

_UNKNOWN: Final = frozenset({"", "UNKNOWN"})

_HINTS: Final[dict[tuple[str, str], str]] = {
    ("conflicts", "clean"): "merges cleanly into {base}",
    ("conflicts", "conflicting"): (
        "conflicts with {base}: merge origin/{base} into the branch (never rebase or "
        "force-push), push with `fr push`, then run `fr pr settle` again"
    ),
    ("conflicts", "unknown"): "the forge has not computed mergeability yet",
    ("ci", "green"): "every check read passed",
    ("ci", "red"): (
        "failing: {failing}; fix it with an ordinary commit, push with `fr push`, then run "
        "`fr pr settle` again"
    ),
    ("ci", "pending"): "checks are still running",
    ("ci", "cancelled"): (
        "cancelled with no newer run: {cancelled}; re-run the workflow (the PR's checks "
        "page), then run `fr pr settle` again"
    ),
    ("ci", "gate-pending"): "waiting on gate check {absent}, which has not reported yet",
    ("ci", "gate-awaiting"): "waiting on gate check {absent}, which has not reported yet",
    ("ci", "awaiting"): "no check has reported on the head yet",
    ("ci", "gate-absent"): (
        "gate check {absent} never reported on the head {minutes} minutes after it was "
        "committed, while the other checks finished; see why its workflow did not run, fix "
        "it and push"
    ),
    ("ci", "missing"): (
        "no check reported on the head {minutes} minutes after it was committed; see why "
        "no workflow ran (the PR's checks page), fix it and push"
    ),
    ("ci", "unrunnable"): (
        "CI cannot run on a conflicting PR: fix the conflict first, and CI runs on the push"
    ),
    ("ci", "unrunnable-relaxed"): (
        "CI cannot run on a conflicting PR, so relaxing `settle.conflicts` alone leaves CI "
        "`unrunnable`: relax `settle.ci` too, with its reason, or resolve the conflict"
    ),
    ("ci", "none"): "the repo's services say `ci none`: no CI to wait for",
    ("ci", "head-unknown"): (
        "no check has reported, and the head's commit time could not be read, so fr "
        "cannot tell whether CI is still coming; see the PR's checks page"
    ),
}
"""The wording of every printed state line, in one place."""

_AGED: Final = frozenset({"awaiting", "missing", "gate-awaiting", "gate-absent"})
"""The hints the head's age may have decided."""
_ESTIMATED: Final = (
    " (the head's age is estimated from local HEAD: the PR head is not in this clone)"
)

MANAGED_LINE: Final = (
    "managed: the wave driver's queue and hand-backs own this PR's mergeability and CI; "
    "nothing to settle here"
)
NO_FORGE_LINE: Final = (
    "unsupported: the origin remote names no forge (a local path or a file:// URL); the "
    "PR's mergeability and CI are not known here"
)
UNSUPPORTED_LINE: Final = (
    "unsupported: the {backend} forge cannot report {op}; the PR's mergeability and CI "
    "are not known, so check them on the forge"
)


def _conflict_state(view: Mapping[str, Any]) -> ConflictState:
    mergeable = str(view.get("mergeable") or "")
    merge_state = str(view.get("merge_state") or "")
    if conflicting(mergeable, merge_state):
        return "conflicting"
    if mergeable in _UNKNOWN or merge_state in _UNKNOWN:
        return "unknown"
    return "clean"


def _ci_state(
    is_conflicting: bool,
    checks: Sequence[Mapping[str, Any]],
    gate_names: Sequence[str] | None,
    *,
    ci_none: bool,
    age: float | None,
) -> tuple[CiState, tuple[str, ...], str, tuple[str, ...]]:
    """(state, failing check names, hint key, the names the hint carries: the absent
    gates, or the cancelled checks). An unknown *age* never reads as `missing`: CI may
    still be coming."""
    if ci_none:
        return "none", (), "none", ()
    if is_conflicting:
        return "unrunnable", (), "unrunnable", ()
    relevant = [c for c in checks if not gate_names or c.get("name") in gate_names]
    failing = tuple(
        sorted({str(c.get("name")) for c in relevant if bucket_verdict(c.get("bucket")) == "fail"})
    )
    if failing:
        return "red", failing, "red", ()
    pending = [c for c in relevant if bucket_verdict(c.get("bucket")) == "pending"]
    if pending:
        if all(c.get("bucket") == "cancel" for c in pending):
            # No newer run replaced them, and none is running: name them and the remedy.
            cancelled = tuple(sorted({str(c.get("name")) for c in pending}))
            return "pending", (), "cancelled", cancelled
        return "pending", (), "pending", ()
    fresh = age is None or age < NO_CI_WAIT_SECONDS
    if not checks:
        if age is None:
            return "pending", (), "head-unknown", ()
        return ("pending", (), "awaiting", ()) if fresh else ("missing", (), "missing", ())
    reported = {str(c.get("name")) for c in relevant}
    absent = tuple(g for g in gate_names or () if g not in reported)
    if absent:
        # A gate not reported yet: a job waiting on others, or a workflow that has not
        # started; CI finished without it only once the head is past the no-CI wait.
        running = any(bucket_verdict(c.get("bucket")) == "pending" for c in checks)
        if running:
            return "pending", (), "gate-pending", absent
        if fresh:
            return "pending", (), "gate-awaiting", absent
        return "missing", (), "gate-absent", absent
    return "green", (), "green", ()


def _code(concern: KeyMode, state: str) -> int:
    if concern.mode != "fix":
        return EXIT_OK
    if state in FAILING:
        return EXIT_FAILING
    if state in UNSETTLED:
        return EXIT_PENDING
    return EXIT_OK


def _line(key: str, km: KeyMode, state: str, hint_key: str = "", **fmt: Any) -> str:
    where = km.source if not km.reason else f"{km.source}: {km.reason}"
    head = f"{key} ({km.mode}, {where}): {state}"
    if km.mode == "off":
        return f"{head} — not read"
    hint = _HINTS.get((key, hint_key or state))
    return f"{head} — {hint.format(**fmt)}" if hint else head


def _witness(modes: Modes, c_state: str, ci_state: str, head: str) -> str:
    return f"{modes.conflicts.mode}/{modes.ci.mode}:{c_state}/{ci_state}@{head}"


def evaluate(
    view: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
    gate_names: Sequence[str] | None,
    modes: Modes,
    *,
    ci_none: bool,
    head_committed_at: float | None,
    now: float,
    head_time_estimated: bool = False,
) -> Verdict:
    """The verdict for one read of the PR (*view* is `GhClient.pr_view`, *checks*
    `GhClient.pr_checks`; *gate_names* None reads every check). *head_committed_at* is
    None when it could not be read; *head_time_estimated* when it is local HEAD's."""
    head = str(view.get("head_oid") or "")
    base = str(view.get("base_ref") or "the base")
    raw_conflict = _conflict_state(view)
    c_state: ConflictState = "off" if modes.conflicts.mode == "off" else raw_conflict
    age = None if head_committed_at is None else now - head_committed_at
    if modes.ci.mode == "off":
        ci_state: CiState = "off"
        failing: tuple[str, ...] = ()
        hint_key, named = "", tuple[str, ...]()
    else:
        ci_state, failing, hint_key, named = _ci_state(
            raw_conflict == "conflicting", checks, gate_names, ci_none=ci_none, age=age
        )
    if hint_key == "unrunnable" and modes.conflicts.mode != "fix":
        hint_key = "unrunnable-relaxed"  # l-tests-r6: the two keys are coupled
    codes = [_code(modes.conflicts, c_state), _code(modes.ci, ci_state)]
    code = (
        EXIT_FAILING
        if EXIT_FAILING in codes
        else EXIT_PENDING
        if EXIT_PENDING in codes
        else EXIT_OK
    )
    lines = (
        _line("conflicts", modes.conflicts, c_state, base=base),
        _line(
            "ci",
            modes.ci,
            ci_state,
            hint_key,
            failing=", ".join(failing),
            absent=", ".join(named),
            cancelled=", ".join(named),
            minutes=int((age or 0) // 60),
        ),
    )
    if head_time_estimated and hint_key in _AGED:
        lines = (lines[0], lines[1] + _ESTIMATED)
    settled = c_state not in UNSETTLED and ci_state not in UNSETTLED
    return Verdict(
        conflict_state=c_state,
        ci_state=ci_state,
        failing_checks=failing,
        exit_code=code,
        lines=lines,
        head=head,
        witness=_witness(modes, c_state, ci_state, head),
        settled=settled,
    )


def managed_verdict(branch: str) -> Verdict:
    """R5: a driver-managed PR, read nothing, exit 0 whatever the modes."""
    return Verdict(
        conflict_state="managed",
        ci_state="managed",
        exit_code=EXIT_OK,
        lines=(f"{branch}: {MANAGED_LINE}",),
        witness="managed",
        settled=True,
    )


def merged_verdict(url: str, head: str = "") -> Verdict:
    """l-errors-r5: the run's recorded PR merged and none is open: nothing to settle."""
    return Verdict(
        conflict_state="merged",
        ci_state="merged",
        exit_code=EXIT_OK,
        lines=(f"merged: {url} has merged and no other PR is open; nothing to settle",),
        head=head,
        witness="merged",
        settled=True,
    )


def unsupported_verdict(modes: Modes, *, backend: str, op: str, head: str = "") -> Verdict:
    """R11: the forge cannot answer a read; never clean or green, never a refusal."""
    return Verdict(
        conflict_state="unsupported",
        ci_state="unsupported",
        exit_code=EXIT_OK,
        lines=(UNSUPPORTED_LINE.format(backend=backend, op=op),),
        head=head,
        witness=_witness(modes, "unsupported", "unsupported", head),
        settled=True,
    )
