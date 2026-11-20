"""Whether a PR conflicts with its base (spec 2026-10-14-exit-gates R19).

One predicate for the board card, `needs_you` and the triage page's PR rows (gh#1197).
`BLOCKED` is deliberately not a conflict: it is branch protection, the normal state of an
unapproved PR.
"""

from __future__ import annotations

CONFLICT_HINT = "conflicting — the driver updates it or hands it back"
CONFLICT_HANDED_BACK_HINT = "conflicting — handed back"
"""A batch PR whose conflict at its current head went to its session (batch-train-truth R18)."""


def conflicting(mergeable: str | None, merge_state: str | None) -> bool:
    """True for `CONFLICTING` (mergeable) or `DIRTY` (merge state) only."""
    return mergeable == "CONFLICTING" or merge_state == "DIRTY"
