"""The ONE module that knows how a run cursor stores a unit.

Spec `2026-09-20-unit-record-unification-design.md` collapses three per-unit
maps — `StepRecord.items` (state), `StepRecord.dispatch` (attempts) and the
top-level `RunState.accounting` (cost) — into a single `StepRecord.units` map
of `UnitRecord`. Three key spaces over one identity is how a unit's state
drifted from its history: `_complete_step` carried the maps forward one at a
time and silently deleted every dispatch record the day a step completed
(finding f7), and `_advance_group` had to re-derive the join at four call
sites.

**This module is the seam that makes that collapse reviewable.** Today it is
implemented over the OLD shape and changes no behaviour whatsoever; phase 3
re-implements exactly these functions over `units` and swaps the model, with
no other file touched. The invariant that buys that is a grep — outside this
module, `fr/run/model.py`, `fr/run/legacy.py` and `fr/artifacts/`, nothing in
`packages/fr/src/fr` names `.items`, `.dispatch` or `.accounting` on a cursor.

So every function here is **pure and shape-neutral**: it speaks of units,
states, attempts and cost, never of which map a fact lives in. Anything that
would force a caller to know the storage — "give me the dispatch map" — is
deliberately absent.

Two signature choices exist for phase 3 rather than for today:

- the cost WRITERS take a `step_id`, the cost READERS do not. Today
  `accounting` is a top-level map that does not record which step owns a key,
  so reading needs no step and writing ignores the one it is given; in the v5
  shape the cost hangs off an attempt inside a step, so the writer needs it
  and the reader still finds the key by scanning. Taking it now means phase 3
  changes no call site.
- `with_estimate` takes `at` explicitly instead of stamping `_now()` itself.
  The estimate's timestamp is the start of the measurement window, and it is
  computed *before* the dispatch brief is built; in v5 that same moment is the
  attempt's `dispatched`. Passing it in keeps those two from drifting apart by
  a second.
"""

from __future__ import annotations

from fr.run.model import (
    ContextEstimate,
    DispatchRecord,
    MeasuredTokens,
    PhaseAccounting,
    RunState,
    StepRecord,
)

__all__ = [
    "ContextEstimate",
    "MeasuredTokens",
    "UnitAttempt",
    "accounted_keys",
    "attempts",
    "estimate_of",
    "estimated_at",
    "fan_out_states",
    "measured_of",
    "open_attempt",
    "unit_keys",
    "unit_state",
    "unit_states",
    "with_attempt_appended",
    "with_estimate",
    "with_last_attempt_replaced",
    "with_measured",
    "with_unit_state",
    "with_unit_states",
    "with_units_carried_forward",
]

UnitAttempt = DispatchRecord
"""What one attempt to hold a unit is, named once so callers never spell the
concrete class. Phase 3 re-points this at `fr.run.model.Attempt`, which carries
the same fields plus `session`/`estimate`/`measured` — so a call site that
constructs `UnitAttempt(dispatched=..., agent_type=..., harness=..., model=...)`
keeps working unchanged."""


# --------------------------------------------------------------- unit state


def unit_state(record: StepRecord, key: str) -> str | None:
    """`key`'s state under `record`, or `None` when it has none.

    `None` covers two genuinely different situations and deliberately does not
    distinguish them, because no caller needs to: a unit this step has never
    recorded, and a `step/<step-id>` unit which by §4.B carries no state at all
    (`StepRecord.state` is that fact's one home).
    """
    return (record.items or {}).get(key)


def unit_states(record: StepRecord) -> dict[str, str]:
    """Every unit of `record` that carries a state, as a plain mutable dict.

    A copy, always: the models are frozen, and a caller that merges markers
    into this map (`_advance_group`, `_resolve_member`) must not be able to
    mutate the cursor by accident.
    """
    return dict(record.items or {})


def with_unit_state(record: StepRecord, key: str, state: str) -> StepRecord:
    """`record` with `key`'s state set to `state`, creating the unit if needed."""
    states = unit_states(record)
    states[key] = state
    return with_unit_states(record, states)


