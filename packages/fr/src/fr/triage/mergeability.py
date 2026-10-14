"""Whether a PR conflicts with its base (spec 2026-10-14-exit-gates R19).

One predicate for the board card and `needs_you`. `BLOCKED` is deliberately not a
conflict: it is branch protection, the normal state of an unapproved PR. The triage
page's own test (`render.py`) counts it and is left alone (spec Non-goals).
"""

from __future__ import annotations

CONFLICT_HINT = "conflicting — the driver updates it or hands it back"


def conflicting(mergeable: str | None, merge_state: str | None) -> bool:
    """True for `CONFLICTING` (mergeable) or `DIRTY` (merge state) only."""
    return mergeable == "CONFLICTING" or merge_state == "DIRTY"
