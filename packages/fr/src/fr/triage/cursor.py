"""Where a batch's run stands at its PR's head (spec 2026-10-14-exit-gates R17, R18, §D).

The board's Developer and Reviewer lanes are decided from the run cursor at the batch
PR's head (`docs/superpowers/runs/<run-id>.yaml`), never from session status.
`cursor_position` reads a parsed cursor document, pure and version-tolerant: a raw
mapping, because a cursor at a PR head may be written by an older or newer `fr` than
this one, and the three facts it needs (a `blocked` step, a done `deliver`, a `manual`
unit) are spelled the same in every run version that has them. `read_cursor` reaches
the document through the git seam's `Checkout` alone: this module starts no process.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.model import CursorPosition, PullRequest

RUNS_DIR = "docs/superpowers/runs"
DELIVER = "deliver"


def _step(steps: Mapping[str, Any], step_id: str) -> Mapping[str, Any]:
    record = steps.get(step_id)
    return record if isinstance(record, Mapping) else {}


def cursor_position(doc: object, branch: str) -> CursorPosition | None:
    """The position of the run cursor *doc* when it names *branch*; None when it is not
    a cursor, or another branch's. First match: `deliver` done, the cursor step
    `blocked` on its gate, a `manual` unit of the cursor step that is all that is left
    of it (every other unit done), else `none`."""
    if not isinstance(doc, Mapping) or doc.get("branch") != branch:
        return None
    run, cursor, steps = doc.get("run"), doc.get("cursor"), doc.get("steps")
    if not isinstance(run, str) or not run or not isinstance(cursor, str) or not cursor:
        return None
    steps = steps if isinstance(steps, Mapping) else {}
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


def read_cursor(checkout: Checkout, pr: PullRequest) -> CursorPosition | None:
    """The cursor position at *pr*'s head, read through *checkout*: every
    `docs/superpowers/runs/*.yaml` at the head commit, the first naming the PR's branch.
    None when the clone cannot reach the head, no cursor names the branch, or the read
    fails: unknown, never a guess."""
    try:
        if not checkout.reach_commit(pr.head_oid, pr.head_ref):
            return None
        for name in checkout.list_dir(pr.head_oid, RUNS_DIR):
            if not name.endswith(".yaml"):
                continue
            text = checkout.show(pr.head_oid, f"{RUNS_DIR}/{name}")
            if text is None:
                continue
            try:
                doc = yaml.safe_load(text)
            except yaml.YAMLError:
                continue
            found = cursor_position(doc, pr.head_ref)
            if found is not None:
                return found
    except TriageError:
        return None
    return None
