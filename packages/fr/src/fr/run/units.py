"""The ONE module that knows how a run cursor stores a unit.

Spec `2026-09-20-unit-record-unification-design.md` collapsed three per-unit
maps — `StepRecord.items` (state), `StepRecord.dispatch` (attempts) and the
top-level `RunState.accounting` (cost) — into a single `StepRecord.units` map
of `UnitRecord`. Three key spaces over one identity is how a unit's state
drifted from its history: `_complete_step` carried the maps forward one at a
time and silently deleted every dispatch record the day a step completed
(finding f7), and `_advance_group` had to re-derive the join at four call
sites.

**This module is the seam that made that collapse reviewable.** Phase 2 wrote
it over the OLD shape, changing no behaviour; phase 3 re-implemented exactly
these functions over `units` and swapped the model, and the callers did not
move. The invariant that bought that is a grep — outside this module,
`fr/run/model.py`, `fr/run/legacy.py` and `fr/artifacts/`, nothing in
`packages/fr/src/fr` names `.units` on a cursor (nor, before it, `.items`,
`.dispatch` or `.accounting`). Keep it: the next shape change is this file.

So every function here is **pure and shape-neutral**: it speaks of units,
states, attempts and cost, never of which map a fact lives in. Anything that
would force a caller to know the storage — "give me the units map" — is
deliberately absent.

Two rules of the v5 shape that this module, and only this module, upholds:

- **A write to one half of a unit never drops the other.** State and attempts
  live in ONE record now, so a wholesale state write (`with_unit_states`) is
  exactly the operation that could delete a unit's history — f7, one shape
  later. Every writer below edits a `UnitRecord` with `model_copy`, never
  rebuilds one from the half it was given.
- **One timestamp.** The moment fr dispatched a unit is its attempt's
  `dispatched`, and it doubles as the START of that attempt's measurement
  window. `ContextEstimate` carries no `at`, so the moment cannot be recorded
  twice and drift; `with_estimate` takes `at=` only to REFUSE an estimate
  whose moment is not the attempt's own.

The cost WRITERS take a `step_id` and the cost READERS do not: cost hangs off
an attempt inside one step's record, so a writer must say which, while a
reader finds the key by scanning — unit keys are unique across a cursor.
"""

from __future__ import annotations

from collections.abc import Mapping

from fr.run.model import (
    Attempt,
    ContextEstimate,
    MeasuredTokens,
    RunState,
    StepRecord,
    UnitRecord,
)

__all__ = [
    "ContextEstimate",
    "MeasuredTokens",
    "UnitAttempt",
    "accounted_attempts",
    "accounted_keys",
    "attempts",
    "dispatch_recorded",
    "dispatched_attempts",
    "estimate_of",
    "estimated_at",
    "evidence_of",
    "fan_out_states",
    "last_attempt",
    "measured_of",
    "open_attempt",
    "unit_keys",
    "unit_state",
    "unit_states",
    "with_attempt_appended",
    "with_estimate",
    "with_evidence",
    "with_last_attempt_replaced",
    "with_measured",
    "with_unit_state",
    "with_unit_states",
]

UnitAttempt = Attempt
"""What one attempt to hold a unit is, named once so callers never spell the
concrete class. It was `DispatchRecord` until the v5 flip re-pointed it here —
one line, and `run_cmd.py`, which constructs
`UnitAttempt(dispatched=..., agent_type=..., harness=..., model=...)` and
annotates with it throughout, did not change."""


def _units(record: StepRecord) -> dict[str, UnitRecord]:
    """`record`'s unit map as a fresh mutable dict — the only `.units` read."""
    return dict(record.units or {})


def _with_units(record: StepRecord, mapping: dict[str, UnitRecord]) -> StepRecord:
    """`record` carrying `mapping` — the only `.units` write. An empty map is
    stored as absent, so a step with no units dumps no `units:` key at all."""
    return record.model_copy(update={"units": mapping or None})


# --------------------------------------------------------------- unit state


