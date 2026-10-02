"""A dispatched attempt's `model` is what its transcript says ran (gh#637).

Found on run `2026-09-26-fix-624-set-status-drop-level`: every
`implement-phase` attempt recorded the tier binding (`claude-haiku-4-5…`,
`claude-sonnet-5`), while all three executor transcripts name only
`claude-opus-5-5`. The executors were dispatched without a model, so the
harness ran them on the orchestrator's. `advance` records the binding before
anything runs, a prediction. `resolve` is where the agent id is known and its
transcript can be read, so that is where fr replaces the prediction with an
observation and says so when the two differ.

The captured subagent fixture runs on `claude-sonnet-5`; the tier here binds
`claude-opus-5`, so a mismatch is the default case.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _GROUPED_SHAPE,
    _SAME_INSTANT,
    _USAGE_FIRST,
    _attempts_by_unit,
    _invoke_measurable,
    _repo,
    _seed_journal,
    _squash,
    _started_grouped_with_plan,
    _write_repo_models,
    _write_shape,
)
from tests.unit.transcript_sessions import add_dispatch, write_session

UNIT = ["--step", "code", "--item", "phase/1"]


@pytest.fixture
def dispatched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path]:
    """`phase/1/code` advanced under a `hard` tier bound to `claude-opus-5`.
    Returns `(repo, shipped, transcript root, session transcript)`."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier="hard")
    _write_repo_models(repo, "claude-code:\n  hard: claude-opus-5\n")
    _seed_journal(repo, shipped)
    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    result = _invoke_measurable(repo, shipped, ["run", "advance", "r1"], root, "sess-1")
    assert result.exit_code == 0, result.output
    return repo, shipped, root, session


def _code_attempt(repo: Path):
    (attempt,) = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"]
    return attempt


def test_advance_still_records_the_binding_as_its_prediction(
    dispatched: tuple[Path, Path, Path, Path],
) -> None:
    repo, *_ = dispatched
    assert _code_attempt(repo).model == "claude-opus-5"


def test_resolve_records_the_model_the_subagent_transcript_names(
    dispatched: tuple[Path, Path, Path, Path],
) -> None:
    repo, shipped, root, session = dispatched
    add_dispatch(
        session, timestamp=_SAME_INSTANT, agent_id="a1f1", tool_use_id="toolu_a", usage=_USAGE_FIRST
    )

    result = _invoke_measurable(
        repo,
        shipped,
        ["run", "resolve", "r1", *UNIT, "--state", "done", "--agent", "a1f1"],
        root,
        "sess-1",
    )

    assert result.exit_code == 0, result.output
    assert _code_attempt(repo).model == "claude-sonnet-5"
    out = _squash(result.output)
    assert "ran on claude-sonnet-5" in out
    assert "claude-opus-5" in out


def test_an_agent_claimed_earlier_is_observed_at_resolve(
    dispatched: tuple[Path, Path, Path, Path],
) -> None:
    """`claim --agent` then a bare `resolve`: the id is on the attempt already."""
    repo, shipped, root, session = dispatched
    claim = ["run", "claim", "r1", *UNIT, "--agent", "a1f1"]
    assert _invoke_measurable(repo, shipped, claim, root, "sess-1").exit_code == 0
    add_dispatch(
        session, timestamp=_SAME_INSTANT, agent_id="a1f1", tool_use_id="toolu_a", usage=_USAGE_FIRST
    )

    resolve = ["run", "resolve", "r1", *UNIT, "--state", "done"]
    result = _invoke_measurable(repo, shipped, resolve, root, "sess-1")

    assert result.exit_code == 0, result.output
    assert _code_attempt(repo).model == "claude-sonnet-5"


def test_a_dated_id_of_the_bound_model_is_a_match_not_a_mismatch(
    dispatched: tuple[Path, Path, Path, Path],
) -> None:
    """Claude Code transcripts name some models with their date
    (`claude-haiku-4-5-20251001`), while a binding may name the undated id
    (the shipped `mechanical: claude-haiku-4-5`). The dispatch honoured the
    binding: no warning — and the precise id is what gets recorded."""
    repo, shipped, root, session = dispatched
    transcript = add_dispatch(
        session, timestamp=_SAME_INSTANT, agent_id="a1f1", tool_use_id="toolu_a", usage=_USAGE_FIRST
    )
    transcript.write_text(
        transcript.read_text().replace("claude-sonnet-5", "claude-opus-5-20260101")
    )

    result = _invoke_measurable(
        repo,
        shipped,
        ["run", "resolve", "r1", *UNIT, "--state", "done", "--agent", "a1f1"],
        root,
        "sess-1",
    )

    assert result.exit_code == 0, result.output
    assert _code_attempt(repo).model == "claude-opus-5-20260101"
    assert "ran on" not in _squash(result.output)


def test_an_unobservable_subagent_keeps_the_recorded_model(
    dispatched: tuple[Path, Path, Path, Path],
) -> None:
    """No transcript for the agent: nothing observed, nothing replaced, no
    warning — an absence is not a mismatch."""
    repo, shipped, root, _ = dispatched
    result = _invoke_measurable(
        repo,
        shipped,
        ["run", "resolve", "r1", *UNIT, "--state", "done", "--agent", "zz99"],
        root,
        "sess-1",
    )

    assert result.exit_code == 0, result.output
    assert _code_attempt(repo).model == "claude-opus-5"
    assert "ran on" not in _squash(result.output)
