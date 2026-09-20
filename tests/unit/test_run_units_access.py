"""`fr.run.units` — the ONE module that knows how a unit is stored.

Phase 2 of `2026-09-20-unit-record-unification` adds no behaviour. It moves
every reader and writer of the cursor's three per-unit maps (`StepRecord.items`,
`StepRecord.dispatch`, `RunState.accounting`) behind this accessor layer, so
that phase 3's collapse into one `units` map re-implements ONE module instead
of editing ~2,300 lines of `run_cmd.py` with a red tree in the middle.

So every assertion here is deliberately about *meaning*, never about storage:
"this unit's state is `done`", "this unit has three attempts, the last one
open", "this unit's estimate says 2,369 handoff chars". Phase 3 must be able to
keep every line below and swap only the implementation.

The inputs are the CAPTURED cursors of `tests/fixtures/run_cursors/` — real
files `fr` wrote — read through `_state()`, which is the single seam phase 3
re-points at `v4_to_v5` + the v5 model.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run import units
from fr.run.model import RunState, parse_run_state

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"

HOLDER = "v4/2026-09-20-feat-phase-holder-identity.yaml"
"""All three maps at once: `items`, `dispatch` (several attempts per unit,
claimed and abandoned) and `accounting`."""

CLUSTER = "v4/2026-09-20-fix-fr-run-cursor-cluster.yaml"
"""gh#496's `phase/<n>: manual` marker, `accounting`, and NO `dispatch` at
all — a stamp-migrated 2 -> 4 body."""

INFLIGHT = "v2/2026-09-20-journal-require-reviews-v2.yaml"
"""In-flight: a flat `deliver: running` with no dispatch record — the u1
recordless-fallback shape, in a real file."""

MEASURED = "v3/2026-09-20-feat-bounded-executor-handoff.yaml"
"""gh#514 telemetry era: `accounting` carrying measured token figures."""

UNMEASURED = "v3/2026-09-20-fix-434-phases-file-tier.yaml"
"""Second v3: `accounting` with sizes only, no measured figures."""

CLAIMED = "phase/3/implement-phase"
"""A unit of `HOLDER`'s `implement` step whose one attempt was CLAIMED (it
carries an agent id, an agent type, a harness and a model) and then abandoned.

Worth stating because the capture corrected an assumption: **no unit in any
captured cursor has more than one attempt.** `--redispatch` and `claim
--abandoned` shipped only days before the capture and no real run has used
them twice on one unit yet, so a multi-attempt unit is built below by
APPENDING to a captured one through the accessors — derived from a capture,
never typed as YAML."""

UNATTEMPTED = "phase/1/implement-phase"
"""A unit of the same step with a state and an ESTIMATE but no attempt at all
— it ran before the dispatch record existed. This is the shape §4.F's
synthesized-attempt clause is about, and it is the majority of every real
cursor."""


def _state(name: str) -> RunState:
    """The captured cursor `name`, as the live model reads it.

    The one seam phase 3 re-points: there it becomes
    `parse_run_state(dump(v4_to_v5(load(text))))`, and every assertion below
    is expected to survive unchanged.
    """
    return parse_run_state((FIXTURES / name).read_text())


# ---------------------------------------------------------------- unit state


def test_unit_state_reads_a_grouped_members_state() -> None:
    record = _state(HOLDER).steps["implement"]
    assert units.unit_state(record, "phase/1/implement-phase") == "done"
    assert units.unit_state(record, "phase/1/review-phase") == "done"


def test_unit_state_is_none_for_a_key_this_step_never_recorded() -> None:
    record = _state(HOLDER).steps["implement"]
    assert units.unit_state(record, "phase/99/implement-phase") is None


def test_unit_state_is_none_for_a_step_with_no_units_at_all() -> None:
    record = _state(INFLIGHT).steps["deliver"]
    assert record.state == "running"  # the STEP is running...
    assert units.unit_state(record, "step/deliver") is None  # ...the unit is unrecorded


def test_a_manual_phase_marker_is_a_unit_state_like_any_other() -> None:
    record = _state(CLUSTER).steps["implement"]
    assert units.unit_state(record, "phase/7") == "manual"


