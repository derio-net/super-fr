"""`render.archive_gate` requires landed evidence (#544).

Spec `2026-09-23-archive-merge-evidence-design.md` §3.C, Test Plan §5 item 5.
`landed` is the set of phase numbers locally complete on the default branch's
remote-tracking ref (`None` = merge state unknown). It is a required keyword
with no default, so no caller can skip the question. Pure-function tests: no
git, no network.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Literal

import pytest
from fr import parse
from fr.render import archive_gate
from fr.states import GhState, PhaseObservation, PrObservation
from fr.types import (
    Completion,
    PhaseDoc,
    PhaseHeader,
    PhaseStateBlock,
    Step,
    StepState,
    Task,
)

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _phase(
    number: int,
    *,
    tag: Literal["agentic", "manual"] = "agentic",
    ticked: bool = True,
    tracking: str | None = None,
    completion_at: str | None = None,
    completion_note: str | None = None,
) -> PhaseDoc:
    step = Step(id=f"P{number}.T1.S1", text="step")
    return PhaseDoc(
        schema_version=2,
        phase=PhaseHeader(number=number, title=f"Phase {number}", tag=tag, tracking_issue=tracking),
        tasks=(Task(number=1, title="t", steps=(step,)),),
        state=PhaseStateBlock(
            steps={step.id: StepState(state="x" if ticked else " ")},
            completion=Completion(at=completion_at, note=completion_note),
        ),
    )


def _plan(*phases: PhaseDoc):
    return dc_replace(parse(FIXTURE), phases=phases)


def _merged_pr_obs() -> PhaseObservation:
    pr = PrObservation(url="u", state="CLOSED", merged=True, draft=False, ci="PASS")
    return PhaseObservation(
        issue_state="CLOSED", issue_labels=frozenset(), issue_assignees=(), linked_prs=(pr,)
    )


def test_landed_is_a_required_keyword() -> None:
    plan = _plan(_phase(1))
    with pytest.raises(TypeError):
        archive_gate(plan, GhState())  # type: ignore[call-arg]


def test_landed_cannot_be_passed_positionally() -> None:
    plan = _plan(_phase(1))
    with pytest.raises(TypeError):
        archive_gate(plan, GhState(), frozenset({1}))  # type: ignore[misc]


def test_a_locally_complete_undispatched_agentic_phase_not_on_the_ref_is_blocked() -> None:
    plan = _plan(_phase(1))
    blockers = archive_gate(plan, GhState(), landed=frozenset(), ref="origin/main")
    assert len(blockers) == 1
    assert blockers[0] == "Phase 1: complete locally, not on origin/main; merge the PR first"


def test_a_phase_that_exists_only_locally_is_blocked_while_its_landed_sibling_passes() -> None:
    """The f-p2-local-phases case: phase 1 merged, phase 2 added and ticked
    on the branch afterwards. `landed` is per phase, so phase 2 is absent."""
    plan = _plan(_phase(1), _phase(2))
    blockers = archive_gate(plan, GhState(), landed=frozenset({1}), ref="origin/main")
    assert blockers == ("Phase 2: complete locally, not on origin/main; merge the PR first",)


def test_unknown_merge_state_blocks_naming_the_reason_and_force() -> None:
    plan = _plan(_phase(1))
    blockers = archive_gate(plan, GhState(), landed=None, unknown_reason="no git remote")
    assert len(blockers) == 1
    assert "Phase 1" in blockers[0]
    assert "merge state unknown (no git remote)" in blockers[0]
    assert "add a remote or use --force" in blockers[0]


def test_a_landed_phase_passes() -> None:
    plan = _plan(_phase(1), _phase(2))
    assert archive_gate(plan, GhState(), landed=frozenset({1, 2})) == ()


def test_an_incomplete_undispatched_agentic_phase_keeps_the_tick_count_wording() -> None:
    plan = _plan(_phase(1, ticked=False))
    blockers = archive_gate(plan, GhState(), landed=frozenset({1}))
    assert len(blockers) == 1
    assert "0/1 steps ticked, undispatched — not complete" in blockers[0]


def test_a_manual_phase_is_judged_locally_only() -> None:
    """fr-goal's trailing manual phase is ticked after merge: locally complete
    is enough, whatever the ref says (spec §3.A)."""
    plan = _plan(_phase(1), _phase(2, tag="manual"))
    assert archive_gate(plan, GhState(), landed=frozenset({1})) == ()
    manual_only = _plan(_phase(1, tag="manual"))
    assert archive_gate(manual_only, GhState(), landed=None) == ()
    assert archive_gate(manual_only, GhState(), landed=frozenset()) == ()


def test_an_open_manual_phase_still_blocks() -> None:
    plan = _plan(_phase(1), _phase(2, tag="manual", ticked=False))
    blockers = archive_gate(plan, GhState(), landed=frozenset({1}))
    assert len(blockers) == 1
    assert blockers[0].startswith("Phase 2:")


def test_the_dispatched_arm_is_unchanged() -> None:
    """A dispatched phase is judged by gh (merged PR), never by `landed`."""
    done = _phase(1, tracking="https://github.com/o/r/issues/1", completion_at="2026-01-01")
    observed = GhState(phases={1: _merged_pr_obs()})
    assert archive_gate(_plan(done), observed, landed=frozenset()) == ()
    assert archive_gate(_plan(done), observed, landed=None) == ()

    not_done = _phase(1, tracking="https://github.com/o/r/issues/1")
    blockers = archive_gate(_plan(not_done), GhState(), landed=frozenset({1}))
    assert len(blockers) == 1
    assert "dispatched — not complete" in blockers[0]
