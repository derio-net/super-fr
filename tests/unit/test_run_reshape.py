"""`fr.run.reshape` — a drifted cursor is rewritten onto the current step list
(spec 2026-10-05-run-upgrade-midflight §A, rules 1-5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import RunState, StepRecord, UnitRecord
from fr.run.reshape import ReshapeError, reshape
from fr.workflow.model import WorkflowManifest
from fr.workflow.resolve import resolve_workflow

REPO = Path(__file__).resolve().parents[2]


def _manifest() -> WorkflowManifest:
    return resolve_workflow("fr-goal", REPO)


def _state(manifest: WorkflowManifest, cursor: str = "implement") -> RunState:
    return RunState(
        run="2026-10-05-feat-x",
        workflow=f"fr-goal@{manifest.schema_version}",
        branch="feat/x",
        started="2026-10-05T10:00:00+00:00",
        cursor=cursor,
        steps={
            s.id: StepRecord(state="pending", members=[m.id for m in s.steps] or None)
            for s in manifest.steps
        },
    )


def test_a_run_with_no_drift_reshapes_to_itself() -> None:
    manifest = _manifest()
    state = _state(manifest)
    assert reshape(state, manifest) == state


# --- the rules --------------------------------------------------------------


def _without(state: RunState, step_id: str) -> RunState:
    return state.model_copy(
        update={"steps": {k: v for k, v in state.steps.items() if k != step_id}}
    )


def _drop_step(manifest: WorkflowManifest, step_id: str) -> WorkflowManifest:
    return manifest.model_copy(
        update={"steps": tuple(s for s in manifest.steps if s.id != step_id)}
    )


def _set(state: RunState, step_id: str, **kw: object) -> RunState:
    steps = dict(state.steps)
    steps[step_id] = steps[step_id].model_copy(update=kw)
    return state.model_copy(update={"steps": steps})


def _unit() -> dict[str, UnitRecord]:
    return {"phase/1/implement-phase": UnitRecord(state="done")}


def test_a_step_added_after_the_cursor_is_inserted_pending_in_manifest_order() -> None:
    manifest = _manifest()
    full = _state(manifest)
    state = _without(full, "journal-check")
    out = reshape(state, manifest)
    assert list(out.steps) == [s.id for s in manifest.steps]
    assert out.steps["journal-check"] == StepRecord(state="pending")
    for sid, rec in state.steps.items():
        assert out.steps[sid] == rec


def test_a_step_added_at_or_behind_the_cursor_refuses() -> None:
    manifest = _manifest()
    state = _without(_state(manifest, cursor="implement"), "spec-review")
    with pytest.raises(ReshapeError, match=r"spec-review.*fr run adopt --supersede"):
        reshape(state, manifest)
    at = _without(_state(manifest, cursor="journal-check"), "journal-check")
    with pytest.raises(ReshapeError, match=r"journal-check.*--supersede"):
        reshape(at, manifest)


def test_a_removed_step_that_holds_nothing_is_dropped() -> None:
    manifest = _manifest()
    state = _state(manifest)
    out = reshape(state, _drop_step(manifest, "plan-review"))
    assert "plan-review" not in out.steps
    assert list(out.steps) == [s.id for s in manifest.steps if s.id != "plan-review"]


@pytest.mark.parametrize(
    "held",
    [
        {"units": {"step/plan-review": UnitRecord()}},
        {"gate": "cleared"},
        {"answered_by": "operator"},
        {"emitted": {"plan": "x"}},
    ],
    ids=["unit", "gate", "answered_by", "emitted"],
)
def test_a_removed_step_that_holds_something_refuses(held: dict[str, object]) -> None:
    manifest = _manifest()
    state = _set(_state(manifest), "plan-review", **held)
    with pytest.raises(ReshapeError, match="plan-review"):
        reshape(state, _drop_step(manifest, "plan-review"))


def test_a_removed_step_that_is_the_cursor_refuses() -> None:
    manifest = _manifest()
    state = _state(manifest, cursor="plan-review")
    with pytest.raises(ReshapeError, match="plan-review"):
        reshape(state, _drop_step(manifest, "plan-review"))


def _with_members(manifest: WorkflowManifest, members: tuple[str, ...]) -> WorkflowManifest:
    steps = []
    for s in manifest.steps:
        if s.id == "implement":
            s = s.model_copy(update={"steps": tuple(m for m in s.steps if m.id in members)})
        steps.append(s)
    return manifest.model_copy(update={"steps": tuple(steps)})


def test_a_group_whose_members_changed_is_rewritten_when_it_holds_no_units() -> None:
    manifest = _manifest()
    state = _state(manifest)
    out = reshape(state, _with_members(manifest, ("implement-phase",)))
    assert out.steps["implement"].members == ["implement-phase"]


def test_a_group_whose_members_changed_refuses_when_it_holds_units() -> None:
    manifest = _manifest()
    state = _set(_state(manifest), "implement", units=_unit())
    with pytest.raises(ReshapeError, match="implement"):
        reshape(state, _with_members(manifest, ("implement-phase",)))


def test_a_schema_mismatch_refuses() -> None:
    manifest = _manifest()
    state = _state(manifest).model_copy(update={"workflow": "fr-goal@2"})
    assert str(manifest.schema_version) != "2"
    with pytest.raises(ReshapeError, match=r"schema.*fr run adopt <plan-dir> --supersede"):
        reshape(state, manifest)


def test_started_and_driver_are_kept() -> None:
    manifest = _manifest()
    state = _without(_state(manifest), "journal-check").model_copy(update={"driver": "standalone"})
    out = reshape(state, manifest)
    assert out.started == state.started
    assert out.driver == "standalone"
    assert out.cursor == state.cursor