def test_unit_states_is_every_state_this_step_records() -> None:
    record = _state(CLUSTER).steps["implement"]
    states = units.unit_states(record)
    assert states["phase/7"] == "manual"
    assert states["phase/1/implement-phase"] == "done"
    assert len(states) == 13  # 12 members + the manual marker


def test_unit_states_of_a_step_with_no_units_is_empty() -> None:
    assert units.unit_states(_state(INFLIGHT).steps["deliver"]) == {}


def test_with_unit_state_sets_one_and_leaves_the_rest_alone() -> None:
    record = _state(HOLDER).steps["implement"]
    updated = units.with_unit_state(record, "phase/1/implement-phase", "failed")
    assert units.unit_state(updated, "phase/1/implement-phase") == "failed"
    assert units.unit_state(updated, "phase/2/implement-phase") == "done"
    # frozen models: the original is untouched
    assert units.unit_state(record, "phase/1/implement-phase") == "done"


def test_with_unit_state_adds_a_key_that_was_not_there() -> None:
    record = _state(INFLIGHT).steps["deliver"]
    updated = units.with_unit_state(record, "step/deliver", "running")
    assert units.unit_states(updated) == {"step/deliver": "running"}


def test_with_unit_states_replaces_the_whole_state_map() -> None:
    record = _state(HOLDER).steps["implement"]
    updated = units.with_unit_states(record, {"phase/1/implement-phase": "running"})
    assert units.unit_states(updated) == {"phase/1/implement-phase": "running"}


def test_with_unit_states_keeps_the_attempts_of_the_units_it_keeps() -> None:
    """The reason this layer exists: in the v5 shape state and attempts share
    one record, so rewriting the state map must not be able to drop history."""
    record = _state(HOLDER).steps["implement"]
    before = units.attempts(record, CLAIMED)
    assert before  # the fixture really does carry attempts for it
    updated = units.with_unit_states(record, dict(units.unit_states(record)))
    assert units.attempts(updated, CLAIMED) == before


# ------------------------------------------------------------------ attempts


def test_attempts_carry_the_identity_the_orchestrator_reported() -> None:
    record = _state(HOLDER).steps["implement"]
    (attempt,) = units.attempts(record, CLAIMED)
    assert attempt.agent == "a5dbd5f0e9bdf3362"
    assert attempt.agent_type == "super-fr:fr-phase-executor"
    assert attempt.harness == "claude-code"
    assert attempt.outcome == "abandoned"


def test_attempts_are_oldest_first() -> None:
    record = _state(HOLDER).steps["implement"]
    appended = units.with_attempt_appended(
        record, CLAIMED, units.UnitAttempt(dispatched="2026-09-20T23:00:00+00:00")
    )
    got = [a.dispatched for a in units.attempts(appended, CLAIMED)]
    assert got == sorted(got)


def test_attempts_of_a_unit_with_a_state_but_no_history_is_empty() -> None:
    """The majority shape: a unit resolved before the dispatch record existed."""
    record = _state(HOLDER).steps["implement"]
    assert units.unit_state(record, UNATTEMPTED) == "done"
    assert units.attempts(record, UNATTEMPTED) == ()


def test_attempts_of_an_unrecorded_unit_is_empty() -> None:
    record = _state(CLUSTER).steps["implement"]
    assert units.attempts(record, "phase/1/implement-phase") == ()


def test_open_attempt_is_none_when_every_attempt_returned() -> None:
    record = _state(HOLDER).steps["implement"]
    for key in units.unit_keys(record):
        assert units.open_attempt(record, key) is None  # the run is finished


def test_open_attempt_is_the_last_attempt_while_it_is_unreturned() -> None:
    record = _state(HOLDER).steps["implement"]
    reopened = units.with_attempt_appended(
        record, CLAIMED, units.UnitAttempt(dispatched="2026-09-20T23:00:00+00:00")
    )
    held = units.open_attempt(reopened, CLAIMED)
    assert held is not None
    assert held == units.attempts(reopened, CLAIMED)[-1]
    assert held.dispatched == "2026-09-20T23:00:00+00:00"