def unit_state(record: StepRecord, key: str) -> str | None:
    """`key`'s state under `record`, or `None` when it has none.

    `None` covers two genuinely different situations and deliberately does not
    distinguish them, because no caller needs to: a unit this step has never
    recorded, and a `step/<step-id>` unit which by §4.B carries no state at all
    (`StepRecord.state` is that fact's one home).
    """
    unit = (record.units or {}).get(key)
    return None if unit is None else unit.state


def unit_states(record: StepRecord) -> dict[str, str]:
    """Every unit of `record` that carries a state, as a plain mutable dict.

    A copy, always: the models are frozen, and a caller that merges markers
    into this map (`_advance_group`, `_resolve_member`) must not be able to
    mutate the cursor by accident. A `step/<step-id>` unit has no state and is
    therefore absent here — it is not a unit with the state `None`.
    """
    return {key: unit.state for key, unit in (record.units or {}).items() if unit.state is not None}


def with_unit_state(record: StepRecord, key: str, state: str) -> StepRecord:
    """`record` with `key`'s state set to `state`, creating the unit if needed."""
    states = unit_states(record)
    states[key] = state
    return with_unit_states(record, states)


def with_unit_states(record: StepRecord, states: dict[str, str]) -> StepRecord:
    """`record` with its unit states replaced wholesale by `states`.

    **Attempts already recorded survive — always.** State and attempts live in
    one `UnitRecord`, so this is exactly the operation that could drop a
    unit's history (the f7 defect, one shape later). Hence:

    - a key in `states` keeps its existing record and only its state moves;
    - a key NOT in `states` loses its state, but a unit that still has
      attempts or evidence is kept, stateless, rather than deleted. Callers
      only ever widen the map (`{**states, **manual_markers}`), so this is a
      guard and not a live path — but the wrong default here is silent loss.
    """
    existing = _units(record)
    merged: dict[str, UnitRecord] = {}
    for key, unit in existing.items():
        if key in states:
            continue
        if unit.attempts or unit.evidence:
            merged[key] = unit.model_copy(update={"state": None})
    for key, state in states.items():
        prior = existing.get(key)
        merged[key] = (
            UnitRecord.model_validate({"state": state})
            if prior is None
            else UnitRecord.model_validate({**prior.model_dump(), "state": state})
        )
    # Order: the caller's order for stated units (it is what `fr run status`
    # prints and what a diff of the cursor shows), stateless survivors first
    # only because they were there first.
    return _with_units(record, merged)


# ------------------------------------------------------------------ attempts


def attempts(record: StepRecord, key: str) -> tuple[UnitAttempt, ...]:
    """Every attempt recorded for `key`, oldest first — empty when there are
    none. An empty tuple is a real answer, never "unknown": a unit fr adopted
    from a plan on disk was genuinely never dispatched."""
    unit = (record.units or {}).get(key)
    return () if unit is None else tuple(unit.attempts)


def open_attempt(record: StepRecord, key: str) -> UnitAttempt | None:
    """`key`'s OPEN attempt (`returned is None`), or `None` when it is free.

    The witness of decision u1: a unit is HELD iff this is not `None`. At most
    one attempt is open and it is the LAST one — `validate_run` enforces both —
    so the tail is the whole answer. A `synthesized` attempt is never a hold
    (`fr.run.model.Attempt.synthesized`): it has no `returned` only because fr
    never knew one, and its unit may long since be `done`.
    """
    recorded = attempts(record, key)
    if not recorded or recorded[-1].returned is not None or recorded[-1].synthesized:
        return None
    return recorded[-1]


def dispatch_recorded(record: StepRecord, key: str) -> bool:
    """Did fr ever RECORD dispatching `key` — is there any witness at all?

    False for a unit with no attempts (adopted from disk, or never reached),
    and ALSO for one whose only attempt is `synthesized`: that attempt carries
    a migrated cost snapshot, not a hold, and a cursor that predates the
    dispatch record has no witness however much it has spent. `advance` falls
    back to the unit's state in exactly this case and no other (decision u1).
    """
    return any(not attempt.synthesized for attempt in attempts(record, key))


