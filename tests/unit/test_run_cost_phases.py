"""Per-phase cost rows and the role-split step table (spec
2026-10-06-cost-evidence §E, R8).

Fixtures use the REAL cursor nesting: phase units live under the group step
`implement`, keyed `phase/<n>/<member>` (members `implement-phase` and
`review-phase`), exactly as this repo's own cursors hold them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.run.cost import PhaseRow, compact_tokens, phase_rows, summarize
from fr.run.model import Attempt, RunState, StepRecord, UnitRecord, save_run_state
from fr.usage.file import (
    Capture,
    Figure,
    ModelFigures,
    SessionEntry,
    UsageFile,
    dump_usage,
    host_label,
    usage_path,
)
from typer.testing import CliRunner

RUN = "r1"
EXECUTOR = "super-fr:fr-phase-executor"


def _attempt(**kw: object) -> Attempt:
    base: dict[str, object] = {
        "dispatched": "2026-10-06T10:00:00+00:00",
        "returned": "2026-10-06T11:00:00+00:00",
        "outcome": "done",
    }
    base.update(kw)
    return Attempt(**base)  # type: ignore[arg-type]


def _state(implement_units: dict[str, UnitRecord]) -> RunState:
    return RunState(
        run=RUN,
        workflow="fr-goal@1",
        branch="b",
        started="2026-10-06T09:00:00+00:00",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", at="2026-10-06T09:30:00+00:00"),
            "implement": StepRecord(
                state="done", at="2026-10-06T12:00:00+00:00", units=implement_units
            ),
            "deliver": StepRecord(state="pending"),
        },
    )


def _two_phases() -> RunState:
    """Phase 1: a v9 attempt (tier/bound) retried once, the retry on another
    model; phase 2: an attempt written before v9 (binding in `model`)."""
    return _state(
        {
            "phase/1/implement-phase": UnitRecord(
                state="done",
                attempts=(
                    _attempt(
                        dispatched="2026-10-06T09:00:00+00:00",
                        returned="2026-10-06T09:10:00+00:00",
                        outcome="failed",
                        agent_type=EXECUTOR,
                        tier="standard",
                        bound="claude-sonnet-5",
                    ),
                    _attempt(
                        agent="a1",
                        agent_type=EXECUTOR,
                        tier="hard",
                        bound="claude-opus-5",
                        model="claude-sonnet-5",
                    ),
                ),
            ),
            "phase/1/review-phase": UnitRecord(state="done", attempts=(_attempt(),)),
            "phase/2/implement-phase": UnitRecord(
                state="done",
                attempts=(_attempt(agent="a2", agent_type=EXECUTOR, model="claude-opus-5"),),
            ),
            "phase/2/review-phase": UnitRecord(state="done", attempts=(_attempt(),)),
        }
    )


def _fig(usd: float | None, turns: int, cache_read: int, output: int) -> Figure:
    return Figure(
        usd=usd, turns=turns, input=1, cache_write=2, cache_read=cache_read, output=output
    )


def _entry(usd: float | None) -> SessionEntry:
    """One session's split: phase 1 executor + orchestrator on both units,
    phase 2 executor only; main/subagent figures on two steps."""
    half = None if usd is None else usd / 2
    return SessionEntry(
        session="s1",
        role="main",
        models={"m": ModelFigures(output=1, usd=usd, usd_source="exact" if usd else "none")},
        steps={"brainstorm": Figure(usd=half, turns=5), "implement": Figure(usd=half, turns=20)},
        steps_by_role={
            "main": {
                "brainstorm": _fig(half, 5, 1_200_000, 34_000),
                "implement": _fig(half, 4, 500, 20),
            },
            "subagent": {"implement": _fig(half, 16, 2_000, 900)},
        },
        units={
            "phase/1/implement-phase": {
                "executor": _fig(usd, 10, 1000, 100),
                "orchestrator": _fig(usd, 2, 100, 10),
            },
            "phase/1/review-phase": {
                "reviewer": _fig(usd, 3, 300, 30),
                "orchestrator": _fig(usd, 1, 50, 5),
            },
            "phase/2/implement-phase": {"executor": _fig(usd, 6, 600, 60)},
            "(unattributed)": {"subagent": _fig(usd, 1, 1, 1)},
        },
    )


# --- phase_rows --------------------------------------------------------------


def test_tier_bound_and_ran_come_from_the_latest_non_synthesized_attempt() -> None:
    rows = phase_rows(_two_phases(), [_entry(1.0)])
    assert [r.phase for r in rows] == [1, 2]
    one = rows[0]
    assert (one.tier, one.bound, one.ran) == ("hard", "claude-opus-5", "claude-sonnet-5")
    assert one.mismatch is True


def test_ran_is_a_dash_for_an_attempt_that_recorded_no_bound() -> None:
    """Before v9 `model` held the binding, not what ran (gh#637)."""
    two = phase_rows(_two_phases(), [_entry(1.0)])[1]
    assert (two.tier, two.bound, two.ran) == (None, None, None)
    assert two.mismatch is False


def test_a_dated_id_of_the_bound_model_is_no_mismatch() -> None:
    state = _state(
        {
            "phase/1/implement-phase": UnitRecord(
                attempts=(
                    _attempt(
                        agent="a",
                        agent_type=EXECUTOR,
                        tier="mechanical",
                        bound="claude-haiku-4-5",
                        model="claude-haiku-4-5-20251001",
                    ),
                )
            )
        }
    )
    (row,) = phase_rows(state, [])
    assert row.ran == "claude-haiku-4-5-20251001" and row.mismatch is False


def test_an_unobserved_model_is_a_dash_and_never_a_mismatch() -> None:
    state = _state(
        {
            "phase/1/implement-phase": UnitRecord(
                attempts=(_attempt(agent_type=EXECUTOR, tier="hard", bound="claude-opus-5"),)
            )
        }
    )
    (row,) = phase_rows(state, [])
    assert (row.bound, row.ran, row.mismatch) == ("claude-opus-5", None, False)


def test_a_synthesized_attempt_is_skipped() -> None:
    state = _state(
        {
            "phase/1/implement-phase": UnitRecord(
                attempts=(
                    _attempt(agent_type=EXECUTOR, tier="hard", bound="b", model="b"),
                    Attempt(dispatched="2026-10-06T12:00:00+00:00", synthesized=True),
                )
            )
        }
    )
    (row,) = phase_rows(state, [])
    assert row.tier == "hard"


def test_role_figures_sum_units_and_orchestrator_spans_both_units() -> None:
    one, two = phase_rows(
        _two_phases(), [_entry(1.0), _entry(0.5).model_copy(update={"session": "s2"})]
    )
    assert one.executor is not None and one.executor.turns == 20
    assert one.executor.usd == pytest.approx(1.5)
    assert one.executor.cache_read == 2000 and one.executor.output == 200
    assert one.reviewer is not None and one.reviewer.turns == 6
    # orchestrator = implement unit + review unit
    assert one.orchestrator is not None and one.orchestrator.turns == 6
    assert one.orchestrator.usd == pytest.approx(3.0)
    assert one.orchestrator.cache_read == 300
    assert two.executor is not None and two.executor.turns == 12
    assert two.reviewer is None and two.orchestrator is None


def test_unpriced_figures_keep_turns_and_tokens_and_dollars_none() -> None:
    (one, _two) = phase_rows(_two_phases(), [_entry(None)])
    assert one.executor is not None
    assert (one.executor.turns, one.executor.cache_read, one.executor.usd) == (10, 1000, None)


def test_an_unavailable_entry_contributes_nothing() -> None:
    rows = phase_rows(_two_phases(), [SessionEntry(session="x", unavailable="elsewhere")])
    assert all(r.executor is None and r.orchestrator is None for r in rows)


def test_phase_row_is_a_value() -> None:
    assert PhaseRow(phase=1, tier=None, bound=None, ran=None, mismatch=False) == PhaseRow(
        phase=1, tier=None, bound=None, ran=None, mismatch=False
    )


# --- summarize: main and subagent per step -----------------------------------


def test_step_rows_carry_main_and_subagent_figures() -> None:
    summary = summarize([_entry(1.0)], ["brainstorm", "implement", "deliver"])
    rows = {r.step: r for r in summary.steps}
    assert rows["brainstorm"].main is not None
    assert rows["brainstorm"].main.cache_read == 1_200_000
    assert rows["brainstorm"].subagent is None
    assert rows["implement"].subagent is not None
    assert rows["implement"].subagent.turns == 16
    assert rows["implement"].subagent.usd == pytest.approx(0.5)
    assert rows["deliver"].main is None and rows["deliver"].subagent is None


def test_compact_tokens() -> None:
    assert compact_tokens(Figure(cache_read=1_200_000, output=34_000)) == "1.2M / 34k"
    assert compact_tokens(Figure(cache_read=999, output=1_500)) == "999 / 1.5k"
    assert compact_tokens(Figure(turns=3)) == "—"
    assert compact_tokens(None) == "—"


# --- the command ---------------------------------------------------------------


def _write_usage(repo: Path, usd: float | None) -> None:
    capture = Capture(
        host=host_label(RUN, "a"),
        harness="claude-code",
        mode="host-worktree",
        captured_at="2026-10-06T12:00:00+00:00",
        at=("deliver",),
        sessions=(_entry(usd),),
    )
    path = usage_path(repo, RUN)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_usage(UsageFile(run=RUN, captures=(capture,))))


