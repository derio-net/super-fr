"""The v5 models, added beside the live shape and not yet wired (spec §4.A).

Phase 2 of `2026-09-20-unit-record-unification` adds `ContextEstimate`,
`MeasuredTokens`, `Attempt` and `UnitRecord` to `fr.run.model` under their
FINAL names while `RunState` still carries `items`/`dispatch`/`accounting`.
Nothing constructs them at runtime yet; phase 3 swaps them in. Pinning their
shape here is what makes that swap a swap.
"""

from __future__ import annotations

import pytest
from fr.run.model import Attempt, ContextEstimate, MeasuredTokens, RunState, StepRecord, UnitRecord
from pydantic import ValidationError

# ------------------------------------------------------------ the cost halves


def test_a_context_estimate_defaults_every_size_to_zero() -> None:
    """A size fr failed to read IS zero bytes of assembled context — the
    opposite stance from a measurement, deliberately."""
    assert ContextEstimate().handoff_chars == 0
    assert ContextEstimate(handoff_chars=7).handoff_chars == 7


def test_a_context_estimate_carries_no_timestamp() -> None:
    """`PhaseAccounting.at` does not survive: in v5 that moment is the
    attempt's own `dispatched`, recorded once instead of twice."""
    with pytest.raises(ValidationError):
        ContextEstimate(at="2026-09-20T00:00:00Z")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "omitted",
    ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"],
)
def test_a_partial_measurement_is_unrepresentable(omitted: str) -> None:
    """gh#514's "all four or none", made STRUCTURAL. `PhaseAccounting` could
    only state it in prose plus a validator, so the unrepresentable state was
    representable everywhere except at the one place that looked."""
    fields = dict.fromkeys(
        (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        ),
        1,
    )
    del fields[omitted]
    with pytest.raises(ValidationError) as excinfo:
        MeasuredTokens(**fields)  # type: ignore[arg-type]
    assert omitted in str(excinfo.value)


def test_a_measured_zero_is_a_real_measurement() -> None:
    """Zero is a figure somebody read; `None` — i.e. no `MeasuredTokens` at
    all — is the absence. The two must never render the same way."""
    nothing_spent = MeasuredTokens(
        input_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        output_tokens=0,
    )
    assert nothing_spent.total == 0


def test_measured_total_sums_the_four() -> None:
    assert (
        MeasuredTokens(
            input_tokens=1,
            cache_creation_input_tokens=2,
            cache_read_input_tokens=4,
            output_tokens=8,
        ).total
        == 15
    )


# ----------------------------------------------------------------- the attempt


def test_an_attempt_needs_only_the_one_fact_fr_always_knows() -> None:
    attempt = Attempt(dispatched="2026-09-20T09:00:00Z")
    assert attempt.agent is None
    assert attempt.session is None
    assert attempt.estimate is None
    assert attempt.measured is None
    assert attempt.returned is None


def test_an_attempt_has_no_dispatched_default() -> None:
    with pytest.raises(ValidationError):
        Attempt()  # type: ignore[call-arg]


def test_returned_and_outcome_are_still_one_fact() -> None:
    """`DispatchRecord`'s invariant, kept verbatim: a half-closed record reads
    as still-held or held-forever depending on which half you look at."""
    with pytest.raises(ValidationError):
        Attempt(dispatched="2026-09-20T09:00:00Z", returned="2026-09-20T09:30:00Z")
    with pytest.raises(ValidationError):
        Attempt(dispatched="2026-09-20T09:00:00Z", outcome="done")
    closed = Attempt(
        dispatched="2026-09-20T09:00:00Z", returned="2026-09-20T09:30:00Z", outcome="done"
    )
    assert closed.outcome == "done"


def test_an_attempt_still_refuses_an_unknown_harness() -> None:
    with pytest.raises(ValidationError):
        Attempt(dispatched="2026-09-20T09:00:00Z", harness="unknown")


def test_an_attempt_carries_its_own_cost() -> None:
    """Per ATTEMPT, not per unit — which is the u2 repair: the old top-level
    map held one snapshot per unit, so a redispatch overwrote the abandoned
    agent's spend, exactly the spend worth seeing."""
    attempt = Attempt(
        dispatched="2026-09-20T09:00:00Z",
        session="sess-1",
        estimate=ContextEstimate(handoff_chars=100),
        measured=MeasuredTokens(
            input_tokens=1,
            cache_creation_input_tokens=1,
            cache_read_input_tokens=1,
            output_tokens=1,
        ),
    )
    assert attempt.estimate is not None and attempt.estimate.handoff_chars == 100
    assert attempt.measured is not None and attempt.measured.total == 4
    assert attempt.session == "sess-1"


def test_an_attempt_is_frozen_and_closed_world() -> None:
    with pytest.raises(ValidationError):
        Attempt(dispatched="2026-09-20T09:00:00Z", bogus="x")  # type: ignore[call-arg]
    attempt = Attempt(dispatched="2026-09-20T09:00:00Z")
    with pytest.raises(ValidationError):
        attempt.agent = "late"  # type: ignore[misc]


# ------------------------------------------------------------- the unit record


def test_a_unit_record_defaults_to_nothing_recorded() -> None:
    unit = UnitRecord()
    assert unit.state is None
    assert unit.attempts == ()
    assert unit.evidence is None


def test_a_flat_units_state_is_none_and_that_is_legal() -> None:
    """§4.B: a `step/<step-id>` unit carries no state, because
    `StepRecord.state` is that fact's one home."""
    assert UnitRecord(attempts=(Attempt(dispatched="2026-09-20T09:00:00Z"),)).state is None


def test_manual_is_a_unit_state() -> None:
    """gh#496's marker is a state a unit can be IN, not an outcome."""
    assert UnitRecord(state="manual").state == "manual"


def test_a_unit_record_refuses_a_state_no_unit_can_be_in() -> None:
    with pytest.raises(ValidationError):
        UnitRecord(state="blocked")  # type: ignore[arg-type]  # a gate blocks a STEP


def test_evidence_maps_an_obligation_to_a_journal_entry_id() -> None:
    assert UnitRecord(state="done", evidence={"review": "rev-p2"}).evidence == {"review": "rev-p2"}


# ---------------------------------------------------------- and now it is wired


def test_run_state_carries_one_unit_map_and_none_of_the_three_it_replaced() -> None:
    """Phase 3, the flip. `units` is the cursor's ONE per-unit map; `items`,
    `dispatch` and the top-level `accounting` are gone from the live model and
    live on only in the frozen `fr.run.legacy`."""
    assert "units" in StepRecord.model_fields
    assert "items" not in StepRecord.model_fields
    assert "dispatch" not in StepRecord.model_fields
    assert "accounting" not in RunState.model_fields


def test_the_storage_models_the_flip_retired_are_gone_from_the_live_module() -> None:
    import fr.run.model as live

    assert not hasattr(live, "DispatchRecord")
    assert not hasattr(live, "PhaseAccounting")
