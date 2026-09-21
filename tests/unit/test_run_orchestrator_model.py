"""fr records a model only for work it dispatched to a tier.

Found live on PR #508's Test Plan, and confirmed false in this repo's own
archive: `implemented/runs/2026-09-20-unit-record-unification-r2.yaml` records
all seven `review-phase` attempts as `model: claude-opus-5`, with no
`agent_type`, unclaimed. Every one of those reviews was done inline by an
orchestrator running a DIFFERENT model.

A tier binding answers "which model does a dispatched agent of this tier get".
An attempt with no `agent_type` is what `fr run status` calls "the
orchestrator": nothing was dispatched to a tier, the unit ran in the
orchestrator's own session, and fr cannot see what that session runs on. The
member inherits its group's `tier: from_phase`, so a model was resolved for
work that tier never touched. `harness` is different — fr detects that about
its own process, so it stays.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _GROUPED_SHAPE,
    _attempts_by_unit,
    _invoke,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_repo_models,
    _write_shape,
)


@pytest.fixture
def at_the_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """`phase/1/peer-review` briefed: a member with a `skill`-less, `agent`-less
    shape, under a group whose tier resolves to a bound model."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="hard")
    _write_repo_models(repo, "claude-code:\n  hard: claude-opus-5\n")
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    done = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]
    assert _invoke(repo, shipped, done).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _attempt(repo: Path, key: str):
    (attempt,) = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])[key]
    return attempt


def test_the_dispatched_executor_still_records_the_tiers_model(
    at_the_review: tuple[Path, Path],
) -> None:
    """The control: this is about who ran the unit, not about models at all."""
    repo, _ = at_the_review
    executor = _attempt(repo, "phase/1/code")
    assert executor.agent_type == "super-fr:fr-phase-executor"
    assert executor.model == "claude-opus-5"


def test_an_orchestrator_run_unit_records_no_model(at_the_review: tuple[Path, Path]) -> None:
    repo, _ = at_the_review
    review = _attempt(repo, "phase/1/peer-review")
    assert review.agent_type is None
    assert review.harness == "claude-code"
    assert review.model is None


def test_status_does_not_print_a_model_beside_the_orchestrator(
    at_the_review: tuple[Path, Path],
) -> None:
    repo, shipped = at_the_review
    out = _squash(_invoke(repo, shipped, ["run", "status", "r1"]).output)
    assert "the orchestrator (claude-code)" in out
    assert "the orchestrator (claude-code, claude-opus-5)" not in out


def test_a_model_the_orchestrator_reports_is_kept(at_the_review: tuple[Path, Path]) -> None:
    """Absent is not forbidden: the orchestrator knows what it runs on and may
    say so. What fr must not do is say it on the orchestrator's behalf."""
    repo, shipped = at_the_review
    args = ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1"]
    result = _invoke(repo, shipped, [*args, "--state", "done", "--model", "claude-fable-5-1"])
    assert result.exit_code == 0, result.output
    assert _attempt(repo, "phase/1/peer-review").model == "claude-fable-5-1"
