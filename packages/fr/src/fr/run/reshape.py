"""Reshape a drifted run cursor onto the current step list (spec
2026-10-05-run-upgrade-midflight §A).

A run's cursor is a position in a step list recorded at `fr run start`. When
the shipped shape later gains or loses a step, every command refuses the
cursor. `reshape` is the pure rewrite that moves a cursor onto the new list
when that loses nothing the run recorded, and refuses (`ReshapeError`) when it
would.
"""

from __future__ import annotations

from collections.abc import Iterable

from fr.run.model import RunState, StepRecord
from fr.workflow.model import WorkflowManifest


class ReshapeError(Exception):
    """A reshape the rules refuse; nothing is written."""


def diff_ids(recorded: Iterable[str], current: Iterable[str]) -> tuple[list[str], list[str]]:
    """`(added, removed)`, each sorted: ids in `current` only / in `recorded` only."""
    rec, cur = set(recorded), set(current)
    return sorted(cur - rec), sorted(rec - cur)


def _holds_something(record: StepRecord) -> bool:
    """A record the new shape could not represent if it vanished: any unit, a
    cleared gate, who cleared it, or an emitted artifact. Lifecycle is not the
    test — a `pending` record can hold all four."""
    return (
        bool(record.units)
        or record.gate is not None
        or (record.answered_by is not None or bool(record.emitted))
    )


def reshape(state: RunState, manifest: WorkflowManifest) -> RunState:
    """`state` rewritten onto `manifest`'s step list, or `ReshapeError`.

    Rules in order; the first that fails refuses (spec §A).
    """
    name, _, recorded_schema = state.workflow.partition("@")
    if recorded_schema and str(manifest.schema_version) != recorded_schema:
        raise ReshapeError(
            f"run {state.run!r} was started against {state.workflow!r}, but {name!r} "
            f"now declares schema {manifest.schema_version}. A schema change alters the "
            "step grammar itself; reshaping across it is not a list edit."
        )

    order = [s.id for s in manifest.steps]
    added, removed = diff_ids(state.steps, order)

    for step_id in removed:
        if step_id == state.cursor:
            raise ReshapeError(
                f"step {step_id!r} was removed from {name!r} but is this run's cursor; "
                "the position it names no longer exists. Use `fr run adopt --supersede`."
            )
        if _holds_something(state.steps[step_id]):
            raise ReshapeError(
                f"step {step_id!r} was removed from {name!r} but this run recorded "
                "something on it (a unit, a cleared gate, who answered it, or an "
                "emitted artifact) that the new shape cannot represent. "
                "Use `fr run adopt --supersede`."
            )

    cursor_at = order.index(state.cursor) if state.cursor in order else -1
    for step_id in added:
        if order.index(step_id) <= cursor_at:
            raise ReshapeError(
                f"step {step_id!r} was added to {name!r} at or behind this run's cursor "
                f"({state.cursor!r}); the cursor only moves forward, so it would never "
                "run. Use `fr run adopt --supersede` to rebuild from disk."
            )

    steps: dict[str, StepRecord] = {}
    for step in manifest.steps:
        if step.id in added:
            steps[step.id] = StepRecord(state="pending", members=[m.id for m in step.steps] or None)
            continue
        record = state.steps[step.id]
        members = [m.id for m in step.steps]
        if step.steps and record.members is not None and record.members != members:
            if record.units:
                raise ReshapeError(
                    f"step {step.id!r} members changed ({record.members} -> {members}) but "
                    "it holds units keyed on the old member ids. "
                    "Use `fr run adopt --supersede`."
                )
            record = record.model_copy(update={"members": members})
        steps[step.id] = record

    if steps == state.steps and list(state.steps) == order:
        return state
    return state.model_copy(update={"steps": steps})
