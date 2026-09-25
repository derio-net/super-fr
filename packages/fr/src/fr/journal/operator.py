"""Verifying an `answered_by: operator` claim before it is written (p3-r1).

Lives in `fr.journal`, not in a command, because every path that writes a
resolution goes through the step-record engine (`fr.record.apply`) — the
verbs `fr journal add --resolves` / `fr journal resolve` and a whole step's
`fr run resolve --record` alike. A check that lived in one verb was a check
the record path skipped.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

from fr.journal.model import JournalEntry, journal_stamp_as_utc

__all__ = ["OperatorClaimRefusedError", "verify_operator_claim"]


class OperatorClaimRefusedError(Exception):
    """fr observed the transcript and the operator claim does not hold."""


def verify_operator_claim(
    entries: Iterable[JournalEntry],
    finding_id: str,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Check an `answered_by: operator` claim on a resolution of `finding_id`.

    The window opens at the finding's LAST out-of-scope record (else the
    finding itself): an operator answer from before the orchestrator moved it
    out answered something else. Same observation the brainstorm gate makes
    (`fr.run.telemetry.operator_answered_since`) with the same three outcomes:
    observed and answered → `None` (record); observed and not → raise
    `OperatorClaimRefusedError` (nothing written); not observable → the
    advisory line to print, and the claim is recorded as stated. OpenCode and
    Hermes have no question tool fr can read, so there it is always advisory.
    """
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError
    from fr.run.telemetry import operator_answered_since

    env = os.environ if env is None else env
    since = next(
        (
            e.created
            for e in reversed(list(entries))
            if e.id == finding_id or (e.resolves == finding_id and e.out_of_scope)
        ),
        None,
    )
    observed = operator_answered_since(env, journal_stamp_as_utc(since)) if since else None
    if observed is True:
        return None
    if observed is False:
        raise OperatorClaimRefusedError(
            f"{finding_id}: no answered question in this session's transcript since "
            f"{since} — `answered_by: operator` is a claim fr can check here, and it does "
            "not hold. Ask the operator with your harness's question tool, then resolve "
            "again."
        )
    try:
        harness = detect_harness(env)
    except HarnessError as e:
        raise OperatorClaimRefusedError(str(e)) from e
    if harness == "claude-code":
        return (
            f"{finding_id}: could not verify `answered_by: operator` — the session "
            "transcript is not readable here; recorded unverified."
        )
    from fr.harness import load_matrix

    # The reason is the parity row's own `scope_note`, never a second
    # hand-typed copy of it (the same rule the brainstorm gate follows).
    row = next(s for s in load_matrix().surfaces if s.id == "out-of-scope-operator-guard")
    cell = row.harnesses.get(harness) if harness is not None else None
    why = (cell.scope_note if cell else None) or "fr cannot read an operator answer here"
    return (
        f"{finding_id}: `answered_by: operator` recorded as stated — advisory on "
        f"{harness or 'an unrecognised harness'}: {why}"
    )
