"""What still holds a run's post-merge gate, by recorded evidence only (spec
2026-10-22-fr-ops R14; for both gates and their rows, spec 2026-11-27-ops-gate-truth R10).

`fr gate pass --gate devops --run <id>` refuses while any of the run's plan ops is not
DONE/N/A by the evidence recorded in this checkout, or any Test Plan step whose
effective gate is `devops` has no `ran`/`n/a` outcome (`owed` does not close one).
Nothing here runs a probe: a pass is a statement about what was recorded, never a
fresh look at the live system.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.acceptance.model import Row, Walk
from fr.acceptance.walks import row_walked
from fr.artifacts.paths import emitted_path
from fr.journal.model import JournalEntry
from fr.ops.testplan import steps_gated
from fr.spec import Step, StepGate

if TYPE_CHECKING:
    from fr.run.model import RunState
    from fr.verification.exit import Exit


def _spec_file(repo_root: Path, spec_rel: str) -> Path | None:
    live = emitted_path(repo_root, spec_rel)
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
    return {n: kind for n, (kind, _) in _fold_outcomes(entries, exclude).items()}


def _fold_outcomes(
    entries: Iterable[JournalEntry], exclude: Set[str]
) -> dict[int, tuple[str, str]]:
    """`fold_step_outcomes`, each with what it says: `ran`, `na` or `owed` (an owed entry
    resolved `fixed` was discharged with evidence, so it reads `ran`)."""
    latest: dict[int, tuple[str, str, str]] = {}
    for e in entries:
        if e.id in exclude:
            continue
        if e.resolves is not None:
            m = _OUTCOME_ID.match(e.resolves)
            if m and e.state == "fixed":
                n = int(m.group(1))
                if latest.get(n, ("", "", ""))[0] == e.resolves:
                    latest[n] = (e.resolves, "discovery", "ran")
            continue
        m = _OUTCOME_ID.match(e.id)
        if m:
            said = "owed" if e.kind == "owed" else "na" if e.title.endswith(": n/a") else "ran"
            latest[int(m.group(1))] = (e.id, e.kind, said)
    return {n: (kind, said) for n, (_, kind, said) in latest.items()}


def _journal_entries(repo_root: Path, spec: Path) -> list[JournalEntry]:
    from fr.archive import spec_slug_of
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    journal = resolve_journal_read_path(repo_root, "spec", spec_slug_of(spec))
    if not journal.is_file():
        return []
    try:
        return parse_journal(journal.read_text())
    except JournalParseError, OSError:
        return []


def ran_steps(
    repo_root: Path, state: RunState, gate: StepGate, *, exclude: Set[str] = frozenset()
) -> list[Step]:
    """The run's Test Plan steps of effective gate *gate* whose effective outcome is
    `ran` (not `n/a`, not `owed`); *exclude* as `gated_steps` (ops-gate-truth R13)."""
    from fr.requirements import run_spec
    from fr.spec import test_plan_steps
    from fr.verification.exit import run_exit

    spec_rel = run_spec(state)
    spec = _spec_file(repo_root, spec_rel) if spec_rel else None
    if spec is None:
        return []
    said = _fold_outcomes(_journal_entries(repo_root, spec), exclude)
    steps = test_plan_steps(spec.read_text(), source=spec_rel)
    gated = steps_gated(steps, run_exit(repo_root, state).gates, gate)
    return [s for s in gated if said.get(s.n, ("", ""))[1] == "ran"]


def _step_outcomes(repo_root: Path, spec: Path, exclude: Set[str] = frozenset()) -> dict[int, str]:
    """Step number -> the kind of its effective outcome (`fold_step_outcomes`)."""
    return fold_step_outcomes(_journal_entries(repo_root, spec), exclude=exclude)


@dataclass(frozen=True)
class GateItem:
    """One thing a post-merge gate owns (spec 2026-11-27-ops-gate-truth R10): what it is,
    whether recorded evidence discharges it, and a one-line reason."""

    what: str
    discharged: bool
    why: str

    @property
    def line(self) -> str:
        return f"{self.what}: {self.why}"


def _row_reason(row: Row, walks: list[Walk]) -> str:
    """Why *row* is (or is not) walked, judged over *walks* (R10)."""
    if row_walked(row, exclude=set(row.walks) - set(walks)):
        return "walked"
    if not walks:
        return f"no walk (status {row.status})"
    latest = max(walks, key=lambda w: w.at)
    if latest.outcome != "pass":
        return f"its latest walk failed ({latest.harness}, {latest.at})"
    passing = {w.harness for w in walks if w.outcome == "pass"}
    owed = [h for h in row.harnesses if h not in passing]
    if owed:
        return f"walk still owed on {', '.join(owed)} (status {row.status})"
    return f"status {row.status}, not walked"


def gate_items(
    repo_root: Path,
    state: RunState,
    gate: StepGate,
    *,
    exclude_walks: Mapping[str, Collection[Walk]] | None = None,
    exclude_outcomes: Set[str] = frozenset(),
) -> list[GateItem]:
    """Every thing `state`'s *gate* owns, discharged or not (R10): each plan op (devops
    only), each Test Plan step whose effective gate is *gate*, and each row whose
    effective gate is *gate* (none under `acceptance: off`). A walk in
    `exclude_walks[row]` and an outcome entry id in *exclude_outcomes* do not count (the
    DevOps stage passes the ones the pinned PR head carries, R12). Raises
    `fr.ops.load.OpsLoadError` when the plan's ops cannot be read."""
    from fr.ops.evidence import JournalEvidence, recorded_close, recorded_state
    from fr.ops.load import load_ops
    from fr.verification.exit import run_exit, run_plan_dir

    out: list[GateItem] = []
    plan_dir = run_plan_dir(repo_root, state) if gate == "devops" else None
    if plan_dir is not None:
        journal = JournalEvidence(repo_root, plan_dir.name)
        for lo in load_ops(plan_dir, repo_root).ops:
            if lo.runbook:  # fr-ops R2: never in the R14 set
                continue
            ev = journal.latest(lo.op.id, runbook=False)
            closed = recorded_close(lo, ev) is not None
            out.append(GateItem(f"op {lo.op.id} [{lo.op.phase}]", closed, recorded_state(lo, ev)))
    exit_ = run_exit(repo_root, state)
    for step, kind in _gated_steps(repo_root, state, gate, exit_.gates, exclude_outcomes):
        if kind == "discovery":  # `ran` or `n/a` (fr-ops R14); `owed` does not close it
            why = "recorded ran or n/a"
        else:
            why = "recorded owed, which does not close it" if kind else "no recorded outcome"
        out.append(
            GateItem(
                f"Test Plan step {step.n} ({gate})", kind == "discovery", f"{why} — {step.text}"
            )  # fmt: skip
        )
    excluded = exclude_walks or {}
    for row, _ in gated_rows(repo_root, exit_, gate):
        skip = set(excluded.get(row.id, ()))
        walks = [w for w in row.walks if w not in skip]
        why = _row_reason(row, walks)
        out.append(GateItem(f"row {row.id} ({gate})", why == "walked", why))
    return out


