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


# --- V1 context accounting (methodology restoration, phase 4) ---


def test_accounting_round_trips_and_defaults_to_absent() -> None:
    """Per-item context snapshots ride the run file (additive, defaulted —
    every pre-accounting run still parses with `accounting=None`)."""
    from fr.run.model import PhaseAccounting

    snap = PhaseAccounting(
        at="2026-09-09T00:00:01Z",
        journal_entries=12,
        journal_lines=180,
        handoff_chars=2100,
        spec_bytes=8400,
        plan_bytes=12500,
    )
    state = _sample_state().model_copy(update={"accounting": {"phase/1/code": snap}})
    assert parse_run_state(dump_run_state(state)) == state
    assert _sample_state().accounting is None
    assert "accounting" not in dump_run_state(_sample_state())


# --- Phase 4: gate provenance + the `run` artifact stamp -------------------
#
# `RunState`/`StepRecord` are `extra="forbid"`, so adding `answered_by` is a
# SHAPE change under `.claude/rules/artifact-versioning.md`. These pin the two
# halves the rule requires of the model itself: the new field, and the
# optional defaulted `schema_version` without which the stamp the migration
# writes would make the file unparseable by the fr that wrote it.


def test_step_record_answered_by_defaults_to_absent_and_round_trips() -> None:
    state = _sample_state()
    assert state.steps["isolate"].answered_by is None

    cleared = state.steps["isolate"].model_copy(update={"gate": "cleared", "answered_by": "agent"})
    text = dump_run_state(_with_isolate(state, cleared))
    assert "answered_by: agent" in text
    assert parse_run_state(text).steps["isolate"].answered_by == "agent"


def _with_isolate(state: RunState, record: StepRecord) -> RunState:
    steps = dict(state.steps)
    steps["isolate"] = record
    return state.model_copy(update={"steps": steps})


def test_an_unrecognised_answered_by_fails_loud() -> None:
    text = """
run: r
workflow: fr-goal@1
branch: b
started: "2026-08-14T09:00:00Z"
cursor: a
steps:
  a:
    state: done
    answered_by: the-cat
"""
    with pytest.raises(RunStateError):
        parse_run_state(text)


def test_run_state_accepts_an_optional_defaulted_schema_version() -> None:
    """Required by `.claude/rules/artifact-versioning.md` in the same PR that
    moves the kind past version 1: the migration stamps `schema_version` into
    the file, and `extra="forbid"` would otherwise make that file unreadable
    by the very fr that wrote it."""
    # absent -> the pre-framework version, not an error
    assert parse_run_state(dump_run_state(_sample_state())) is not None
    state = RunState(
        run="r",
        workflow="fr-goal@1",
        branch="b",
        started="2026-08-14T09:00:00Z",
        cursor="a",
        steps={"a": StepRecord(state="pending")},
    )
    assert state.schema_version == 1

    stamped = parse_run_state(
        "schema_version: 2\nrun: r\nworkflow: fr-goal@1\nbranch: b\n"
        'started: "2026-08-14T09:00:00Z"\ncursor: a\nsteps:\n  a:\n    state: pending\n'
    )
    assert stamped.schema_version == 2


def test_the_current_run_schema_version_comes_from_the_artifact_registry() -> None:
    """One number, one place: the registry is the ONLY module allowed to
    declare a kind's `current_version`, so fr's own writers read it rather
    than restating it."""
    from fr.artifacts.registry import artifact_kind
    from fr.run.model import current_run_schema_version

    assert current_run_schema_version() == artifact_kind("run").current_version


# --- Phase 1 (dispatch-holder-identity): DispatchRecord ---------------------
#
# spec `2026-09-20-dispatch-holder-identity-design.md` §4.A/§4.B. `dispatched`
# is the one field fr writes itself (`advance` timestamps its own act);
# everything else is either derived (`agent_type`, `model`) or a reported
# claim (`agent`, `harness`, `returned`, `outcome`) — spec §3's seam.


def test_dispatch_record_requires_dispatched_and_defaults_the_rest_to_none() -> None:
    from fr.run.model import DispatchRecord

    record = DispatchRecord(dispatched="2026-09-20T09:00:00Z")
    assert record.dispatched == "2026-09-20T09:00:00Z"
    assert record.agent is None
    assert record.agent_type is None
    assert record.harness is None
    assert record.model is None
    assert record.returned is None
    assert record.outcome is None

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError, missing field
        DispatchRecord()  # type: ignore[call-arg]


