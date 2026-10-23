"""What still holds a run's `devops` gate, by recorded evidence only (spec
2026-10-22-fr-ops R14).

`fr gate pass --gate devops --run <id>` refuses while any of the run's plan ops is not
DONE/N/A by the evidence recorded in this checkout, or any Test Plan step whose
effective gate is `devops` has no `ran`/`n/a` outcome (`owed` does not close one).
Nothing here runs a probe: a pass is a statement about what was recorded, never a
fresh look at the live system.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Set
from pathlib import Path
from typing import TYPE_CHECKING

from fr.journal.model import JournalEntry
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


_OUTCOME_ID = re.compile(r"^test-plan-step-(\d+)(?:-\d+)?$")


def fold_step_outcomes(
    entries: Iterable[JournalEntry], *, exclude: Set[str] = frozenset()
) -> dict[int, str]:
    """Step number -> the kind of its EFFECTIVE outcome (spec 2026-10-22-fr-ops R15,
    p4-r3): the latest outcome entry for the step wins (`test-plan-step-<n>`, or a later
    `test-plan-step-<n>-<k>` that `fr closeout outcome` writes over an owed one), and an
    owed entry a later record resolves `fixed` reads closed (`discovery`). Entries whose
    id is in *exclude* (those the PR head carries, inside the DevOps stage) are skipped."""
    latest: dict[int, tuple[str, str]] = {}
    for e in entries:
        if e.id in exclude:
            continue
        if e.resolves is not None:
            m = _OUTCOME_ID.match(e.resolves)
            if m and e.state == "fixed":
                n = int(m.group(1))
                if latest.get(n, ("", ""))[0] == e.resolves:
                    latest[n] = (e.resolves, "discovery")
            continue
        m = _OUTCOME_ID.match(e.id)
        if m:
            latest[int(m.group(1))] = (e.id, e.kind)
    return {n: kind for n, (_, kind) in latest.items()}


def _step_outcomes(repo_root: Path, spec: Path, exclude: Set[str] = frozenset()) -> dict[int, str]:
    """Step number -> the kind of its effective outcome (`fold_step_outcomes`)."""
    from fr.archive import spec_slug_of
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    journal = resolve_journal_read_path(repo_root, "spec", spec_slug_of(spec))
    if not journal.is_file():
        return {}
    try:
        entries = parse_journal(journal.read_text())
    except (JournalParseError, OSError):
        return {}
    return fold_step_outcomes(entries, exclude=exclude)


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


def gated_steps(
    repo_root: Path, state: RunState, gate: StepGate, *, exclude: Set[str] = frozenset()
) -> list[tuple[Step, str | None]]:
    """The run's Test Plan steps whose effective gate is `gate`, each with the kind of its
    effective outcome (`discovery` for ran and n/a, `owed`), or `None` when it has none.
    *exclude*: outcome entry ids not to count (the DevOps stage's PR-carried ones)."""
    from fr.requirements import run_spec
    from fr.spec import test_plan_steps
    from fr.verification.exit import run_exit

    spec_rel = run_spec(state)
    spec = _spec_file(repo_root, spec_rel) if spec_rel else None
    if spec is None:
        return []
    gates = run_exit(repo_root, state).gates
    outcomes = _step_outcomes(repo_root, spec, exclude)
    return [
        (step, outcomes.get(step.n))
        for step in steps_gated(test_plan_steps(spec.read_text()), gates, gate)
    ]