def gated_rows(repo_root: Path, exit_: Exit, gate: StepGate) -> list[tuple[Row, str]]:
    """The rows of *exit_* whose effective gate is *gate*, each with its effective
    strategy; none under `acceptance: off` (ops-gate-truth R8)."""
    from fr.settings import disabled

    if disabled(repo_root, "acceptance"):
        return []
    return [(r, exit_.row_kinds[r.id]) for r in exit_.gated_rows if exit_.row_gates[r.id] == gate]


def gate_blockers(
    repo_root: Path,
    state: RunState,
    gate: StepGate,
    *,
    exclude_walks: Mapping[str, Collection[Walk]] | None = None,
    exclude_outcomes: Set[str] = frozenset(),
) -> list[str]:
    """One line per item of `gate_items` still owed; `[]` when nothing holds the gate."""
    items = gate_items(
        repo_root, state, gate, exclude_walks=exclude_walks, exclude_outcomes=exclude_outcomes
    )
    return [i.line for i in items if not i.discharged]


def devops_blockers(repo_root: Path, state: RunState) -> list[str]:
    """One line per thing holding `state`'s devops gate; `[]` when nothing does
    (`gate_blockers(..., "devops")`). Raises `fr.ops.load.OpsLoadError` when the plan's
    ops cannot be read."""
    return gate_blockers(repo_root, state, "devops")


def gated_steps(
    repo_root: Path, state: RunState, gate: StepGate, *, exclude: Set[str] = frozenset()
) -> list[tuple[Step, str | None]]:
    """The run's Test Plan steps whose effective gate is `gate`, each with the kind of its
    effective outcome (`discovery` for ran and n/a, `owed`), or `None` when it has none.
    *exclude*: outcome entry ids not to count (the DevOps stage's PR-carried ones)."""
    from fr.verification.exit import run_exit

    return _gated_steps(repo_root, state, gate, run_exit(repo_root, state).gates, exclude)


def _gated_steps(
    repo_root: Path, state: RunState, gate: StepGate, gates: Set[str], exclude: Set[str]
) -> list[tuple[Step, str | None]]:
    from fr.requirements import run_spec
    from fr.spec import test_plan_steps

    spec_rel = run_spec(state)
    spec = _spec_file(repo_root, spec_rel) if spec_rel else None
    if spec is None:
        return []
    outcomes = _step_outcomes(repo_root, spec, exclude)
    return [
        (step, outcomes.get(step.n))
        for step in steps_gated(test_plan_steps(spec.read_text(), source=spec_rel), gates, gate)
    ]