def _with_attempts(record: StepRecord, key: str, recorded: tuple[UnitAttempt, ...]) -> StepRecord:
    mapping = _units(record)
    unit = mapping.get(key) or UnitRecord()
    mapping[key] = unit.model_copy(update={"attempts": recorded})
    return _with_units(record, mapping)


def with_attempt_appended(record: StepRecord, key: str, attempt: UnitAttempt) -> StepRecord:
    """`record` with `attempt` appended to `key`'s history.

    Never overwrites: a failed unit that is retried, or one `--redispatch`ed
    over a lost agent, keeps every prior attempt. That list is the forensic
    trail gh-503 asked for. The unit's STATE is untouched — and a unit that
    did not exist yet is created without one, which is exactly right for the
    one caller that does that: a flat step's `step/<step-id>` unit (§4.B).
    """
    return _with_attempts(record, key, (*attempts(record, key), attempt))


def with_last_attempt_replaced(record: StepRecord, key: str, attempt: UnitAttempt) -> StepRecord:
    """`record` with `key`'s LAST attempt replaced by `attempt`.

    The one mutation shape every write to an open hold shares — `claim`'s
    identity fill, `claim --abandoned`, `--redispatch`'s abandon and
    `resolve`'s close all rewrite exactly the tail, because the open attempt
    IS the tail. Callers establish that the unit is held (`open_attempt`);
    this does not re-derive it, so there stays exactly one place that decides
    what "open" means. A key with no attempt at all is a caller bug and raises
    `KeyError`, as it did when the attempts had a map of their own.
    """
    recorded = attempts(record, key)
    if not recorded:
        raise KeyError(key)
    return _with_attempts(record, key, (*recorded[:-1], attempt))


# --------------------------------------------------------------- evidence


def evidence_of(record: StepRecord, key: str) -> dict[str, str]:
    """`key`'s verified evidence — `{obligation: journal entry id}` (§4.E).

    An empty dict is a real answer and covers two situations the caller does
    not need to tell apart: a step that declares no obligation at all, and a
    unit resolved before the gate existed. The SECOND is visible debt — but
    "which units owe evidence" is a question about the MANIFEST (which steps
    declare it), not about the cursor, so it is answered by the caller that
    has one, not guessed at here.

    A copy: the models are frozen, and no reader may hand a caller something
    that looks mutable but silently is not part of the cursor.
    """
    unit = (record.units or {}).get(key)
    return dict(unit.evidence or {}) if unit is not None else {}


def with_evidence(record: StepRecord, key: str, evidence: Mapping[str, str]) -> StepRecord:
    """`record` with `evidence` MERGED onto `key`'s existing evidence.

    Merged, never replaced, for the same reason `_resolve_member` merges
    `emitted`: a step may carry more than one obligation and they need not be
    satisfied in one call. The unit is created (stateless) when absent rather
    than silently dropping the write — `with_unit_states` already keeps a
    stateless unit that has evidence, so such a record is representable and
    must not be lost between here and there.
    """
    mapping = _units(record)
    prior = mapping.get(key)
    merged = {**(prior.evidence if prior is not None and prior.evidence else {}), **evidence}
    base = prior.model_dump() if prior is not None else {}
    mapping[key] = UnitRecord.model_validate({**base, "evidence": merged or None})
    return _with_units(record, mapping)


# ----------------------------------------------------------------- the units


