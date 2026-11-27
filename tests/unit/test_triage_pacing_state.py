"""`pacing.json` (spec 2026-10-12-quota-pacing R15)."""

from __future__ import annotations

import json
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
        summary={"in_flight": 1, "merged": 2, "pending": 0, "closing": 0},
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


def test_a_negative_backoff_is_not_usable(tmp_path: Path) -> None:
    """p1-r1: a persisted negative backoff is refused like any wrong shape."""
    (tmp_path / pacing_state.PACING_FILE).write_text('{"backoff": -3}', encoding="utf-8")
    state, warning = pacing_state.load(tmp_path)
    assert state == PacingState()
    assert warning is not None


def test_a_binary_file_is_an_empty_state_and_a_warning(tmp_path: Path) -> None:
    """p1-r6: non-UTF-8 bytes (a UnicodeDecodeError, a ValueError) must not crash."""
    (tmp_path / pacing_state.PACING_FILE).write_bytes(b"\xff\xfe\x00\x80binary")
    state, warning = pacing_state.load(tmp_path)
    assert state == PacingState()
    assert warning is not None


def test_an_unusable_summary_is_no_summary(tmp_path: Path) -> None:
    (tmp_path / pacing_state.PACING_FILE).write_text('{"summary": {"pending": "x"}}')
    state, warning = pacing_state.load(tmp_path)
    assert state.summary is None and warning is None


def test_a_summary_with_a_key_the_summary_does_not_have_is_no_summary(tmp_path: Path) -> None:
    """p2-r7: a quiet pass builds the pass summary from this record, so a key it does not
    know (or one it requires, missing) drops the record and the next pass plans."""
    (tmp_path / pacing_state.PACING_FILE).write_text(
        '{"summary": {"in_flight": 1, "merged": 0, "pending": 0, "closing": 0, "bogus": 1}}',
        encoding="utf-8",
    )
    assert pacing_state.load(tmp_path)[0].summary is None
    (tmp_path / pacing_state.PACING_FILE).write_text(
        '{"summary": {"in_flight": 1}}', encoding="utf-8"
    )
    assert pacing_state.load(tmp_path)[0].summary is None


def test_held_for_quota_round_trips_and_a_bad_value_is_false(tmp_path: Path) -> None:
    """p2-r3: whether the last planned pass held its dispatches for the quota."""
    pacing_state.save(tmp_path, PacingState(held_for_quota=True))
    assert pacing_state.load(tmp_path)[0].held_for_quota is True
    (tmp_path / pacing_state.PACING_FILE).write_text('{"held_for_quota": "yes"}')
    assert pacing_state.load(tmp_path)[0].held_for_quota is False


def test_planned_at_round_trips_and_a_bad_value_is_none(tmp_path: Path) -> None:
    """R7 of spec 2026-11-27-queue-followups: `planned_at` is parsed on its own, so a bad
    value is unknown and the rest of the state is kept."""
    summary = {"in_flight": 1, "merged": 2, "pending": 0, "closing": 0}
    state = PacingState(etags={"o/r": {"p": "e"}}, planned_at=AT, summary=summary)
    pacing_state.save(tmp_path, state)
    loaded, warning = pacing_state.load(tmp_path)
    assert loaded == state and warning is None
    path = tmp_path / pacing_state.PACING_FILE
    data = json.loads(path.read_text("utf-8"))
    data["planned_at"] = "garbage"
    path.write_text(json.dumps(data), "utf-8")
    loaded, warning = pacing_state.load(tmp_path)
    assert warning is None and loaded.planned_at is None
    assert loaded.etags == state.etags and loaded.summary == state.summary
