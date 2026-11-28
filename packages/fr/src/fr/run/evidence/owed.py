"""Evidence debt: units resolved `done` before an obligation their step now declares (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5. A report, never a refusal: `fr run status` and
`fr run check` print it and their exit codes do not change.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from pathlib import Path

from fr.run import units
from fr.run.adopt import AdoptError
from fr.run.historical import HISTORICAL_REVIEWER
from fr.run.model import RunState, RunStateError, StepRecord
from fr.run.steps import resolve_manifest_checked_schema
from fr.workflow.model import Step, WorkflowError, WorkflowManifest


def evidence_owed(manifest: WorkflowManifest) -> dict[str, tuple[Step, ...]]:
    """`{top-level step id: (every step under it that declares evidence,)}`.

    A group's members are the realistic case (`implement`'s `review-phase`);
    a flat step declaring evidence is included so a report can never go quiet
    about a shape that asks for something it never got.
    """
    owed: dict[str, tuple[Step, ...]] = {}
    for step in manifest.steps:
        candidates = step.steps or (step,)
        declaring = tuple(s for s in candidates if s.evidence)
        if declaring:
            owed[step.id] = declaring
    return owed


def unevidenced_units(repo_root: Path, state: RunState) -> dict[tuple[str, str], tuple[str, ...]]:
    """`{(step id, unit key): obligations it lacks}` for every unit that is
    `done` under a step which declares evidence it does not carry — spec
    §4.E's visible debt. Per OBLIGATION, because a shape can grow one: a unit
    resolved with `review=` before `findings` existed owes `findings` and
    nothing else, and saying "unevidenced" of it would be as wrong as silence.

    **Never a failure, and never an exit code.** These are reviews resolved
    before the gate existed; the migration cannot invent evidence for them and
    does not try. An obligation cannot be enforced backwards in time — doing
    so would fail every in-flight run on the day the plugin updates.

    Fail-SOFT on a manifest it cannot resolve (drifted, renamed, deleted):
    this is a report line, and a report that turns `fr run check` into an
    error is a worse outcome than a report that is silent. The exit code of
    every caller is unchanged either way.
    """
    try:
        # Schema-checked only: a step-list drift does not make "which units owe
        # evidence" unanswerable, and the caller (`status`/`check`) warns about
        # the drift itself (spec 2026-10-05-run-upgrade-midflight §B).
        manifest = resolve_manifest_checked_schema(repo_root, state)
    except RunStateError, WorkflowError, AdoptError, OSError:
        return {}
    out: dict[tuple[str, str], tuple[str, ...]] = {}
    for step_id, declaring in evidence_owed(manifest).items():
        record = state.steps.get(step_id)
        if record is None:
            continue
        for member in declaring:
            suffix = f"step/{member.id}" if member.id == step_id else f"/{member.id}"
            for key in units.unit_keys(record):
                matches = key == suffix if member.id == step_id else key.endswith(suffix)
                unit_state = record.state if member.id == step_id else units.unit_state(record, key)
                if not matches or unit_state != "done":
                    continue
                held = units.evidence_of(record, key)
                if held.get("reviewer") == HISTORICAL_REVIEWER:
                    # R9: reviewed before this cursor existed — reported as
                    # such by the caller, never as debt.
                    continue
                lacking = tuple(name for name in member.evidence if name not in held)
                if lacking:
                    out[(step_id, key)] = lacking
    return out


def debt_phrase(record: StepRecord, key: str, lacking: tuple[str, ...]) -> str:
    """How one unit's evidence debt reads — ONE spelling for `status` and
    `check`. A unit with no evidence at all keeps the sentence it always had."""
    if not units.evidence_of(record, key):
        return "unevidenced (predates the evidence gate)"
    return f"unevidenced: {', '.join(lacking)} (predates that obligation)"
