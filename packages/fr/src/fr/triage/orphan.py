"""Retiring a `left-scope` batch (spec 2026-11-27-closeout-state R7, R8).

A batch whose repo left the scope's facts can reach nothing on the forge, so the one
thing left to do with it is to append a cancel event. The verbs hand the pieces here:
`orphan_refusal` for `batch cancel`, `focus_refusal` for `batch focus`, and `retire` for
the `--orphaned` flow itself. Kept out of `commands/triage_batch_cmd.py`, which is at its
module line budget.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fr.triage.batch import derive_batch_stage
from fr.triage.model import Batch, CancelEvent, Facts

ORPHANED_HELP = (
    "Retire a batch whose repo left this scope: only the cancel event, nothing on the forge."
)


def _left(batch: Batch) -> str:
    return f"repo {batch.repo_name} left this scope"


def retire_command(batch: Batch) -> str:
    return f"fr triage batch cancel {batch.id} --orphaned"


def focus_refusal(batch: Batch, facts: Facts) -> str | None:
    """R7: `batch focus` on a `left-scope` batch refuses, naming the way to retire it."""
    if derive_batch_stage(batch, facts) != "left-scope":
        return None
    return (
        f"batch {batch.id!r}: its {_left(batch)} (no session of this scope reaches it); "
        f"retire it with `{retire_command(batch)}`"
    )


def orphan_refusal(batch: Batch, facts: Facts, *, orphaned: bool) -> str | None:
    """R8: `cancel` on a `left-scope` batch needs `--orphaned`, and `--orphaned` on any
    other batch is refused. None when the flag and the batch agree."""
    left = derive_batch_stage(batch, facts) == "left-scope"
    if left and not orphaned:
        return (
            f"batch {batch.id!r}: its {_left(batch)}, so nothing on the forge can be "
            f"withdrawn; retire it with `{retire_command(batch)}`"
        )
    if orphaned and not left:
        return (
            f"batch {batch.id!r} is not left-scope; --orphaned retires only a batch whose repo left"
        )
    return None


def retire(
    batch: Batch,
    *,
    yes: bool,
    reason: str,
    at: datetime,
    say: Callable[[str], None],
    save: Callable[[Batch], None],
) -> None:
    """The `--orphaned` plan; with *yes*, append the cancel event and nothing else."""
    say(f"cancel batch {batch.id} (left-scope)")
    say(f"  {_left(batch)}: nothing on the forge is withdrawn")
    say("  append a cancel event to judgements.yaml")
    if not yes:
        say("nothing written; re-run with --yes to act")
        return
    event = CancelEvent(kind="cancel", at=at, reason=reason)
    save(batch.model_copy(update={"events": [*batch.events, event]}))
    say(f"cancelled batch {batch.id}")
