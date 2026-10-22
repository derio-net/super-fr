"""What still holds a run's `devops` gate, by recorded evidence only (spec
2026-10-22-fr-ops R14).

`fr gate pass --gate devops --run <id>` refuses while any of the run's plan ops is not
DONE/N/A by the evidence recorded in this checkout, or any Test Plan step whose
effective gate is `devops` has no `ran`/`n/a` outcome (`owed` does not close one).
Nothing here runs a probe: a pass is a statement about what was recorded, never a
fresh look at the live system.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fr.ops.testplan import steps_gated
from fr.spec import Step, StepGate

if TYPE_CHECKING:
    from fr.run.model import RunState


def _spec_file(repo_root: Path, spec_rel: str) -> Path | None:
    live = repo_root / spec_rel
    if live.is_file():
        return live
    from fr.archive import resolve_local_spec

    return resolve_local_spec(repo_root, spec_rel)


def _step_outcomes(repo_root: Path, spec: Path) -> dict[str, str]:
    """Outcome id -> the kind of its entry (`discovery` for ran and n/a, `owed`)."""
    from fr.archive import OUTCOME_PREFIX, spec_slug_of
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    journal = resolve_journal_read_path(repo_root, "spec", spec_slug_of(spec))
    if not journal.is_file():
        return {}
    try:
        entries = parse_journal(journal.read_text())
    except (JournalParseError, OSError):
        return {}
    return {e.id: e.kind for e in entries if e.resolves is None and e.id.startswith(OUTCOME_PREFIX)}


def devops_blockers(repo_root: Path, state: RunState) -> list[str]:
    """One line per thing holding `state`'s devops gate; `[]` when nothing does.
    Raises `fr.ops.load.OpsLoadError` when the plan's ops cannot be read."""
    from fr.ops.evidence import JournalEvidence, recorded_close, recorded_state
    from fr.ops.load import load_ops
    from fr.verification.exit import run_plan_dir

    out: list[str] = []
    plan_dir = run_plan_dir(repo_root, state)
    if plan_dir is not None:
        journal = JournalEvidence(repo_root, plan_dir.name)
        for lo in load_ops(plan_dir, repo_root).ops:
            if lo.runbook:  # R2: never in the R14 set
                continue
            ev = journal.latest(lo.op.id, runbook=False)
            if recorded_close(lo, ev) is None:
                out.append(f"op {lo.op.id} [{lo.op.phase}]: {recorded_state(lo, ev)}")
    for step, kind in gated_steps(repo_root, state, "devops"):
        if kind == "discovery":  # `ran` or `n/a` (R14); `owed` does not close it
            continue
        why = "recorded owed, which does not close it" if kind else "no recorded outcome"
        out.append(f"Test Plan step {step.n} (devops): {why} — {step.text}")
    return out


def gated_steps(repo_root: Path, state: RunState, gate: StepGate) -> list[tuple[Step, str | None]]:
    """The run's Test Plan steps whose effective gate is `gate`, each with the kind of its
    recorded outcome (`discovery` for ran and n/a, `owed`), or `None` when it has none."""
    from fr.archive import outcome_id
    from fr.requirements import run_spec
    from fr.spec import test_plan_steps
    from fr.verification.exit import run_exit

    spec_rel = run_spec(state)
    spec = _spec_file(repo_root, spec_rel) if spec_rel else None
    if spec is None:
        return []
    gates = run_exit(repo_root, state).gates
    outcomes = _step_outcomes(repo_root, spec)
    return [
        (step, outcomes.get(outcome_id(step.n)))
        for step in steps_gated(test_plan_steps(spec.read_text()), gates, gate)
    ]
