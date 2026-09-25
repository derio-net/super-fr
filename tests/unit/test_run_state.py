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


# --- one record per unit (spec 2026-09-20-unit-record-unification §4.A) -----
#
# `items`, `dispatch` and the top-level `accounting` were three key spaces over
# ONE identity. The live model is the v5 shape only: `StepRecord.units`. What a
# v4 cursor looks like is `fr.run.legacy`'s business, tested in
# `test_run_legacy.py` against captured files.

_MEASURED = {
    "input_tokens": 4,
    "cache_creation_input_tokens": 51315,
    "cache_read_input_tokens": 200784,
    "output_tokens": 1927,
}


def _with_units(state: RunState, step_id: str, units: dict) -> RunState:
    steps = dict(state.steps)
    steps[step_id] = steps[step_id].model_copy(update={"units": units})
    return state.model_copy(update={"steps": steps})


def test_a_unit_record_round_trips_with_its_state_and_attempts() -> None:
    from fr.run.model import Attempt, UnitRecord

    held = Attempt(
        dispatched="2026-09-20T00:00:01Z",
        agent="add889a7",
        agent_type="super-fr:fr-phase-executor",
        harness="claude-code",
        model="claude-sonnet-5",
    )
    closed = Attempt(
        dispatched="2026-09-19T00:00:01Z",
        returned="2026-09-19T01:00:00Z",
        outcome="abandoned",
    )
    state = _with_units(
        _sample_state(),
        "implement",
        {"phase/1/code": UnitRecord(state="running", attempts=(closed, held))},
    )

    text = dump_run_state(state)

    assert parse_run_state(text) == state
    assert dump_run_state(parse_run_state(text)) == text
    unit = parse_run_state(text).steps["implement"].units["phase/1/code"]
    assert [a.outcome for a in unit.attempts] == ["abandoned", None]


def test_units_default_to_absent_and_a_unitless_run_omits_the_key() -> None:
    assert _sample_state().steps["implement"].units is None
    assert "units" not in dump_run_state(_sample_state())


def test_a_unit_with_no_attempts_dumps_no_attempts_key() -> None:
    """An adopted `done` unit and a `manual` marker were never dispatched. They
    dump as `{state: …}` and nothing else — the same bytes the 4 -> 5 rewrite
    produces for them, so a migrated cursor and a native one agree."""
    from fr.run.model import UnitRecord

    state = _with_units(
        _sample_state(),
        "implement",
        {"phase/1/code": UnitRecord(state="done"), "phase/7": UnitRecord(state="manual")},
    )
    text = dump_run_state(state)
    assert "attempts" not in text
    assert parse_run_state(text) == state


@pytest.mark.parametrize(
    ("where", "fragment"),
    [
        ("step", "    items:\n      phase/1/code: done\n"),
        (
            "step",
            "    dispatch:\n      phase/1/code:\n      - dispatched: '2026-09-20T00:00:01Z'\n",
        ),
        ("top", "accounting:\n  phase/1/code:\n    at: '2026-09-09T09:00:01Z'\n"),
        # run 7 (spec 2026-09-25-lean-cost-aware-process §5.B.4): usage left the cursor
        ("step", "    main_session:\n      turns: 1\n"),
        (
            "step",
            "    units:\n      phase/1/code:\n        attempts:\n"
            "        - dispatched: '2026-09-20T00:00:01Z'\n          estimate: {}\n",
        ),
    ],
)
def test_the_live_parser_refuses_every_map_the_flip_removed(where: str, fragment: str) -> None:
    """The live model is v5 ONLY and closed-world: a v4 body is refused, by
    name, rather than half-read. Reading v4 is `fr.run.legacy`'s job, and
    getting a v4 file to v5 is the migration's — `fr migrate artifacts`."""
    head = (
        "run: r1\nworkflow: fr-goal@1\nbranch: feat/x\nstarted: '2026-09-09T09:00:00Z'\n"
        "cursor: implement\nsteps:\n  implement:\n    state: running\n"
    )
    text = head + fragment
    with pytest.raises(RunStateError, match=fragment.split(":")[0].strip()):
        parse_run_state(text)