def unit_keys(record: StepRecord) -> tuple[str, ...]:
    """Every unit key `record` knows anything about, sorted.

    A flat `kind: agent` step records a `step/<step-id>` unit with attempts
    and no state, and it must not be invisible to a walk.
    """
    return tuple(sorted(record.units or {}))


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
#
# Cost is per ATTEMPT (decision u2), and this section answers at BOTH grains.
#
# Per attempt — `last_attempt` (what a writer touches: `advance` estimates the
# attempt it just opened, `resolve` and `claim --abandoned` measure the one
# they just closed, and both are the tail), `accounted_attempts` and
# `dispatched_attempts` (what `fr run status` renders and totals, so a
# redispatched unit's abandoned spend is in the figures rather than behind
# them).
#
# Per unit — `estimate_of` / `measured_of` / `estimated_at` / `accounted_keys`,
# which answer for the unit's LAST attempt: that is the attempt a cost was
# last written to and, for a migrated v4 cursor, the one the rewrite attached
# the unit's single snapshot to. Never a substitute for the per-attempt view:
# on a redispatched unit they show the retry and hide the abandoned spend.
#
# NOTE for review (phase 4): those four now have NO caller in `src/`. Phase 4
# re-pointed `_with_measurement` at `last_attempt` and `fr run status` at
# `accounted_attempts`, and the per-unit question went with them. They are
# still exercised — `tests/unit/test_run_cli.py`'s `_Snapshot` reads a unit's
# cost through them rather than through the storage, which is the seam this
# module exists to offer — so they are not dead in the sense
# `with_units_carried_forward` was. Flagged rather than deleted so review can
# decide, the way phase 3 flagged that one.


def _owner(state: RunState, key: str) -> str | None:
    for step_id, record in state.steps.items():
        if key in (record.units or {}):
            return step_id
    return None


def last_attempt(state: RunState, key: str) -> UnitAttempt | None:
    """`key`'s most recent attempt anywhere in `state`, or `None`.

    The attempt every cost WRITE lands on — `advance` estimates the one it
    just opened; `resolve` and `claim --abandoned` measure the one they just
    closed — and both are the tail by construction. Handed back whole rather
    than as a timestamp, because a measurement needs four of its fields at
    once: the window edges `dispatched`/`returned`, and the `(session, agent)`
    pair that says WHICH transcript is this attempt's (§4.D.1).
    """
    step_id = _owner(state, key)
    if step_id is None:
        return None
    recorded = attempts(state.steps[step_id], key)
    return recorded[-1] if recorded else None


_last_attempt = last_attempt


def accounted_attempts(state: RunState) -> tuple[tuple[str, UnitAttempt], ...]:
    """Every `(unit key, attempt)` in `state` that carries an estimate —
    key-sorted, and within a unit oldest attempt first.

    Cost is per ATTEMPT (decision u2), so a REDISPATCHED unit contributes
    twice and the abandoned attempt's spend — exactly the spend worth seeing
    — lands in the totals rather than being overwritten by the retry.
    `accounted_keys` answers the older, per-unit question and is not a
    substitute: on a unit with two attempts it yields one key, and the
    earlier figure is invisible.
    """
    found = [
        (key, attempt)
        for record in state.steps.values()
        for key, unit in (record.units or {}).items()
        for attempt in unit.attempts
        if attempt.estimate is not None
    ]
    # `key=` on the key alone: `Attempt` is not orderable, and the sort is
    # stable, so two attempts of one unit keep their oldest-first order.
    return tuple(sorted(found, key=lambda pair: pair[0]))


def dispatched_attempts(state: RunState) -> int:
    """How many attempts `state` records at all — the denominator of
    "measured N of M".

    Attempts, not units: the numerator counts attempts now, so a denominator
    of units would report better coverage than there is the moment one unit is
    redispatched. A `synthesized` attempt counts — it carries a real cost
    snapshot a measurement could still land beside.
    """
    return sum(
        len(unit.attempts)
        for record in state.steps.values()
        for unit in (record.units or {}).values()
    )


def accounted_keys(state: RunState) -> tuple[str, ...]:
    """Every unit key whose LAST attempt records a cost, sorted — across all
    steps.

    Sorted by KEY and not grouped by step: that is what the v4 top-level
    `accounting` map rendered, and the per-step storage must not quietly
    reorder `fr run status`. Per UNIT, so it cannot see a redispatched unit's
    earlier attempt — `accounted_attempts` is what renders and totals those.
    """
    return tuple(
        sorted(
            key
            for record in state.steps.values()
            for key, unit in (record.units or {}).items()
            if unit.attempts and unit.attempts[-1].estimate is not None
        )
    )


