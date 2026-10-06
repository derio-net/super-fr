"""The merges the driver stopped on, as `<state dir>/merge-stops.json` (gh#987).

A merge stop (`batch_merge.MergeStopError`: an unresolvable conflict, a refusal) is found
only when the merge is executed, so no pure input carries it: `drive_pass` over the facts
plans the same `merge` every pass, and the board, which asks that pass for its hint, read
"merge ready" while the driver was stopped. The driver writes each stop here, at the head
it stopped at, and clears it when the batch merges; the board reads it and shows the card
as needing the operator while the batch's PR still sits at that head.

Kept beside `drive.lock`, never in `judgements.yaml`: it is the driver's operational state,
true of one head, and a new judgements event kind would make the file unreadable to every
older `fr` (its models are closed-world). The board is a view, so a missing or unreadable
file reads as no stops, never as an error.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic

MERGE_STOPS_FILE = "merge-stops.json"
_SCHEMA = 1


@dataclass(frozen=True)
class MergeStop:
    """Why the driver stopped merging a batch, and at which PR head."""

    head: str
    reason: str
    at: str  # ISO 8601, when the driver stopped


def load_stops(target: Path) -> dict[str, MergeStop]:
    """The recorded stops by batch id; empty when there is no readable record."""
    try:
        data = json.loads((target / MERGE_STOPS_FILE).read_text(encoding="utf-8"))
        if data.get("schema") != _SCHEMA:
            return {}
        return {str(bid): MergeStop(**stop) for bid, stop in data["stops"].items()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def _write(target: Path, stops: Mapping[str, MergeStop]) -> None:
    body = {"schema": _SCHEMA, "stops": {bid: asdict(s) for bid, s in sorted(stops.items())}}
    write_text_atomic(target / MERGE_STOPS_FILE, json.dumps(body, indent=2) + "\n")


def record_stop(target: Path, batch_id: str, stop: MergeStop) -> None:
    """Record (or replace) *batch_id*'s stop."""
    stops = load_stops(target)
    if stops.get(batch_id) != stop:
        _write(target, {**stops, batch_id: stop})


def clear_stop(target: Path, batch_id: str) -> None:
    """Forget *batch_id*'s stop; nothing is written when it has none."""
    stops = load_stops(target)
    if batch_id in stops:
        del stops[batch_id]
        _write(target, stops)


def live_stop(stop: MergeStop | None, head: str | None) -> MergeStop | None:
    """*stop* while the PR still sits at the head it was recorded at; a head that moved
    is a new attempt, and an unknown head cannot prove it moved."""
    if stop is None or (head and head != stop.head):
        return None
    return stop
