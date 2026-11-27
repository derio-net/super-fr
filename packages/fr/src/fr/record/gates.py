"""Gates a step record's resolve runs that `fr plan self-review` used to
(spec `2026-09-25-lean-cost-aware-process-design.md` §5.C.2.2)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fr.parser import Plan

__all__ = ["refactor_gaps"]

_TASK_ID_RE = re.compile(r"p\d+\.t\d+")
"""Task ids (`P<n>.T<m>`) inside journal justifications — matched casefolded,
so `P1.T1`, `p1.t1` and a trailing comma all resolve; uppercased at use."""


def refactor_gaps(plan: Plan, phase_n: int, also_justified: Iterable[str] = ()) -> list[str]:
    """Task ids (`P<n>.T<m>`) of phase `phase_n` that ran red → green with no
    refactor step and no recorded reason — what refuses its resolve.

    At plan time the task has not run yet, so "nothing to clean" was a guess;
    at resolve the executor knows, which is why the check moved here. Two
    exemptions kept from the old gate: manual phases (runbook work has nothing
    to extract) and single-step tasks (fr-plan writes no empty refactor step
    for a trivial task). The reason is read from the plan journal — a record's
    `refactor:` entry is journalled as `no-refactor-because <task>`, and a run
    that predates records wrote exactly that entry by hand. `also_justified`
    names tasks justified by entries not on disk yet — the record being
    applied, whose journal is still in memory.
    """
    phase = next((p for p in plan.phases if p.phase.number == phase_n), None)
    if phase is None or phase.phase.tag != "agentic":
        return []
    justified: set[str] | None = None
    gaps: list[str] = []
    for task in phase.tasks:
        if len(task.steps) < 2 or any("refactor" in s.text.casefold() for s in task.steps):
            continue
        if justified is None:
            justified = _refactor_justifications(plan) | set(also_justified)
        task_id = f"P{phase_n}.T{task.number}"
        if task_id not in justified:
            gaps.append(task_id)
    return gaps


def _refactor_justifications(plan: Plan) -> set[str]:
    """Task ids (`P<n>.T<m>`) with a recorded `no-refactor-because`
    justification: a plan-scope discovery/decision whose title or body
    carries both the marker and the id."""
    from fr.plan_review.journal import journal_entries

    root = plan.repo_root
    if root is None:
        return set()
    # Read-resolve (active else archived), like the skeleton override: a
    # justification outlives the plan it was logged against.
    entries = journal_entries(root, "plan", plan.meta.plan)
    found: set[str] = set()
    for e in entries:
        if e.kind not in ("discovery", "decision"):
            continue
        hay = f"{e.title}\n{e.body}".casefold()
        if "no-refactor-because" not in hay:
            continue
        found.update(m.group(0).upper() for m in _TASK_ID_RE.finditer(hay))
    return found
