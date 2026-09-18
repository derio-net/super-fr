"""`fr.run.provenance.gates` — 2026-09-18 harness-parity-matrix spec §3.D.3,
Phase 5 (review r4-i2).

`cleared_gates`/`agent_cleared_gates` read `RunState` alone, so they cannot
tell "this run has no gates" apart from "this run HAS a gate whose
provenance predates `answered_by`" — both read as empty. Verified live on
this feature's own run cursor: `brainstorm` IS `gate: operator` in the
shipped manifest and WAS cleared by the operator, before the field
existed, and `cleared_gates()` returns `()` for it regardless. `gates()`
reads the MANIFEST too, so it can say so instead of rendering blank —
which on a PR body reads as "the feature never ran", this repo's
signature failure mode.
"""

from __future__ import annotations

from fr.run.model import RunState, StepRecord
from fr.run.provenance import GateStatus, gates
from fr.workflow.model import Step, WorkflowManifest


def _manifest(*steps: Step) -> WorkflowManifest:
    return WorkflowManifest(schema=1, workflow="w", unit="run", steps=steps)  # type: ignore[call-arg]


def _state(steps: dict[str, StepRecord], cursor: str = "brainstorm") -> RunState:
    return RunState(
        run="r1",
        workflow="w@1",
        branch="b",
        started="2026-09-18T00:00:00+00:00",
        cursor=cursor,
        steps=steps,
    )


_GATED_STEP = Step(id="brainstorm", kind="cli", gate="operator", run="true")  # type: ignore[call-arg]
_UNGATED_STEP = Step(id="plan", kind="cli", run="true")  # type: ignore[call-arg]


def test_a_step_the_manifest_never_gates_is_absent() -> None:
    manifest = _manifest(_UNGATED_STEP)
    state = _state({"plan": StepRecord(state="done")})
    assert gates(state, manifest) == ()


def test_a_gated_step_never_reached_is_absent() -> None:
    """No record at all for the gated step — the run has not gotten there
    yet. Not reported; `deliver` only runs once the workflow is done."""
    manifest = _manifest(_GATED_STEP)
    state = _state({})
    assert gates(state, manifest) == ()


def test_a_gated_step_cleared_with_provenance_is_recorded() -> None:
    manifest = _manifest(_GATED_STEP)
    state = _state({"brainstorm": StepRecord(state="done", gate="cleared", answered_by="operator")})
    result = gates(state, manifest)
    assert result == (GateStatus(step="brainstorm", outcome="recorded", answered_by="operator"),)


def test_a_gated_step_cleared_by_the_agent_is_recorded() -> None:
    manifest = _manifest(_GATED_STEP)
    state = _state({"brainstorm": StepRecord(state="done", gate="cleared", answered_by="agent")})
    result = gates(state, manifest)
    assert result[0].outcome == "recorded"
    assert result[0].answered_by == "agent"


def test_a_gated_cli_step_cleared_before_answered_by_existed_is_unrecorded() -> None:
    """`gate: cleared`, `answered_by: None` — the r4-i2 shape: a pre-field
    cursor whose gate genuinely fired, but whose provenance was never
    written because the field did not exist yet."""
    manifest = _manifest(_GATED_STEP)
    state = _state({"brainstorm": StepRecord(state="pending", gate="cleared", answered_by=None)})
    result = gates(state, manifest)
    assert result == (GateStatus(step="brainstorm", outcome="unrecorded", answered_by=None),)


def test_a_gated_agent_step_done_with_no_gate_field_is_unrecorded() -> None:
    """The gated AGENT branch never writes `gate: cleared` at all (it goes
    straight to `done` via `_complete_step`) — this is the shape of this
    very feature's own OpenCode run cursor, and the exact case
    `cleared_gates()` cannot distinguish from "never happened"."""
    manifest = _manifest(Step(id="brainstorm", kind="agent", gate="operator", skill="s"))  # type: ignore[call-arg]
    state = _state({"brainstorm": StepRecord(state="done", gate=None, answered_by=None)})
    result = gates(state, manifest)
    assert result == (GateStatus(step="brainstorm", outcome="unrecorded", answered_by=None),)


def test_a_gated_step_still_blocked_is_not_reported_as_cleared() -> None:
    manifest = _manifest(_GATED_STEP)
    state = _state({"brainstorm": StepRecord(state="blocked")})
    assert gates(state, manifest) == ()


def test_gates_walks_grouped_for_each_member_steps_too() -> None:
    """A `gate: operator` MEMBER step (nested under `for_each`) must not be
    invisible — `gates()` walks `Step.steps` recursively, the same shape
    `_find_step` already assumes elsewhere in this package."""
    group = Step(  # type: ignore[call-arg]
        id="implement",
        kind="agent",
        for_each="phase",
        skill="s",
        steps=(Step(id="review", kind="agent", gate="operator", skill="r"),),  # type: ignore[call-arg]
    )
    manifest = _manifest(group)
    state = _state({"review": StepRecord(state="done", answered_by="operator")})
    result = gates(state, manifest)
    assert result == (GateStatus(step="review", outcome="recorded", answered_by="operator"),)


def test_gates_preserves_manifest_step_order() -> None:
    first = Step(id="a", kind="cli", gate="operator", run="true")  # type: ignore[call-arg]
    second = Step(id="b", kind="cli", gate="operator", run="true")  # type: ignore[call-arg]
    manifest = _manifest(first, second)
    state = _state(
        {
            "b": StepRecord(state="done", gate="cleared", answered_by="agent"),
            "a": StepRecord(state="done", gate="cleared", answered_by="operator"),
        }
    )
    result = gates(state, manifest)
    assert [g.step for g in result] == ["a", "b"]
