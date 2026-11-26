"""Where a batch's run stands at its PR's head (spec 2026-10-14-exit-gates R17, R18, §D).

The board's Developer and Reviewer lanes are decided from the run cursor at the batch
PR's head (`docs/superpowers/runs/<run-id>.yaml`), never from session status.
`cursor_position` reads a parsed cursor document, pure and version-tolerant: a raw
mapping, because a cursor at a PR head may be written by an older or newer `fr` than
this one, and the three facts it needs (a `blocked` step, a done `deliver`, a `manual`
unit) are spelled the same in every run version that has them. `read_cursor` reaches
the document through the git seam's `Checkout` alone: this module starts no process.

Fail-closed (spec 2026-11-24-batch-merge-readiness R1): a PR's head may carry more than one
cursor naming its branch, and its run is delivered only when EVERY one records `deliver`
done; the fold (`fold_positions`) lives here alone. `read_cursor` also says whether it read
at all, so "no cursor names the branch" is never mistaken for "the head could not be read",
and a run file it cannot use is "could not be read" too, with its cause, never skipped.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import yaml

from fr.artifacts.paths import KIND_DIRS
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.model import CursorAnswer, CursorPosition, PullRequest

RUNS_DIR = KIND_DIRS["run"]
DELIVER = "deliver"


class UnreadableCursorError(ValueError):
    """A run file that is no usable cursor (R1 fail closed): its text says why."""


def _step(steps: Mapping[str, Any], step_id: str) -> Mapping[str, Any]:
    record = steps.get(step_id)
    return record if isinstance(record, Mapping) else {}


def _usable(doc: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    """*doc*'s run, cursor step and steps, or `UnreadableCursorError`: the shape
    `fr.isolation.preserve.branch_runs` reads (steps a mapping of mappings)."""
    run, cursor, steps = doc.get("run"), doc.get("cursor"), doc.get("steps")
    if not isinstance(run, str) or not run:
        raise UnreadableCursorError("names no run")
    if not isinstance(cursor, str) or not cursor:
        raise UnreadableCursorError("names no cursor step")
    if not isinstance(steps, Mapping):
        raise UnreadableCursorError("steps is not a mapping")
    bad = next((str(k) for k, v in steps.items() if not isinstance(v, Mapping)), None)
    if bad is not None:
        raise UnreadableCursorError(f"step {bad} is not a mapping")
    return run, cursor, steps


def cursor_position(doc: object, branch: str) -> CursorPosition | None:
    """The position of the run cursor *doc* when it names *branch*; None when it names
    another branch. A document that is no run (not a mapping, no `branch`) or that names
    *branch* with no usable run, cursor or steps raises `UnreadableCursorError`: unknown, never
    "no cursor" (R1). First match: `deliver` done, the cursor step `blocked` on its gate, a
    `manual` unit of the cursor step that is all that is left of it (every other unit done),
    else `none`."""
    if not isinstance(doc, Mapping):
        raise UnreadableCursorError("is not a mapping")
    if "branch" not in doc:
        raise UnreadableCursorError("names no branch")
    if doc.get("branch") != branch:
        return None
    run, cursor, steps = _usable(doc)
    if _step(steps, DELIVER).get("state") == "done":
        return CursorPosition(run=run, step=DELIVER, kind="deliver-done")
    record = _step(steps, cursor)
    if record.get("state") == "blocked":
        return CursorPosition(run=run, step=cursor, kind="gate")
    units = record.get("units")
    states = {
        str(key): unit.get("state")
        for key, unit in (units.items() if isinstance(units, Mapping) else ())
        if isinstance(unit, Mapping) and unit.get("state") is not None
    }
    manual = sorted(k for k, v in states.items() if v == "manual")
    if manual and all(v in ("done", "manual") for v in states.values()):
        return CursorPosition(run=run, step=cursor, kind="manual", unit=manual[0])
    return CursorPosition(run=run, step=cursor, kind="none")


def fold_positions(found: Sequence[CursorPosition]) -> CursorPosition | None:
    """One position for every cursor naming a branch (batch-merge-readiness R1): `deliver`
    done only when every one is, otherwise the first that is not; None for none."""
    return next((p for p in found if p.kind != "deliver-done"), found[0] if found else None)


def read_cursor(checkout: Checkout, pr: PullRequest) -> CursorAnswer:
    """The folded cursor position at *pr*'s head, read through *checkout*, and whether it
    was read: every `docs/superpowers/runs/*.yaml` at the head commit naming the PR's
    branch, folded by `fold_positions`. `(None, "read")` when none names the branch. Fail
    closed (R1): the head not reached, a failed git read, and any run file that is not YAML
    or not a usable cursor (`cursor_position`) make the whole read `unread`, with the cause
    in `detail` (l-errors-r2), so a corrupt file beside a delivered cursor never delivers."""
    at = pr.head_oid[:12]
    found: list[CursorPosition] = []
    try:
        why = checkout.reach_failure(pr.head_oid, pr.head_ref)
        if why:
            return CursorAnswer(None, "unread", f"head {at} not reached: {why}")
        for name in sorted(checkout.list_dir(pr.head_oid, RUNS_DIR)):
            if not name.endswith(".yaml"):
                continue
            path = f"{RUNS_DIR}/{name}"
            text = checkout.show(pr.head_oid, path)
            if text is None:
                return CursorAnswer(None, "unread", f"{path} at {at} could not be shown")
            try:
                position = cursor_position(yaml.safe_load(text), pr.head_ref)
            except yaml.YAMLError as exc:
                return CursorAnswer(None, "unread", f"{path} at {at} is not YAML: {exc}")
            except UnreadableCursorError as exc:
                return CursorAnswer(None, "unread", f"{path} at {at} {exc}")
            if position is not None:
                found.append(position)
    except TriageError as exc:
        return CursorAnswer(None, "unread", f"reading {RUNS_DIR} at {at} failed: {exc}")
    return CursorAnswer(fold_positions(found), "read")


def answer_at(pr: PullRequest, open_clone: Callable[[], Checkout] | None) -> CursorAnswer:
    """The driver's read of *pr*'s head cursor (batch-merge-readiness R1): `no-clone` when
    *open_clone* is None, else `read_cursor` through it, a clone that cannot be opened or
    read being `unread` with its cause (l-errors-r2)."""
    if open_clone is None:
        return CursorAnswer(None, "no-clone", f"no clone of {pr.repo}")
    try:
        return read_cursor(open_clone(), pr)
    except TriageError as exc:
        return CursorAnswer(None, "unread", f"the clone of {pr.repo} could not be read: {exc}")
