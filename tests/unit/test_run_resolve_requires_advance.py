"""A grouped unit cannot be resolved before `fr run advance` briefed it.

Found live, driving PR #508's post-merge Test Plan on Claude Code: `review-phase`
was resolved `done` with no `advance` in between, and fr accepted it — a `done`
unit with evidence and NO attempt, so no holder and no cost for the review. The
OpenCode run, which advanced first, has one.

`_resolve_member` guarded the GROUP's state and refused while any OTHER unit
was running, but had no precondition on the unit it was resolving. The flat
step path always had one ("not running or blocked … advance first"); this file
holds the grouped path to the same rule. `_close_on_resolve` stays silent when
nothing is open — adopted cursors depend on that — so the check has to sit
before the write, which is where the flat path keeps its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _invoke,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import _shape


def _code_done_review_never_advanced(tmp_path: Path) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _shape(evidence=False))
    _started_grouped_with_plan(repo, shipped)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    done = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]
    assert _invoke(repo, shipped, done).exit_code == 0
    return repo, shipped


def _resolve_review(repo: Path, shipped: Path, state: str):
    args = ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1", "--state", state]
    return _invoke(repo, shipped, args)


@pytest.mark.parametrize("state", ["done", "failed"])
def test_a_unit_that_was_never_advanced_cannot_be_resolved(tmp_path: Path, state: str) -> None:
    repo, shipped = _code_done_review_never_advanced(tmp_path)

    result = _resolve_review(repo, shipped, state)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "phase/1/peer-review" in out
    assert "fr run advance r1" in out
    # `advance` briefs the NEXT unit in order, which need not be the one named:
    # promising it "opens this unit" sends someone resolving phase 2 early to a
    # brief for phase 1 with no warning.
    assert "next unit in order" in out
    after = load_run_state(repo, "r1")
    assert after.steps["implement"].state == "running"
    assert units.unit_state(after.steps["implement"], "phase/1/peer-review") != state
    assert after.cursor == "implement"


def test_once_advanced_it_resolves_and_the_attempt_is_there(tmp_path: Path) -> None:
    """The control: the refusal is about the missing `advance`, nothing else."""
    repo, shipped = _code_done_review_never_advanced(tmp_path)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    result = _resolve_review(repo, shipped, "done")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["implement"]
    assert units.unit_state(record, "phase/1/peer-review") == "done"
    (attempt,) = units.attempts(record, "phase/1/peer-review")
    assert attempt.returned is not None
    assert attempt.outcome == "done"


SKILLS = [
    Path(__file__).resolve().parents[2] / "plugins/super-fr/skills/fr-goal/SKILL.md",
    Path(__file__).resolve().parents[2] / ".opencode/skills/fr-goal/SKILL.md",
    Path(__file__).resolve().parents[2] / ".hermes/skills/fr/fr-goal/SKILL.md",
]


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parts[-4])
def test_the_skill_describes_the_sequence_fr_now_enforces(path: Path) -> None:
    """The defect was produced by following the skill: its loop went straight
    from the executor's return to resolving the review, with no `advance` to
    brief `review-phase` in between. Refusing the shortcut while the prose still
    describes it would make every phase trip the refusal once."""
    text = " ".join(path.read_text().split())
    assert "`fr run advance <run-id>` again to brief `review-phase`" in text


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parts[-4])
def test_the_skill_asks_the_orchestrator_to_say_what_it_ran_on(path: Path) -> None:
    """fr no longer guesses a model for work the orchestrator did itself (C2),
    so unless the skill asks for it the field is simply never filled."""
    text = " ".join(path.read_text().split())
    # The record form (spec 2026-09-25 §5.C): the review-phase record's evidence.
    assert "model: <the model you are running on>" in text