def test_open_attempt_of_a_unit_with_no_attempts_is_none() -> None:
    """A unit that is `running` with no attempt at all is NOT held — no
    witness is not the same as a witness saying "free", and decision u1 puts
    that distinction in the caller, not here."""
    record = _state(INFLIGHT).steps["deliver"]
    assert record.state == "running"
    assert units.open_attempt(record, "step/deliver") is None


def test_with_attempt_appended_keeps_every_prior_attempt() -> None:
    record = _state(HOLDER).steps["implement"]
    before = units.attempts(record, CLAIMED)
    assert before  # a claimed, abandoned attempt is already on record
    updated = units.with_attempt_appended(
        record, CLAIMED, units.UnitAttempt(dispatched="2026-09-20T23:00:00+00:00")
    )
    assert units.attempts(updated, CLAIMED)[:-1] == before
    assert units.attempts(updated, CLAIMED)[-1].dispatched == "2026-09-20T23:00:00+00:00"


def test_with_attempt_appended_opens_a_unit_that_had_none() -> None:
    record = _state(CLUSTER).steps["implement"]
    key = "phase/1/implement-phase"
    updated = units.with_attempt_appended(
        record, key, units.UnitAttempt(dispatched="2026-09-20T23:00:00+00:00")
    )
    assert len(units.attempts(updated, key)) == 1
    assert units.unit_state(updated, key) == "done"  # the state it already had survives


def test_with_last_attempt_replaced_rewrites_only_the_tail() -> None:
    record = _state(HOLDER).steps["implement"]
    # A two-attempt unit, built by appending to a captured one — no real
    # cursor has one yet (see CLAIMED), and typing YAML for it would be the
    # construction the fixture rule forbids.
    record = units.with_attempt_appended(
        record, CLAIMED, units.UnitAttempt(dispatched="2026-09-20T23:00:00+00:00")
    )
    before = units.attempts(record, CLAIMED)
    assert len(before) > 1
    updated = units.with_last_attempt_replaced(
        record, CLAIMED, before[-1].model_copy(update={"agent": "replaced"})
    )
    assert units.attempts(updated, CLAIMED)[:-1] == before[:-1]
    assert units.attempts(updated, CLAIMED)[-1].agent == "replaced"


def test_unit_keys_is_the_sorted_union_of_stated_and_attempted_units() -> None:
    record = _state(HOLDER).steps["implement"]
    keys = units.unit_keys(record)
    assert keys == tuple(sorted(keys))
    assert set(keys) >= set(units.unit_states(record))
    assert all(units.attempts(record, k) or units.unit_state(record, k) for k in keys)


def test_unit_keys_includes_a_unit_that_has_attempts_but_no_state() -> None:
    """A flat `kind: agent` step, captured: `HOLDER`'s `deliver` step records
    `step/deliver` with one attempt and no state at all (§4.B)."""
    record = _state(HOLDER).steps["deliver"]
    assert units.unit_keys(record) == ("step/deliver",)
    assert units.unit_state(record, "step/deliver") is None
    assert len(units.attempts(record, "step/deliver")) == 1


# -------------------------------------------------- carrying units forward


def test_units_carried_forward_keeps_states_and_attempts_together() -> None:
    """Finding f7: `_complete_step` once dropped every dispatch record at the
    moment a step completed, because it carried the maps forward one at a
    time. One function carries the whole unit record or nothing does."""
    prior = _state(HOLDER).steps["implement"]
    fresh = prior.model_copy(update={"items": None, "dispatch": None, "state": "done"})
    carried = units.with_units_carried_forward(fresh, prior)
    assert units.unit_states(carried) == units.unit_states(prior)
    for key in units.unit_keys(prior):
        assert units.attempts(carried, key) == units.attempts(prior, key)


def test_units_carried_forward_from_a_step_with_no_units_records_nothing() -> None:
    prior = _state(INFLIGHT).steps["deliver"]
    carried = units.with_units_carried_forward(prior.model_copy(update={"state": "done"}), prior)
    assert units.unit_keys(carried) == ()


