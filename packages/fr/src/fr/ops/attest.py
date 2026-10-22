"""`fr ops attest` (spec 2026-10-22-fr-ops R8): close an UNVERIFIABLE op by a
person's word. Never for an op that has a `check:` (including `proof`)."""

from __future__ import annotations

from dataclasses import replace

from fr.ops.apply import Prompt, Record
from fr.ops.engine import Journal, Runner, StatusRow, runner_secrets, status
from fr.ops.identity import IdentityResolver
from fr.ops.load import LoadedOp
from fr.ops.mask import sanitise_reason


class AttestRefused(Exception):  # noqa: N818
    """The attestation cannot be made (exit 2)."""


def attest_op(
    lo: LoadedOp,
    *,
    note: str,
    runner: Runner,
    identities: IdentityResolver,
    journal: Journal,
    prompt: Prompt,
    record: Record,
) -> StatusRow:
    op = lo.op
    if "\n" in note or "\r" in note:
        raise AttestRefused("--note must be a single line")
    if op.check is not None:
        raise AttestRefused(f"op {op.id!r} has a check; it is verified, not attested")
    if not prompt.has_terminal():
        raise AttestRefused("attesting needs a terminal; nothing written")
    if not note.strip():
        raise AttestRefused("--note must say what you did or saw")
    clean = sanitise_reason(note, runner_secrets(runner))
    if not clean:
        raise AttestRefused("--note must be one short line (200 characters, not a response body)")
    row = status([lo], runner=runner, identities=identities, journal=journal)[0]
    if row.state != "UNVERIFIABLE":
        raise AttestRefused(f"op {op.id!r} is {row.label}; only an UNVERIFIABLE op is attested")
    if not prompt.confirm(f"attest {op.id} — {op.summary}\n  as done by you, noting: {note}"):
        raise AttestRefused("not confirmed; nothing written")
    record(op=op.id, result="attested", phase=op.phase, reason=clean, attested_by="operator")
    return replace(row, state="DONE", how="attested", reason=None)
