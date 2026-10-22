"""What still holds a run's `devops` gate, by recorded evidence only (spec
2026-10-22-fr-ops R14).

`fr gate pass --gate devops --run <id>` refuses while any of the run's plan ops is not
DONE/N/A by the evidence recorded in this checkout, or any Test Plan step whose
effective gate is `devops` has no recorded outcome. Nothing here runs a probe: a pass
is a statement about what was recorded, never a fresh look at the live system.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fr.run.model import RunState


def _spec_file(repo_root: Path, spec_rel: str) -> Path | None:
    live = repo_root / spec_rel
    if live.is_file():
        return live
    from fr.archive import resolve_local_spec

    return resolve_local_spec(repo_root, spec_rel)


def devops_blockers(repo_root: Path, state: RunState) -> list[str]:
    """One line per thing holding `state`'s devops gate; `[]` when nothing does.
    Raises `fr.ops.load.OpsLoadError` when the plan's ops cannot be read."""
    from fr.archive import missing_outcomes
    from fr.ops.evidence import JournalEvidence, recorded_close, recorded_state
    from fr.ops.load import load_ops
    from fr.ops.testplan import steps_gated
    from fr.requirements import run_spec
    from fr.verification.exit import run_exit, run_plan_dir

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
    spec_rel = run_spec(state)
    spec = _spec_file(repo_root, spec_rel) if spec_rel else None
    if spec is not None:
        gates = run_exit(repo_root, state).gates
        missing = missing_outcomes(repo_root, spec)
        for step in steps_gated(missing, gates, "devops"):
            out.append(f"Test Plan step {step.n} (devops): no recorded outcome — {step.text}")
    return out