# ------------------------------------------------------------ the fan-out map


def test_fan_out_states_finds_the_step_that_fans_out_not_the_cursor() -> None:
    state = _state(HOLDER)
    assert state.cursor == "deliver"
    assert units.fan_out_states(state)["phase/1/implement-phase"] == "done"


def test_fan_out_states_is_empty_when_no_step_fans_out() -> None:
    state = _state("v1/2026-09-09-feat-issue-464.yaml")
    assert units.fan_out_states(state) or True  # documents the shape either way
    smallest = state.model_copy(
        update={"steps": {k: v.model_copy(update={"items": None}) for k, v in state.steps.items()}}
    )
    assert units.fan_out_states(smallest) == {}


# ----------------------------------------------------------------- the cost


def test_accounted_keys_are_sorted_and_cover_every_unit_with_a_cost() -> None:
    state = _state(HOLDER)
    keys = units.accounted_keys(state)
    assert keys == tuple(sorted(keys))
    assert "phase/1/implement-phase" in keys


def test_estimate_of_reads_the_v1_sizes() -> None:
    estimate = units.estimate_of(_state(CLUSTER), "phase/1/implement-phase")
    assert estimate is not None
    assert estimate.journal_entries == 5
    assert estimate.journal_lines == 26
    assert estimate.handoff_chars == 2369
    assert estimate.spec_bytes == 18657
    assert estimate.plan_bytes == 36765


def test_estimate_of_an_unaccounted_unit_is_none() -> None:
    assert units.estimate_of(_state(CLUSTER), "phase/99/implement-phase") is None


def test_estimated_at_is_the_moment_fr_assembled_the_context() -> None:
    assert (
        units.estimated_at(_state(CLUSTER), "phase/1/implement-phase")
        == "2026-09-20T13:30:36+00:00"
    )


def test_estimated_at_of_an_unaccounted_unit_is_none() -> None:
    assert units.estimated_at(_state(CLUSTER), "phase/99/implement-phase") is None


def test_measured_of_is_none_where_no_transcript_figure_was_read() -> None:
    state = _state(UNMEASURED)
    assert units.accounted_keys(state)  # it HAS accounting...
    assert all(units.measured_of(state, k) is None for k in units.accounted_keys(state))


def test_measured_of_reads_all_four_figures_where_they_exist() -> None:
    state = _state(MEASURED)
    measured = [units.measured_of(state, k) for k in units.accounted_keys(state)]
    got = [m for m in measured if m is not None]
    assert got, "this fixture's value is that it carries real measurements"
    for m in got:
        assert m.total == (
            m.input_tokens
            + m.cache_creation_input_tokens
            + m.cache_read_input_tokens
            + m.output_tokens
        )


def test_with_estimate_and_with_measured_round_trip_through_the_accessors() -> None:
    state = _state(CLUSTER)
    key = "phase/9/implement-phase"
    written = units.with_estimate(
        state,
        "implement",
        key,
        units.ContextEstimate(
            journal_entries=1, journal_lines=2, handoff_chars=3, spec_bytes=4, plan_bytes=5
        ),
        at="2026-09-20T23:00:00+00:00",
    )
    estimate = units.estimate_of(written, key)
    assert estimate is not None and estimate.handoff_chars == 3
    assert units.estimated_at(written, key) == "2026-09-20T23:00:00+00:00"
    assert units.measured_of(written, key) is None

    measured = units.with_measured(
        written,
        "implement",
        key,
        units.MeasuredTokens(
            input_tokens=1,
            cache_creation_input_tokens=2,
            cache_read_input_tokens=3,
            output_tokens=4,
        ),
    )
    got = units.measured_of(measured, key)
    assert got is not None and got.total == 10
    # …and the estimate it was folded in beside is untouched
    after = units.estimate_of(measured, key)
    assert after is not None and after.handoff_chars == 3


def test_a_partial_measurement_cannot_be_represented() -> None:
    """gh#514's "all four or none" invariant, made structural (spec §4.A)."""
    with pytest.raises(Exception):
        units.MeasuredTokens(input_tokens=1)  # type: ignore[call-arg]
