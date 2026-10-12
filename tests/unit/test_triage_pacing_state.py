"""`pacing.json` (spec 2026-10-12-quota-pacing R15)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fr.triage import pacing_state, state_ref
from fr.triage.pacing_state import PacingState

AT = datetime(2026, 10, 12, 16, 30, tzinfo=UTC)


def test_state_round_trips(tmp_path: Path) -> None:
    state = PacingState(
        etags={"o/r": {"repos/o/r/issues": 'W/"abc"'}},
        full_at=AT,
        wait_until=AT,
        backoff=2,
        next_pass_at=AT,
        judgements_digest="d1",
        budget={"resource": "graphql", "remaining": 5, "limit": 5000, "reset": AT.isoformat()},
    )
    pacing_state.save(tmp_path, state)
    loaded, warning = pacing_state.load(tmp_path)
    assert loaded == state and warning is None


def test_a_missing_file_is_an_empty_state(tmp_path: Path) -> None:
    assert pacing_state.load(tmp_path) == (PacingState(), None)


def test_unreadable_json_is_an_empty_state_and_a_warning(tmp_path: Path) -> None:
    (tmp_path / pacing_state.PACING_FILE).write_text("{not json")
    state, warning = pacing_state.load(tmp_path)
    assert state == PacingState()
    assert warning is not None and "pacing.json" in warning


def test_a_wrong_shape_is_an_empty_state_and_a_warning(tmp_path: Path) -> None:
    (tmp_path / pacing_state.PACING_FILE).write_text('{"etags": [1], "backoff": "x"}')
    state, warning = pacing_state.load(tmp_path)
    assert state == PacingState() and warning


def test_save_creates_the_state_dir_and_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "scope"
    pacing_state.save(target, PacingState(backoff=1))
    assert [p.name for p in target.iterdir()] == ["pacing.json"]


def test_pacing_json_stays_out_of_the_state_ref() -> None:
    assert "pacing.json" not in state_ref.REF_FILES
