"""`fr.run.reshape` — a drifted cursor is rewritten onto the current step list
(spec 2026-10-05-run-upgrade-midflight §A, rules 1-5)."""

from __future__ import annotations

from pathlib import Path

from fr.run.model import RunState, StepRecord
from fr.run.reshape import reshape
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
