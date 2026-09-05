"""Run state — the durable cursor, spec §4.B, Phase 7.

`fr.run.model` is the run-side sibling of `fr.journal.model`: pydantic,
`frozen=True`, `extra="forbid"`, one parse entry point that never leaks a
raw yaml/pydantic exception. It is the *control* log (which step, what it
emitted); the journal stays the *content* log.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import (
    RunState,
    RunStateError,
    StepRecord,
    archived_run_path,
    dump_run_state,
    parse_run_state,
    run_path,
)


def _sample_state() -> RunState:
    return RunState(
        run="2026-08-14-ticket-polling",
        workflow="fr-goal@1",
        branch="feat/ticket-polling",
        started="2026-08-14T09:00:00Z",
        cursor="implement",
        steps={
            "isolate": StepRecord(state="done", at="2026-08-14T09:00:11Z"),
            "brainstorm": StepRecord(
                state="done",
                emitted={"spec": "docs/superpowers/specs/2026-08-14-x-design.md"},
            ),
            "spec-review": StepRecord(state="done"),
            "plan": StepRecord(
                state="done", emitted={"plan": "docs/superpowers/plans/2026-08-14-x"}
            ),
            "plan-review": StepRecord(state="done", exit=0),
            "implement": StepRecord(state="running"),
            "review": StepRecord(state="pending"),
            "deliver": StepRecord(state="pending"),
        },
    )


def test_round_trip_is_byte_stable() -> None:
    state = _sample_state()
    text1 = dump_run_state(state)
    state2 = parse_run_state(text1)
    text2 = dump_run_state(state2)
    assert text1 == text2
    assert state2 == state


def test_run_path_resolves_under_docs_superpowers_runs(tmp_path: Path) -> None:
    assert run_path(tmp_path, "2026-08-14-ticket-polling") == (
        tmp_path / "docs" / "superpowers" / "runs" / "2026-08-14-ticket-polling.yaml"
    )


def test_archived_run_path_resolves_under_implemented_runs(tmp_path: Path) -> None:
    assert archived_run_path(tmp_path, "2026-08-14-ticket-polling") == (
        tmp_path
        / "docs"
        / "superpowers"
        / "implemented"
        / "runs"
        / "2026-08-14-ticket-polling.yaml"
    )


def test_unknown_step_state_fails_loud() -> None:
    text = """
run: r
workflow: fr-goal@1
branch: b
started: "2026-08-14T09:00:00Z"
cursor: a
steps:
  a: {state: bogus}
"""
    with pytest.raises(RunStateError):
        parse_run_state(text)


def test_invalid_yaml_fails_loud_as_run_state_error() -> None:
    with pytest.raises(RunStateError):
        parse_run_state("not: valid: yaml: [")


def test_non_mapping_top_level_fails_loud() -> None:
    with pytest.raises(RunStateError):
        parse_run_state("- a\n- b\n")


def test_unknown_top_level_key_fails_loud() -> None:
    text = """
run: r
workflow: fr-goal@1
branch: b
started: "2026-08-14T09:00:00Z"
cursor: a
steps: {}
bogus: true
"""
    with pytest.raises(RunStateError):
        parse_run_state(text)


def test_step_record_and_run_state_are_frozen() -> None:
    state = _sample_state()
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError on frozen mutation
        state.cursor = "review"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017
        state.steps["isolate"].state = "failed"  # type: ignore[misc]


def test_pending_step_has_no_null_padding_in_dump() -> None:
    """Optional step fields (`at`/`emitted`/`exit`/`stdout`) are excluded when
    unset, so a freshly-started run's YAML stays readable — no `at: null`
    noise for steps that haven't run yet."""
    state = _sample_state()
    text = dump_run_state(state)
    assert "review:" in text
    assert "null" not in text
