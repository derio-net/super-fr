"""Reading gate provenance off a run cursor — spec §3.D.3.

Two surfaces report the same thing: `fr run check` (informational, exit code
unchanged) and, from phase 5, fr-goal's `deliver` step, which puts the list in
the PR body under an "Operator gates" heading. They must not be able to
disagree about what counts as agent-cleared, so neither of them reads
`StepRecord.answered_by` itself — both call in here.

**What counts as a cleared gate is `answered_by`, not `gate`.** The two
branches of `fr run resolve` record differently: clearing a `cli` step's gate
writes `gate: cleared` and returns the step to `pending`, while a gated
`agent` step goes straight to `done` through `_complete_step`, which writes no
`gate` at all. `answered_by` is written on *both* paths and on no other, so it
is the one field that means "a gate was cleared here" whatever kind of step it
was — and the gated agent step is precisely the shape of the measured failure
(spec §1), so a reader keyed on `gate` would have missed it.
"""

from __future__ import annotations

from dataclasses import dataclass

from fr.run.model import AnsweredBy, RunState


@dataclass(frozen=True)
class ClearedGate:
    """One gate this run records as cleared, and who cleared it."""

    step: str
    answered_by: AnsweredBy
    at: str | None = None

    @property
    def by_agent(self) -> bool:
        return self.answered_by == "agent"


def cleared_gates(state: RunState) -> tuple[ClearedGate, ...]:
    """Every gate `state` records as cleared, in step order.

    Step order, not resolution order: `RunState.steps` is built from the
    manifest, so this reads down the run the way the operator reads it.
    """
    return tuple(
        ClearedGate(step=step_id, answered_by=record.answered_by, at=record.at)
        for step_id, record in state.steps.items()
        if record.answered_by is not None
    )


def agent_cleared_gates(state: RunState) -> tuple[ClearedGate, ...]:
    """The gates no operator answered — what both surfaces actually report."""
    return tuple(gate for gate in cleared_gates(state) if gate.by_agent)