def with_unit_states(record: StepRecord, states: dict[str, str]) -> StepRecord:
    """`record` with its unit states replaced wholesale by `states`.

    **Attempts already recorded survive.** That is the whole reason this is a
    function and not an assignment: in the v5 shape state and attempts live in
    one record, so a wholesale state write is exactly the operation that could
    drop a unit's history — the f7 defect, one shape later. Today the two maps
    are separate and the guarantee is free; it is asserted by a test so that it
    stays true when it stops being free.
    """
    return record.model_copy(update={"items": dict(states) if states else None})


# ------------------------------------------------------------------ attempts


def attempts(record: StepRecord, key: str) -> tuple[UnitAttempt, ...]:
    """Every attempt recorded for `key`, oldest first — empty when there are
    none. An empty tuple is a real answer, never "unknown": a unit fr adopted
    from a plan on disk was genuinely never dispatched."""
    return tuple((record.dispatch or {}).get(key) or ())


def open_attempt(record: StepRecord, key: str) -> UnitAttempt | None:
    """`key`'s OPEN attempt (`returned is None`), or `None` when it is free.

    The witness of decision u1: a unit is HELD iff this is not `None`. At most
    one attempt is open and it is the LAST one — `validate_run` enforces both —
    so the tail is the whole answer.
    """
    recorded = attempts(record, key)
    if not recorded or recorded[-1].returned is not None:
        return None
    return recorded[-1]


def with_attempt_appended(record: StepRecord, key: str, attempt: UnitAttempt) -> StepRecord:
    """`record` with `attempt` appended to `key`'s history.

    Never overwrites: a failed unit that is retried, or one `--redispatch`ed
    over a lost agent, keeps every prior attempt. That list is the forensic
    trail gh-503 asked for.
    """
    dispatch = dict(record.dispatch or {})
    dispatch[key] = [*(dispatch.get(key) or []), attempt]
    return record.model_copy(update={"dispatch": dispatch})


def with_last_attempt_replaced(record: StepRecord, key: str, attempt: UnitAttempt) -> StepRecord:
    """`record` with `key`'s LAST attempt replaced by `attempt`.

    The one mutation shape every write to an open hold shares — `claim`'s
    identity fill, `claim --abandoned`, `--redispatch`'s abandon and
    `resolve`'s close all rewrite exactly the tail, because the open attempt
    IS the tail. Callers establish that the unit is held (`open_attempt`);
    this does not re-derive it, so there stays exactly one place that decides
    what "open" means.
    """
    dispatch = dict(record.dispatch or {})
    recorded = list(dispatch[key])
    recorded[-1] = attempt
    dispatch[key] = recorded
    return record.model_copy(update={"dispatch": dispatch})


# ----------------------------------------------------------------- the units


def unit_keys(record: StepRecord) -> tuple[str, ...]:
    """Every unit key `record` knows anything about, sorted.

    The union of "has a state" and "has attempts", because both are units. A
    flat `kind: agent` step records a `step/<step-id>` unit with attempts and
    no state, and it must not be invisible to a walk.
    """
    return tuple(sorted({*(record.items or {}), *(record.dispatch or {})}))


def with_units_carried_forward(record: StepRecord, prior: StepRecord) -> StepRecord:
    """`record`, carrying every unit `prior` recorded — state AND attempts.

    Finding f7's fix, as one function rather than as a field list. Completing
    a step rebuilds its record from scratch, and carrying the maps forward one
    at a time is how the whole run's holder history came to be deleted by the
    act of FINISHING: the only readers are `status`/`check`, so the deletion
    was silent. Passing the unit data as one thing makes forgetting half of it
    unexpressible, which is what phase 3 needs — there the two halves are one
    object and a partial copy would be a new defect in a new shape.
    """
    return record.model_copy(
        update={
            "items": dict(prior.items) if prior.items else None,
            "dispatch": dict(prior.dispatch) if prior.dispatch else None,
        }
    )


def fan_out_states(state: RunState) -> dict[str, str]:
    """The unit states of the step that fans out — NOT of the cursor.

    At most one step of a shape fans out (`for_each: phase`), and adoption
    deliberately moves the cursor PAST it when every phase is done, so reading
    the cursor's record made "N/M phases complete" vanish for exactly the steps
    where it is most worth printing. Scanning for the record that carries unit
    states needs no knowledge of the workflow's step names.
    """
    for record in state.steps.values():
        states = unit_states(record)
        if states:
            return states
    return {}


