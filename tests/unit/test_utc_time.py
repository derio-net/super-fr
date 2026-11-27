"""R8: `fr.utc_time.parse_as_utc`, the naive-as-UTC reader."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fr.utc_time import parse_as_utc


@pytest.mark.parametrize("value", [None, "", 5, b"2026-11-27T10:00:00", "not a time"])
def test_missing_empty_non_string_or_garbage_is_none(value: object) -> None:
    assert parse_as_utc(value) is None


def test_zulu_is_utc() -> None:
    assert parse_as_utc("2026-11-27T10:00:00Z") == datetime(2026, 11, 27, 10, tzinfo=UTC)


def test_a_naive_time_is_read_as_utc() -> None:
    parsed = parse_as_utc("2026-11-27T10:00:00")
    assert parsed == datetime(2026, 11, 27, 10, tzinfo=UTC)
    assert parsed is not None and parsed.utcoffset() == timedelta(0)


def test_an_offset_is_kept() -> None:
    parsed = parse_as_utc("2026-11-27T10:00:00+02:00")
    assert parsed is not None and parsed.utcoffset() == timedelta(hours=2)
