"""`fr run cost` — gh#593's per-step table (spec
`2026-09-24-fr-goal-scope-proportion-cost-design.md` §D, Reporting).

One row per top-level step with the main session's turns, sessions, four
token figures, cache-read per turn and cost when the harness reported one; a
subagent line summing every attempt's `measured`; and an explicit flag on the
measurements taken before the per-message dedupe, which over-count.

The numbers are asserted on the pure row builder (`fr.run.cost`), because a
rich table folds cells at the test runner's 80 columns; the CLI tests assert
what the operator must be able to see at any width.
"""

from __future__ import annotations

import os
from pathlib import Path

from fr.cli import app
from fr.run.cost import CostRow, cost_rows, possibly_over_counted, subagent_total
from fr.run.model import (
    Attempt,
    MainSessionUsage,
    MeasuredTokens,
    RunState,
    StepRecord,
    UnitRecord,
    load_run_state,
    save_run_state,
)
from typer.testing import CliRunner

runner = CliRunner()


def _measured(n: int) -> MeasuredTokens:
    return MeasuredTokens(
        input_tokens=n,
        cache_creation_input_tokens=10 * n,
        cache_read_input_tokens=100 * n,
        output_tokens=2 * n,
    )


def _attempt(returned: str, n: int | None) -> Attempt:
    return Attempt(
        dispatched=returned,
        returned=returned,
        outcome="done",
        measured=None if n is None else _measured(n),
    )


MAIN_IMPLEMENT = MainSessionUsage(
    input_tokens=40,
    cache_creation_input_tokens=5_000,
    cache_read_input_tokens=90_000,
    output_tokens=1_200,
    turns=30,
    sessions=2,
    cost_usd=1.25,
)
MAIN_DELIVER = MainSessionUsage(
    input_tokens=4,
    cache_creation_input_tokens=500,
    cache_read_input_tokens=9_000,
    output_tokens=120,
    turns=0,
    sessions=1,
)


def _state() -> RunState:
    """Upgraded mid-run: `brainstorm` and `spec-review` completed on an fr
    without main-session measurement (and without the dedupe); `implement`
    and `deliver` on this one."""
    return RunState(
        schema_version=6,
        run="r1",
        workflow="fr-goal@1",
        branch="b",
        started="2026-09-24T09:00:00+00:00",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", at="2026-09-24T09:05:00+00:00"),
            "spec-review": StepRecord(
                state="done",
                at="2026-09-24T09:10:00+00:00",
                units={
                    "step/spec-review": UnitRecord(
                        attempts=(_attempt("2026-09-24T09:10:00+00:00", 1),)
                    )
                },
            ),
            "implement": StepRecord(
                state="done",
                at="2026-09-24T10:00:00+00:00",
                main_session=MAIN_IMPLEMENT,
                units={
                    "phase/1/code": UnitRecord(
                        state="done",
                        attempts=(
                            _attempt("2026-09-24T09:50:00+00:00", 2),
                            _attempt("2026-09-24T09:55:00+00:00", None),
                        ),
                    )
                },
            ),
            "deliver": StepRecord(
                state="done",
                at="2026-09-24T10:30:00+00:00",
                main_session=MAIN_DELIVER,
                units={
                    "step/deliver": UnitRecord(attempts=(_attempt("2026-09-24T10:20:00+00:00", 3),))
                },
            ),
        },
    )


# --- the pure builder ---------------------------------------------------------


def test_one_row_per_top_level_step_in_cursor_order() -> None:
    rows = cost_rows(_state())
    assert [r.step for r in rows] == ["brainstorm", "spec-review", "implement", "deliver"]


def test_a_measured_step_carries_its_figures_and_cache_read_per_turn() -> None:
    row = {r.step: r for r in cost_rows(_state())}["implement"]
    assert row == CostRow(
        step="implement",
        turns=30,
        sessions=2,
        input_tokens=40,
        cache_creation_input_tokens=5_000,
        cache_read_input_tokens=90_000,
        output_tokens=1_200,
        cache_read_per_turn=3_000,
        cost_usd=1.25,
    )


def test_an_unmeasured_step_is_none_throughout_never_zero() -> None:
    row = {r.step: r for r in cost_rows(_state())}["brainstorm"]
    assert row == CostRow(step="brainstorm")
    assert row.turns is None and row.input_tokens is None and row.cost_usd is None


def test_zero_turns_has_no_cache_read_per_turn() -> None:
    row = {r.step: r for r in cost_rows(_state())}["deliver"]
    assert row.turns == 0 and row.cache_read_per_turn is None and row.cost_usd is None


def test_the_subagent_line_sums_every_measured_attempt() -> None:
    total = subagent_total(_state())
    assert total.measured == 3 and total.attempts == 4
    assert total.tokens == _measured(1 + 2 + 3)


def test_measurements_taken_before_main_session_existed_are_flagged() -> None:
    """The dedupe shipped with main-session measurement, so a measured attempt
    that returned before the run's first main-session measurement was summed
    per record — possibly over-counted. An unmeasured one has nothing to flag."""
    assert possibly_over_counted(_state()) == ["phase/1/code", "step/spec-review"]


def test_a_run_with_no_main_session_anywhere_flags_every_measurement() -> None:
    state = _state()
    steps = {k: v.model_copy(update={"main_session": None}) for k, v in state.steps.items()}
    assert possibly_over_counted(state.model_copy(update={"steps": steps})) == [
        "phase/1/code",
        "step/deliver",
        "step/spec-review",
    ]


# --- the command ---------------------------------------------------------------


def _invoke(repo: Path, *argv: str):
    return runner.invoke(app, ["run", "cost", *argv], env={**os.environ, "VK_REPO_ROOT": str(repo)})


def test_the_command_prints_the_table_and_writes_nothing(tmp_path: Path) -> None:
    path = save_run_state(tmp_path, _state())
    before = path.read_bytes()

    result = _invoke(tmp_path, "r1")

    assert result.exit_code == 0, result.output
    for step in ("brainstorm", "spec-review", "implement", "deliver", "subagents"):
        assert step in result.output
    assert "—" in result.output, "an unmeasured figure prints as a dash"
    assert "$1.25" in result.output
    assert path.read_bytes() == before, "read-only: the cursor is never written"
    assert load_run_state(tmp_path, "r1") == _state()


def test_the_command_names_the_possibly_over_counted_units(tmp_path: Path) -> None:
    save_run_state(tmp_path, _state())

    result = _invoke(tmp_path, "r1")

    flat = " ".join(result.output.split())
    assert "possibly over-counted" in flat
    assert "phase/1/code" in flat and "step/spec-review" in flat
    assert "step/deliver" not in flat.split("possibly over-counted", 1)[1]


def test_an_unknown_run_exits_two(tmp_path: Path) -> None:
    assert _invoke(tmp_path, "nope").exit_code == 2
