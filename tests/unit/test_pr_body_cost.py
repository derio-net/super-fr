"""The PR body's `## Cost` table reads this host's sessions LIVE (gh#680).

`deliver` renders the body before its own capture runs, so a table built from
the usage file alone showed only what the first capture on this host saw —
the brainstorm — and `—` for every later step. The render now folds a live,
in-memory reading of this host's sessions over the file, and writes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.record.pr_body import render_pr_body
from fr.run.model import load_run_state
from fr.usage.file import Figure, ModelFigures, SessionEntry, load_usage, usage_path

from tests.unit.test_usage_capture import (  # noqa: F401 — `transcripts` is a fixture
    CC_SESSION,
    RUN,
    _setup,
    _step,
    transcripts,
)


def _live(monkeypatch: pytest.MonkeyPatch, entry: SessionEntry) -> None:
    """What reading this host's transcripts returns NOW, whatever the file says."""
    import fr.usage.capture

    monkeypatch.setattr(fr.usage.capture, "session_entry", lambda *a, **k: entry)


def _cost(body: str) -> str:
    return body.split("## Cost", 1)[1]


@pytest.mark.usefixtures("transcripts")
def test_the_cost_table_counts_steps_the_file_has_not_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review"):
        assert _step(repo, shipped, step).exit_code == 0
    stale = load_usage(usage_path(repo, RUN))
    assert stale is not None and [c.at for c in stale.captures] == [("resolve:brainstorm",)]
    before = usage_path(repo, RUN).read_bytes()
    _live(
        monkeypatch,
        SessionEntry(
            session=CC_SESSION,
            steps={
                "brainstorm": Figure(turns=6),
                "plan": Figure(turns=7),
                "review": Figure(turns=12),
            },
            models={"m": ModelFigures(input=1, output=1)},
        ),
    )

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "| plan | 7 |" in cost, cost
    assert "| review | 12 |" in cost, cost
    assert "Sessions: 1 read, 0 unavailable." in cost
    # a render is a read: the capture is deliver's to write, after its gate
    assert usage_path(repo, RUN).read_bytes() == before


@pytest.mark.usefixtures("transcripts")
def test_turns_without_dollars_say_why_the_dollars_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _step(repo, shipped, "brainstorm").exit_code == 0
    _live(monkeypatch, SessionEntry(session=CC_SESSION, steps={"brainstorm": Figure(turns=6)}))

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "| **total** | | — |" in cost
    assert "no cost recorded yet" in cost, cost


@pytest.mark.usefixtures("transcripts")
def test_dollars_present_carry_no_missing_dollars_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _step(repo, shipped, "brainstorm").exit_code == 0
    _live(
        monkeypatch,
        SessionEntry(
            session=CC_SESSION,
            steps={"brainstorm": Figure(turns=6, usd=1.5)},
            models={"m": ModelFigures(output=1, usd=1.5, usd_source="exact")},
        ),
    )

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "| brainstorm | 6 | $1.50 |" in cost
    assert "no cost recorded yet" not in cost


# --- spec 2026-10-06-cost-evidence §E (R9): both tables in Markdown ----------


def _split_entry(usd: float | None) -> SessionEntry:
    def fig(turns: int, read: int, out: int) -> Figure:
        return Figure(usd=usd, turns=turns, cache_read=read, output=out)

    return SessionEntry(
        session=CC_SESSION,
        steps={"brainstorm": Figure(turns=6, usd=usd)},
        steps_by_role={
            "main": {"brainstorm": fig(4, 1_200_000, 34_000)},
            "subagent": {"brainstorm": fig(2, 500, 20)},
        },
        units={
            "phase/1/implement-phase": {
                "executor": fig(10, 2_000, 100),
                "orchestrator": fig(1, 5, 5),
            },
            "phase/1/review-phase": {"reviewer": fig(3, 300, 30), "orchestrator": fig(1, 5, 5)},
        },
        models={"m": ModelFigures(output=1, usd=usd, usd_source="exact" if usd else "none")},
    )


@pytest.mark.usefixtures("transcripts")
def test_the_cost_section_carries_the_role_split_step_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _step(repo, shipped, "brainstorm").exit_code == 0
    _live(monkeypatch, _split_entry(1.5))

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "main turns | main cache-read / output | main cost" in cost, cost
    assert "subagent turns | subagent cache-read / output | subagent cost" in cost
    assert "| brainstorm | 6 | $1.50 | 4 | 1.2M / 34k | $1.50 | 2 | 500 / 20 | $1.50 |" in cost


@pytest.mark.usefixtures("transcripts")
def test_the_cost_section_carries_the_per_phase_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _step(repo, shipped, "brainstorm").exit_code == 0
    _live(monkeypatch, _split_entry(None))

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "| phase | tier | bound | ran |" in cost, cost
    assert "executor turns" in cost and "reviewer turns" in cost
    assert "orchestrator cost" in cost
    # no attempt recorded: tier/bound/ran `—`; unpriced: tokens and turns, dollars `—`
    assert "| 1 | — | — | — | 10 | 2.0k / 100 | — | 3 | 300 / 30 | — | 2 | 10 / 10 | — |" in cost


def test_the_phase_markdown_marks_a_mismatch() -> None:
    from fr.record.pr_body import cost_markdown
    from fr.run.cost import PhaseRow, Summary

    row = PhaseRow(
        phase=2, tier="hard", bound="claude-opus-5", ran="claude-sonnet-5", mismatch=True
    )
    text = cost_markdown(Summary(), [row], RUN)
    assert "| 2 | hard | claude-opus-5 | claude-sonnet-5 ≠ |" in text