def test_dispatch_record_is_frozen_and_closed_world() -> None:
    from fr.run.model import DispatchRecord

    record = DispatchRecord(dispatched="2026-09-20T09:00:00Z")
    with pytest.raises(Exception):  # noqa: B017 — frozen
        record.agent = "a1"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017 — extra="forbid"
        DispatchRecord(dispatched="2026-09-20T09:00:00Z", bogus="x")  # type: ignore[call-arg]


@pytest.mark.parametrize("outcome", ["done", "failed", "abandoned"])
def test_dispatch_record_outcome_accepts_every_documented_value(outcome: str) -> None:
    from fr.run.model import DispatchRecord

    record = DispatchRecord(
        dispatched="2026-09-20T09:00:00Z",
        returned="2026-09-20T09:30:00Z",
        outcome=outcome,  # type: ignore[arg-type]
    )
    assert record.outcome == outcome


def test_dispatch_record_pairs_returned_and_outcome() -> None:
    """`outcome` is set exactly when `returned` is — the docstring said so
    before anything enforced it, and "open" is the state every reader keys on.

    A record with `returned` and no `outcome` reads as still-held to
    `fr run status` while carrying a return timestamp, and one with `outcome`
    and no `returned` reads as held forever by an agent that already finished.
    Both are the double-dispatch hazard wearing a disguise, so the model
    refuses them rather than leaving the invariant to every caller.
    """
    from fr.run.model import DispatchRecord

    # Open: neither half set. Closed: both. Both are fine.
    assert DispatchRecord(dispatched="2026-09-20T09:00:00Z").returned is None
    assert (
        DispatchRecord(
            dispatched="2026-09-20T09:00:00Z",
            returned="2026-09-20T09:30:00Z",
            outcome="done",
        ).outcome
        == "done"
    )

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        DispatchRecord(dispatched="2026-09-20T09:00:00Z", returned="2026-09-20T09:30:00Z")
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        DispatchRecord(dispatched="2026-09-20T09:00:00Z", outcome="done")


def test_dispatch_record_outcome_rejects_an_unrecognised_value() -> None:
    from fr.run.model import DispatchRecord

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        DispatchRecord(dispatched="2026-09-20T09:00:00Z", outcome="cancelled")  # type: ignore[arg-type]


def test_dispatch_record_harness_accepts_every_member_of_the_closed_harness_set() -> None:
    from fr.harness.model import HARNESSES
    from fr.run.model import DispatchRecord

    for harness in HARNESSES:
        record = DispatchRecord(dispatched="2026-09-20T09:00:00Z", harness=harness)
        assert record.harness == harness


def test_dispatch_record_harness_rejects_unknown() -> None:
    from fr.run.model import DispatchRecord

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        DispatchRecord(dispatched="2026-09-20T09:00:00Z", harness="unknown")


def test_step_record_dispatch_defaults_to_none_and_a_dispatchless_step_parses_unchanged() -> None:
    text = """
run: r
workflow: fr-goal@1
branch: b
started: "2026-08-14T09:00:00Z"
cursor: a
steps:
  a: {state: pending}
"""
    state = parse_run_state(text)
    assert state.steps["a"].dispatch is None


def test_a_run_state_carrying_dispatch_round_trips_and_omits_dispatch_when_none() -> None:
    from fr.run.model import DispatchRecord

    state = _sample_state()
    held = DispatchRecord(
        dispatched="2026-08-14T09:00:11Z",
        agent="add889a7",
        agent_type="super-fr:fr-phase-executor",
        harness="claude-code",
        model="claude-sonnet-5",
    )
    steps = dict(state.steps)
    steps["implement"] = steps["implement"].model_copy(
        update={"dispatch": {"phase/1/implement-phase": [held]}}
    )
    state = state.model_copy(update={"steps": steps})

    text = dump_run_state(state)
    assert "phase/1/implement-phase" in text
    round_tripped = parse_run_state(text)
    assert round_tripped == state
    assert round_tripped.steps["implement"].dispatch == {"phase/1/implement-phase": [held]}

    # a step with dispatch=None (the default) omits the key entirely
    assert "dispatch" not in dump_run_state(_sample_state())
