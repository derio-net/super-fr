"""The driver's record of the merges it stopped on (gh#987): `merge-stops.json`."""

from __future__ import annotations

from pathlib import Path

from fr.triage.merge_stops import (
    MERGE_STOPS_FILE,
    MergeStop,
    clear_stop,
    load_stops,
    record_stop,
)


def test_no_file_is_no_stops(tmp_path: Path) -> None:
    assert load_stops(tmp_path) == {}


def test_a_recorded_stop_reads_back_and_clears(tmp_path: Path) -> None:
    record_stop(tmp_path, "a", MergeStop(head="sha-1", reason="conflict: x.py", at="t1"))
    record_stop(tmp_path, "b", MergeStop(head="sha-2", reason="draft", at="t2"))
    assert load_stops(tmp_path)["a"] == MergeStop(head="sha-1", reason="conflict: x.py", at="t1")
    clear_stop(tmp_path, "a")
    assert set(load_stops(tmp_path)) == {"b"}


def test_clearing_a_batch_with_no_stop_writes_nothing(tmp_path: Path) -> None:
    clear_stop(tmp_path, "a")
    assert not (tmp_path / MERGE_STOPS_FILE).exists()


def test_an_unreadable_file_is_no_stops_never_an_error(tmp_path: Path) -> None:
    """The board is a view: a damaged record must not stop it rendering."""
    (tmp_path / MERGE_STOPS_FILE).write_text("{not json", encoding="utf-8")
    assert load_stops(tmp_path) == {}
    (tmp_path / MERGE_STOPS_FILE).write_text('{"schema": 1, "stops": {"a": 3}}', "utf-8")
    assert load_stops(tmp_path) == {}