# --- per-unit cost readers: TEST SEAM ONLY -------------------------------
# `estimate_of`, `measured_of`, `estimated_at` and `accounted_keys` answer for a
# unit's LAST attempt. Production code must iterate attempts instead — a per-unit
# read is the exact shape of the defect that discarded an abandoned attempt's
# cost. `tests/unit/test_tripwire_per_unit_cost_reads.py` fails on a new caller
# anywhere under `packages/*/src`.
def estimate_of(state: RunState, key: str) -> ContextEstimate | None:
    """What fr assembled for `key` — the V1 sizes — or `None` if unrecorded."""
    last = _last_attempt(state, key)
    return None if last is None else last.estimate


def estimated_at(state: RunState, key: str) -> str | None:
    """When fr assembled `key`'s context — the START of its measurement window.

    It IS the attempt's `dispatched`: one moment, recorded once. `advance`
    stamps it before the dispatch brief is built, so it precedes every
    transcript record of the dispatch it measures. `None` when there is no
    estimate — no window, no measurement — which is also what an attempt
    opened without one (a flat `kind: agent` step) reads as.
    """
    last = _last_attempt(state, key)
    if last is None or last.estimate is None:
        return None
    return last.dispatched


def measured_of(state: RunState, key: str) -> MeasuredTokens | None:
    """What `key` actually burned, or `None` when nothing was measured.

    A measurement is atomic, and in this shape that is structural: a
    `MeasuredTokens` has all four figures or does not exist.
    """
    last = _last_attempt(state, key)
    return None if last is None else last.measured


def _with_last_attempt(state: RunState, step_id: str, key: str, attempt: UnitAttempt) -> RunState:
    steps = dict(state.steps)
    steps[step_id] = with_last_attempt_replaced(steps[step_id], key, attempt)
    return state.model_copy(update={"steps": steps})


def with_estimate(
    state: RunState,
    step_id: str,
    key: str,
    estimate: ContextEstimate,
    *,
    at: str,
) -> RunState:
    """`state` with `estimate` recorded on `key`'s LAST attempt under `step_id`.

    `at` is the moment the estimate was assembled, and it must BE that
    attempt's `dispatched` — otherwise this raises `ValueError`. That is the
    "one timestamp" rule with teeth: the estimate is COMPUTED before the brief
    and the attempt is OPENED after it, and the easy mistake is to let the
    attempt stamp its own, later, `dispatched` — which silently moves the
    start of the measurement window past the dispatch it measures. Callers
    pass the same `at` to both; this checks that they did.

    Also raises when `key` has no attempt under `step_id`: an estimate is what
    fr assembled FOR an attempt, so there is nothing to record it on. fr never
    synthesizes an attempt at run time — only the 4 -> 5 migration does, once,
    for cursors that predate the dispatch record.
    """
    recorded = attempts(state.steps[step_id], key)
    if not recorded:
        raise ValueError(f"unit {key!r} of step {step_id!r} has no attempt to estimate")
    if recorded[-1].dispatched != at:
        raise ValueError(
            f"unit {key!r}: the estimate was assembled at {at!r} but its attempt says it was "
            f"dispatched at {recorded[-1].dispatched!r} — one moment, recorded once"
        )
    return _with_last_attempt(
        state, step_id, key, recorded[-1].model_copy(update={"estimate": estimate})
    )


def with_measured(state: RunState, step_id: str, key: str, measured: MeasuredTokens) -> RunState:
    """`state` with `measured` recorded BESIDE the estimate of `key`'s last
    attempt under `step_id`.

    Beside, never replacing: the estimate and the measurement are different
    quantities (one dispatch's assembled context versus cumulative billing
    across its turns) and `fr run status` is built on showing both. A unit
    whose last attempt has no estimate has no measurement window either, so
    there is nothing to measure against and `state` comes back unchanged.
    """
    record = state.steps.get(step_id)
    recorded = attempts(record, key) if record is not None else ()
    if not recorded or recorded[-1].estimate is None:
        return state
    return _with_last_attempt(
        state, step_id, key, recorded[-1].model_copy(update={"measured": measured})
    )