_CAPTURED = sorted(
    (Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors").glob("v*/*.yaml")
)


@pytest.mark.parametrize("path", _CAPTURED, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_migrated_capture_and_a_native_dump_are_the_same_data(path: Path) -> None:
    """Every captured cursor, rewritten 4 -> 5, parses with the live model and
    dumps back to the SAME data — nothing invented by the model (no padded
    `attempts: []`, no defaulted zeros the rewrite did not write), nothing lost."""
    import yaml
    from fr.artifacts.run_usage_split import split_usage
    from fr.run.legacy import v4_to_v5

    assert _CAPTURED, "no captured cursors — the glob is wrong, not the fixtures"
    migrated, _usage = split_usage(v4_to_v5(yaml.safe_load(path.read_text())))
    state = parse_run_state(yaml.safe_dump(migrated, sort_keys=False))
    redumped = yaml.safe_load(dump_run_state(state))
    redumped.pop("schema_version")
    migrated.pop("schema_version", None)
    assert redumped == migrated


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


# --- Attempt (was DispatchRecord; dispatch-holder-identity phase 1) --------
#
# spec `2026-09-20-dispatch-holder-identity-design.md` §4.A/§4.B. `dispatched`
# is the one field fr writes itself (`advance` timestamps its own act);
# everything else is either derived (`agent_type`, `model`) or a reported
# claim (`agent`, `harness`, `returned`, `outcome`) — spec §3's seam.


def test_dispatch_record_requires_dispatched_and_defaults_the_rest_to_none() -> None:
    from fr.run.model import Attempt

    record = Attempt(dispatched="2026-09-20T09:00:00Z")
    assert record.dispatched == "2026-09-20T09:00:00Z"
    assert record.agent is None
    assert record.agent_type is None
    assert record.harness is None
    assert record.model is None
    assert record.returned is None
    assert record.outcome is None

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError, missing field
        Attempt()  # type: ignore[call-arg]


def test_dispatch_record_is_frozen_and_closed_world() -> None:
    from fr.run.model import Attempt

    record = Attempt(dispatched="2026-09-20T09:00:00Z")
    with pytest.raises(Exception):  # noqa: B017 — frozen
        record.agent = "a1"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017 — extra="forbid"
        Attempt(dispatched="2026-09-20T09:00:00Z", bogus="x")  # type: ignore[call-arg]


@pytest.mark.parametrize("outcome", ["done", "failed", "abandoned"])
def test_dispatch_record_outcome_accepts_every_documented_value(outcome: str) -> None:
    from fr.run.model import Attempt

    record = Attempt(
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
    from fr.run.model import Attempt

    # Open: neither half set. Closed: both. Both are fine.
    assert Attempt(dispatched="2026-09-20T09:00:00Z").returned is None
    assert (
        Attempt(
            dispatched="2026-09-20T09:00:00Z",
            returned="2026-09-20T09:30:00Z",
            outcome="done",
        ).outcome
        == "done"
    )

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Attempt(dispatched="2026-09-20T09:00:00Z", returned="2026-09-20T09:30:00Z")
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Attempt(dispatched="2026-09-20T09:00:00Z", outcome="done")


def test_dispatch_record_outcome_rejects_an_unrecognised_value() -> None:
    from fr.run.model import Attempt

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Attempt(dispatched="2026-09-20T09:00:00Z", outcome="cancelled")  # type: ignore[arg-type]


def test_dispatch_record_harness_accepts_every_member_of_the_closed_harness_set() -> None:
    from fr.harness.model import HARNESSES
    from fr.run.model import Attempt

    for harness in HARNESSES:
        record = Attempt(dispatched="2026-09-20T09:00:00Z", harness=harness)
        assert record.harness == harness


def test_dispatch_record_harness_rejects_unknown() -> None:
    from fr.run.model import Attempt

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Attempt(dispatched="2026-09-20T09:00:00Z", harness="unknown")


# --- multi-line strings render as block literals (PR #508 review) ----------
#
# A cursor is git-tracked and read in diffs. `safe_dump`'s default renders a
# string ending in a newline as a single-quoted scalar folded over three lines
# (valid YAML that LOOKS broken — the operator asked whether it was), and a
# failed step's several lines of output as one double-quoted blob of `\n`
# escapes and continuation backslashes.


def _with_stdout(stdout: str) -> RunState:
    state = _sample_state()
    steps = dict(state.steps)
    steps["plan-review"] = StepRecord(state="failed", exit=1, stdout=stdout)
    return state.model_copy(update={"steps": steps})


def test_multi_line_stdout_dumps_as_a_block_literal() -> None:
    stdout = (
        "plan self-review: 2 issue(s)\n"
        " phase 1 task P1.T3 has no refactor step\n"
        " phase 7 task P7.T2 has no refactor step\n"
    )
    text = dump_run_state(_with_stdout(stdout))

    assert "    stdout: |\n" in text
    assert "      plan self-review: 2 issue(s)\n" in text
    assert "       phase 7 task P7.T2 has no refactor step\n" in text
    assert "\\n" not in text
    assert "\\\n" not in text


def test_a_single_trailing_newline_no_longer_folds_a_quoted_scalar() -> None:
    text = dump_run_state(_with_stdout("self-review passed\n"))

    assert "    stdout: |\n      self-review passed\n" in text
    assert "'self-review passed" not in text


def test_a_single_line_string_is_still_plain() -> None:
    text = dump_run_state(_with_stdout("self-review passed"))

    assert "    stdout: self-review passed\n" in text


# Block style is a HINT to PyYAML's emitter, which falls back to a quoted
# scalar for anything a block literal cannot carry. Whatever it picks, the
# string that comes back must be the string that went in — byte for byte,
# chomping included — and the dump must be a fixed point.
_AWKWARD = [
    "one\n",
    "one\ntwo",
    "one\ntwo\n",
    "one\ntwo\n\n",
    "one\n\n\ntwo\n",
    "\n",
    "\n\n",
    "\nleading blank\n",
    "  leading spaces\nthen not\n",
    "trailing space \nnext\n",
    "tab\there\nnext\n",
    "crlf\r\nnext\r\n",
    "# looks like a comment\n- looks like a list\nkey: value\n",
    "--- \n...\n",
    "unicode ✓ — dash\nnext\n",
    "ansi \x1b[31mred\x1b[0m\nnext\n",
    "'single' and \"double\"\nnext\n",
    "x" * 200 + "\n" + "y " * 100 + "\n",
]


@pytest.mark.parametrize("stdout", _AWKWARD, ids=[repr(s)[:24] for s in _AWKWARD])
def test_every_stdout_round_trips_exactly(stdout: str) -> None:
    state = _with_stdout(stdout)
    text = dump_run_state(state)

    back = parse_run_state(text)

    assert back.steps["plan-review"].stdout == stdout
    assert back == state
    assert dump_run_state(back) == text


def test_long_lines_inside_a_block_literal_are_not_folded() -> None:
    line = "word " * 60 + "end"
    text = dump_run_state(_with_stdout(f"{line}\nnext\n"))

    assert f"      {line}\n" in text


@pytest.mark.parametrize(
    "name",
    [
        "v4/2026-09-20-feat-phase-holder-identity.yaml",
        "v4/2026-09-20-fix-fr-run-cursor-cluster.yaml",
        "v3/2026-09-20-feat-bounded-executor-handoff.yaml",
        "v2/2026-09-20-journal-require-reviews-v2.yaml",
    ],
)
def test_the_migration_and_the_native_dump_are_one_writer(tmp_path: Path, name: str) -> None:
    """Two writers put cursors on disk — `dump_run_state` and the 4 -> 5 body
    rewrite. If only one learns a style, a cursor restyles itself the first
    time it is saved after migrating: a diff nobody wrote."""
    from fr.artifacts.run_unit_record import rewrite_to_unit_records

    fixture = Path(__file__).resolve().parents[2] / "tests/fixtures/run_cursors" / name
    path = tmp_path / fixture.name
    path.write_bytes(fixture.read_bytes())

    rewrite_to_unit_records(path)
    # …and the 6 -> 7 split, the chain's last body rewrite, writes through the
    # same `dump_cursor_yaml`
    import yaml
    from fr.artifacts.run_usage_split import split_usage
    from fr.run.model import dump_cursor_yaml

    migrated = dump_cursor_yaml(split_usage(yaml.safe_load(path.read_text()))[0])

    if "phase-holder-identity" in name:  # the one whose `plan-review` printed a line
        assert "    stdout: |\n      self-review passed\n" in migrated
    assert "\\n" not in migrated
    body = "\n".join(ln for ln in migrated.splitlines() if not ln.startswith("schema_version:"))
    native = dump_run_state(parse_run_state(migrated))
    native_body = "\n".join(
        ln for ln in native.splitlines() if not ln.startswith("schema_version:")
    )
    assert body == native_body
