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
        SessionEntry(session=CC_SESSION, steps={"brainstorm": Figure(turns=6, usd=1.5)}),
    )

    cost = _cost(render_pr_body(repo, load_run_state(repo, RUN)))

    assert "| brainstorm | 6 | $1.50 |" in cost
    assert "no cost recorded yet" not in cost