def _invoke(repo: Path) -> str:
    result = CliRunner().invoke(
        app,
        ["run", "cost", RUN],
        env={**os.environ, "VK_REPO_ROOT": str(repo), "COLUMNS": "400"},
    )
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


def test_the_command_prints_the_role_split_and_the_phase_table(tmp_path: Path) -> None:
    save_run_state(tmp_path, _two_phases())
    _write_usage(tmp_path, 1.0)

    out = _invoke(tmp_path)

    assert "subagent" in out and "main" in out
    assert "1.2M / 34k" in out
    assert "By phase" in out
    for needle in ("hard", "claude-opus-5", "claude-sonnet-5", "executor", "reviewer"):
        assert needle in out, needle
    assert "≠" in out, "the mismatched phase is marked"


def test_the_command_unpriced_shows_tokens_and_turns_and_dash_dollars(tmp_path: Path) -> None:
    save_run_state(tmp_path, _two_phases())
    _write_usage(tmp_path, None)

    out = _invoke(tmp_path)

    assert "1.2M / 34k" in out
    assert "—" in out
    assert "$" not in out


def test_a_closed_out_run_prints_its_per_phase_table_from_the_archive(tmp_path: Path) -> None:
    """Review p2-r1: an archived run's usage file was found, its cursor was not."""
    from fr.run.model import archived_run_path, run_path
    from fr.usage.file import archived_usage_path

    save_run_state(tmp_path, _two_phases())
    archived = archived_run_path(tmp_path, RUN)
    archived.parent.mkdir(parents=True, exist_ok=True)
    run_path(tmp_path, RUN).rename(archived)
    _write_usage(tmp_path, 1.0)
    usage = usage_path(tmp_path, RUN)
    target = archived_usage_path(tmp_path, RUN)
    target.parent.mkdir(parents=True, exist_ok=True)
    usage.rename(target)

    out = _invoke(tmp_path)

    assert "By phase" in out
    assert "claude-sonnet-5 ≠" in out


def test_an_unparseable_archived_cursor_still_prints_the_step_table(tmp_path: Path) -> None:
    from fr.run.model import archived_run_path

    archived = archived_run_path(tmp_path, RUN)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("schema_version: 2\nrun: r1\nitems: {}\n")
    _write_usage(tmp_path, 1.0)

    out = _invoke(tmp_path)

    assert "1.2M / 34k" in out
    assert "By phase" not in out, "an unreadable cursor gives no per-phase table"
