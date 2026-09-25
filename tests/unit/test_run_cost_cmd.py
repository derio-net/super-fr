"""`fr run cost` — a run's cost read from its usage file (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.4).

Numbers are asserted on the pure summarizer (`fr.run.cost`), because a rich
table folds cells at the runner's width; the CLI tests assert what the operator
must see: per-step rows, `—` for an unobserved figure (never `0`), a checkout
that never ran the run, the archive fallback, and `--recompute`.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.run.cost import effective_entries, summarize
from fr.run.model import RunState, StepRecord, save_run_state
from fr.usage.file import (
    Capture,
    Figure,
    ModelFigures,
    SessionEntry,
    UsageFile,
    archived_usage_path,
    dump_usage,
    host_label,
    usage_path,
)
from typer.testing import CliRunner

runner = CliRunner()
RUN = "r1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "usage"
CC_SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"


def _entry(session: str, usd: float | None, turns: int | None, step: str = "brainstorm"):
    return SessionEntry(
        session=session,
        role="main",
        models={
            "claude-opus-5-5": ModelFigures(
                input=1,
                cache_write=2,
                cache_read=30,
                output=4,
                usd=usd,
                usd_source="exact" if usd is not None else "none",
            )
        },
        steps={step: Figure(usd=usd, turns=turns)},
    )


def _capture(host: str, at: str, *sessions: SessionEntry) -> Capture:
    return Capture(
        host=host_label(RUN, host),
        harness="claude-code",
        mode="host-worktree",
        captured_at="2026-09-25T00:00:00+00:00",
        at=(at,),
        sessions=sessions,
    )


def _file(*captures: Capture) -> UsageFile:
    return UsageFile(run=RUN, captures=captures)


def _write(path: Path, file: UsageFile) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_usage(file))
    return path


def _invoke(repo: Path, *argv: str):
    return runner.invoke(app, ["run", "cost", *argv], env={**os.environ, "VK_REPO_ROOT": str(repo)})


# --- the summarizer ---------------------------------------------------------


def test_steps_and_models_sum_across_sessions_and_keep_cursor_order() -> None:
    entries, replayed, _ = effective_entries(
        _file(
            _capture("a", "deliver", _entry("s1", 1.0, 3), _entry("s2", 0.5, 2, step="plan")),
        )
    )
    summary = summarize(entries, ["plan", "brainstorm", "deliver"])
    assert not replayed
    assert [(r.step, r.usd, r.turns) for r in summary.steps] == [
        ("plan", 0.5, 2),
        ("brainstorm", 1.0, 3),
        ("deliver", None, None),
    ]
    (model,) = summary.models
    assert model.cache_read == 60 and model.usd == pytest.approx(1.5)
    assert summary.total == pytest.approx(1.5)


def test_an_unpriced_session_is_none_never_zero() -> None:
    summary = summarize([_entry("s1", None, None)])
    assert summary.steps[0].usd is None and summary.steps[0].turns is None
    assert summary.total is None


def test_a_reading_beats_another_hosts_absence() -> None:
    entries, _, _ = effective_entries(
        _file(
            _capture("a", "deliver", _entry("s1", 1.0, 3)),
            _capture("b", "resolve:review", SessionEntry(session="s1", unavailable="elsewhere")),
        )
    )
    assert [e.unavailable for e in entries] == [None]


def test_live_captures_supersede_migrated_figures_of_the_steps_they_cover() -> None:
    migrated = _capture("(migrated)", "migrated", _entry("(main)", None, 9))
    live = _capture("a", "deliver", _entry("s1", 2.0, 4))
    entries, replayed, ignored = effective_entries(_file(migrated, live))
    assert [e.session for e in entries] == ["s1"] and not replayed and ignored == 1
    entries, replayed, ignored = effective_entries(_file(migrated))
    assert [e.session for e in entries] == ["(main)"] and replayed and ignored == 0


def test_a_live_capture_of_an_unrelated_session_keeps_the_migrated_figures() -> None:
    """p2-r22: supersede per session and per step, never wholesale — a live
    closeout session that covers no migrated step drops no migrated figure."""
    migrated = _capture(
        "(migrated)",
        "migrated",
        _entry("(main)", None, 9),
        _entry("agent-x", None, 5, step="plan"),
    )
    live = _capture("a", "closeout", _entry("closeout-session", 0.5, 2, step="deliver"))
    entries, replayed, ignored = effective_entries(_file(migrated, live))
    assert {e.session for e in entries} == {"(main)", "agent-x", "closeout-session"}
    assert not replayed and ignored == 0
    summary = summarize(entries, ["brainstorm", "plan", "deliver"])
    assert [(r.step, r.turns) for r in summary.steps] == [
        ("brainstorm", 9),
        ("plan", 5),
        ("deliver", 2),
    ]


def test_a_migrated_entry_is_superseded_by_a_live_reading_of_its_session() -> None:
    migrated = _capture("(migrated)", "migrated", _entry("agent-x", None, 5, step="plan"))
    live = _capture("a", "deliver", _entry("agent-x", 1.0, 0, step="deliver"))
    entries, _, ignored = effective_entries(_file(migrated, live))
    assert [(e.session, e.models["claude-opus-5-5"].usd) for e in entries] == [("agent-x", 1.0)]
    assert ignored == 1


def test_a_migrated_entry_is_trimmed_to_the_steps_no_live_reading_covers() -> None:
    main = SessionEntry(
        session="(main)",
        role="main",
        models={"unknown": ModelFigures(input=10)},
        steps={"brainstorm": Figure(turns=9), "plan": Figure(turns=3)},
    )
    migrated = _capture("(migrated)", "migrated", main)
    live = _capture("a", "resolve:brainstorm", _entry("s1", 1.0, 4))
    entries, _, ignored = effective_entries(_file(migrated, live))
    by_session = {e.session: e for e in entries}
    assert set(by_session["(main)"].steps) == {"plan"}
    # its tokens span a covered step and cannot be apportioned: not counted twice
    assert by_session["(main)"].models == {}
    assert ignored == 0


def test_the_command_says_how_many_migrated_entries_it_ignored(tmp_path: Path) -> None:
    migrated = _capture("(migrated)", "migrated", _entry("(main)", None, 9))
    live = _capture("a", "deliver", _entry("s1", 2.0, 4))
    _write(usage_path(tmp_path, RUN), _file(migrated, live))
    result = _invoke(tmp_path, RUN)
    assert result.exit_code == 0, result.output
    assert "1 migrated entries ignored" in " ".join(result.output.split())


# --- the command ------------------------------------------------------------


def test_the_command_reads_the_usage_file_on_a_checkout_that_never_ran_it(tmp_path: Path) -> None:
    path = _write(usage_path(tmp_path, RUN), _file(_capture("a", "deliver", _entry("s1", 1.25, 3))))
    before = path.read_bytes()

    result = _invoke(tmp_path, RUN)

    assert result.exit_code == 0, result.output
    for needle in ("brainstorm", "claude-opus-5-5", "$1.25", "1 read, 0 unavailable", "deliver@"):
        assert needle in result.output, needle
    assert path.read_bytes() == before, "read-only"


def test_the_archived_usage_file_is_read_when_the_active_one_is_gone(tmp_path: Path) -> None:
    _write(archived_usage_path(tmp_path, RUN), _file(_capture("a", "closeout", _entry("s", 2, 1))))
    result = _invoke(tmp_path, RUN)
    assert result.exit_code == 0, result.output
    assert "$2.00" in result.output


def test_an_unobserved_figure_prints_a_dash(tmp_path: Path) -> None:
    _write(usage_path(tmp_path, RUN), _file(_capture("a", "deliver", _entry("s1", None, None))))
    result = _invoke(tmp_path, RUN)
    assert result.exit_code == 0, result.output
    assert "—" in result.output
    assert "$0.00" not in result.output


def test_no_usage_recorded_exits_two_and_names_recompute(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "nope")
    assert result.exit_code == 2
    assert "--recompute" in " ".join(result.output.split())


def test_recompute_reads_this_hosts_transcripts_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "projects" / "-work-example"
    root.mkdir(parents=True)
    shutil.copy(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl", root)
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", CC_SESSION)
    save_run_state(
        tmp_path,
        RunState(
            run=RUN,
            workflow="fr-goal@1",
            branch="b",
            started="2026-09-21T11:00:00+00:00",
            cursor="deliver",
            steps={"brainstorm": StepRecord(state="done", at="2026-09-21T13:00:00+00:00")},
        ),
    )

    result = _invoke(tmp_path, RUN, "--recompute")

    assert result.exit_code == 0, result.output
    assert "recomputed" in result.output and "1 read" in result.output
    assert not usage_path(tmp_path, RUN).exists()