# --------------------------------------------------------------------- cost


def accounted_keys(state: RunState) -> tuple[str, ...]:
    """Every unit key `state` records a cost for, sorted — across all steps.

    Sorted by KEY and not grouped by step, which is what today's top-level
    `accounting` map renders and therefore what must keep rendering. In
    practice one step fans out, so every accounted key belongs to it; the
    ordering is stated here rather than left to the storage so that phase 3's
    per-step walk cannot quietly reorder `fr run status`.
    """
    return tuple(sorted(state.accounting or {}))


def _snapshot(state: RunState, key: str) -> PhaseAccounting | None:
    return (state.accounting or {}).get(key)


def estimate_of(state: RunState, key: str) -> ContextEstimate | None:
    """What fr assembled for `key` — the V1 sizes — or `None` if unrecorded."""
    snap = _snapshot(state, key)
    if snap is None:
        return None
    return ContextEstimate(
        journal_entries=snap.journal_entries,
        journal_lines=snap.journal_lines,
        handoff_chars=snap.handoff_chars,
        spec_bytes=snap.spec_bytes,
        plan_bytes=snap.plan_bytes,
    )


def estimated_at(state: RunState, key: str) -> str | None:
    """When fr assembled `key`'s context — the START of its measurement window.

    Written immediately before the dispatch brief, so it precedes every
    transcript record of the dispatch it measures. `None` when there is no
    estimate, and also when there is one with no timestamp (a pre-`at`
    snapshot): both mean the same thing to the only caller — no window, no
    measurement.
    """
    snap = _snapshot(state, key)
    return None if snap is None else snap.at


def measured_of(state: RunState, key: str) -> MeasuredTokens | None:
    """What `key` actually burned, or `None` when nothing was measured.

    A measurement is atomic: a snapshot carrying only some of the four figures
    is not a small honest number, it is a structural problem
    (`fr.artifacts.structure.validate_run` reports it as one), so it reads here
    as no measurement at all rather than as a partial sum.
    """
    snap = _snapshot(state, key)
    if snap is None:
        return None
    values = snap.measured_fields()
    if any(value is None for value in values.values()):
        return None
    return MeasuredTokens.model_validate(values)


def with_estimate(
    state: RunState,
    step_id: str,
    key: str,
    estimate: ContextEstimate,
    *,
    at: str,
) -> RunState:
    """`state` with `estimate` recorded for `key` under `step_id`, stamped `at`.

    `step_id` is unused today — `accounting` is a top-level map that does not
    record which step owns a key — and is taken anyway, because in the v5 shape
    the estimate hangs off an attempt inside that step's record. Recording it
    now is what lets phase 3 change this body and nothing else.

    Callers write this AFTER the attempt is opened, even though `at` was
    computed before: in v5 there has to be an attempt for the estimate to hang
    off, and `at` carries the earlier moment so the measurement window still
    starts before the dispatch it measures.
    """
    _ = step_id
    snaps = dict(state.accounting or {})
    snaps[key] = PhaseAccounting(
        at=at,
        journal_entries=estimate.journal_entries,
        journal_lines=estimate.journal_lines,
        handoff_chars=estimate.handoff_chars,
        spec_bytes=estimate.spec_bytes,
        plan_bytes=estimate.plan_bytes,
    )
    return state.model_copy(update={"accounting": snaps})


def with_measured(state: RunState, step_id: str, key: str, measured: MeasuredTokens) -> RunState:
    """`state` with `measured` folded in beside `key`'s existing estimate.

    Folded IN, never replacing: the estimate and the measurement are different
    quantities (one dispatch's assembled context versus cumulative billing
    across its turns) and `fr run status` is built on showing both. A unit with
    no estimate at all has no window either, so there is nothing to fold into
    and `state` comes back unchanged.
    """
    _ = step_id
    snaps = dict(state.accounting or {})
    snap = snaps.get(key)
    if snap is None:
        return state
    snaps[key] = snap.model_copy(update=measured.model_dump())
    return state.model_copy(update={"accounting": snaps})
