"""Reading gate provenance off a run cursor — spec §3.D.3, widened in Phase 5
(review r4-i2) to also read the WORKFLOW MANIFEST.

Two surfaces report the same thing: `fr run check` (informational, exit code
unchanged) and, from phase 5, fr-goal's `deliver` step (`fr run gates`), which
puts the list in the PR body under an "Operator gates" heading. They must not
be able to disagree about what counts as agent-cleared, so neither of them
reads `StepRecord.answered_by` itself — both call in here.

**What counts as a cleared gate is `answered_by`, not `gate`.** The two
branches of `fr run resolve` record differently: clearing a `cli` step's gate
writes `gate: cleared` and returns the step to `pending`, while a gated
`agent` step goes straight to `done` through `_complete_step`, which writes no
`gate` at all. `answered_by` is written on *both* paths and on no other, so it
is the one field that means "a gate was cleared here" whatever kind of step it
was — and the gated agent step is precisely the shape of the measured failure
(spec §1), so a reader keyed on `gate` would have missed it.

**Why `gates()` reads the manifest too (r4-i2).** `cleared_gates`/
`agent_cleared_gates` read `RunState` alone, so they cannot tell "this run has
no gates" apart from "this run HAS a gate whose provenance predates
`answered_by`" — both read as empty. Verified live on this very feature's own
run cursor: `brainstorm` IS `gate: operator` in the shipped manifest and WAS
cleared by the operator, before the field existed, and `cleared_gates()`
returns `()` regardless. Only the manifest knows a gate was DECLARED at all,
so `gates()` takes it as a second argument and can render "provenance not
recorded" instead of nothing — nothing, on a PR body, reads as "the feature
never ran", this repo's signature failure mode. The same gap applies to a run
built by `fr run adopt`: it marks prior steps `done` with no `gate` and no
`answered_by` either, for the same underlying reason (the field did not exist
when the work happened) — `gates()` reports that run the same "unrecorded"
way, not as "no gates fired".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fr.run.model import AnsweredBy, RunState
from fr.workflow.model import Step, WorkflowManifest


@dataclass(frozen=True)
class ClearedGate:
    """One gate this run records as cleared, and who cleared it.

    `at` is the record's LAST WRITE, not the moment the gate was answered
    (review r4-m2). On the `cli` path the gate is cleared, the step returns to
    `pending`, and the next `advance` executes it — `_complete_step` then
    overwrites `at`, so what survives is the execution time. Render it as "last
    write to this record" or not at all; do not present it as when a human
    answered, which is a claim this field cannot support."""

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


GateOutcome = Literal["recorded", "unrecorded"]
"""What `gates()` knows about one manifest-declared `gate: operator` step
that this cursor shows as cleared. A step the cursor has not reached yet
(no record, or a record still `pending`/`blocked`) is left OUT of the
result entirely — `gates()` reports what happened, not what has not."""


@dataclass(frozen=True)
class GateStatus:
    """One `gate: operator` step the MANIFEST declares, and what this
    cursor's record shows about it being cleared.

    `recorded` means `answered_by` is set — the same fact `ClearedGate`
    carries. `unrecorded` means the record shows the gate WAS cleared (`cli`
    path: `gate == "cleared"`; `agent` path: `state == "done"`, since that
    branch never writes `gate` at all) but `answered_by` is `None` — a
    cursor written before the field existed, or an `fr run adopt` cursor
    that marked the step `done` with no gate history to read. Distinct from
    a step this run has not reached, which never appears here at all."""

    step: str
    outcome: GateOutcome
    answered_by: AnsweredBy | None = None
    at: str | None = None


def _gated_steps(steps: tuple[Step, ...]) -> tuple[Step, ...]:
    """The TOP-LEVEL steps declaring `gate: operator`.

    Deliberately not flattened into `for_each` members, and the docstring that
    claimed otherwise was wrong (review r5-i2). A member step never has a
    `StepRecord`: both builders key `RunState.steps` on top-level ids only
    (`run_cmd.py`'s `{s.id: StepRecord(...) for s in manifest.steps}` and the
    identical comprehension in `adopt.py`), and member progress lives in the
    group's `record.items` under `phase/<n>/<member>`. So a walk that descended
    into members could only ever look up records that do not exist — and the
    test covering it passed solely because it hand-built a member-keyed state no
    fr code path writes. A green test over an impossible state is worse than no
    test.

    Member gates are also unenforced upstream: `_advance_group` never consults
    `member.gate`, so nothing blocks on one either. Modelling them means giving
    members records and teaching `_advance_group` to honour the gate — a real
    change, not a walk. Until then this says what is true."""
    return tuple(step for step in steps if step.gate == "operator")


def gates(state: RunState, manifest: WorkflowManifest) -> tuple[GateStatus, ...]:
    """Every `gate: operator` step `manifest` declares that this cursor shows
    as cleared, in manifest step order — recorded or not (r4-i2).

    Reading the manifest is what lets this tell "no gate exists here" apart
    from "a gate existed and was cleared before `answered_by` existed": a
    step `RunState` alone cannot distinguish (`cleared_gates` above cannot
    either, for exactly that reason)."""
    statuses: list[GateStatus] = []
    for step in _gated_steps(manifest.steps):
        record = state.steps.get(step.id)
        if record is None:
            continue
        if record.answered_by is not None:
            statuses.append(
                GateStatus(
                    step=step.id, outcome="recorded", answered_by=record.answered_by, at=record.at
                )
            )
            continue
        cleared = record.gate == "cleared" or record.state == "done"
        if cleared:
            statuses.append(GateStatus(step=step.id, outcome="unrecorded", at=record.at))
    return tuple(statuses)
