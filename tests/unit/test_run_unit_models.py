"""The v5 models, added beside the live shape and not yet wired (spec §4.A).

Phase 2 of `2026-09-20-unit-record-unification` adds `Attempt` and
`UnitRecord` (and, until run 7, the two cost halves) to `fr.run.model` under their
FINAL names while `RunState` still carries `items`/`dispatch`/`accounting`.
Nothing constructs them at runtime yet; phase 3 swaps them in. Pinning their
shape here is what makes that swap a swap.
"""

from __future__ import annotations

import pytest
from fr.run.model import Attempt, RunState, StepRecord, UnitRecord
from pydantic import ValidationError

# ----------------------------------------------------------------- the attempt


def test_an_attempt_needs_only_the_one_fact_fr_always_knows() -> None:
    attempt = Attempt(dispatched="2026-09-20T09:00:00Z")
    assert attempt.agent is None
    assert attempt.session is None
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


def test_an_attempt_carries_no_cost_since_run_7() -> None:
    """Run 7 moved `estimate` and `measured` into the run's usage file (spec
    2026-09-25-lean-cost-aware-process §5.B.4); the live model refuses them."""
    for gone in ("estimate", "measured"):
        with pytest.raises(ValidationError):
            Attempt.model_validate({"dispatched": "2026-09-20T09:00:00Z", gone: {}})


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
