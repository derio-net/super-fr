"""Journal `created` stamps carry their offset (super-fr#625).

A naive stamp loses the writer's zone, and the reader can only guess its own:
a review written in a UTC container, read on a UTC+9 host, lands nine hours
early and `fr run resolve` refuses it; west of UTC a stale one is accepted.
Every test here pins the WRITER's zone and the READER's zone separately,
because a single shared TZ is exactly the case that hid the bug.
"""

from __future__ import annotations

import datetime as _dt
import re
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fr.journal.model import journal_stamp_as_utc
from fr.run.telemetry import parse_timestamp

from tests.unit.test_run_evidence_separate_context import (
    _REVIEW,
    _at_the_spec_review,
    _spec_journal,
    _spec_review,
)

_SRC = Path(__file__).resolve().parents[2] / "packages" / "fr" / "src" / "fr"
# Every module that stamps a journal entry's `created`.
_WRITER_MODULES = ("commands/journal_cmd.py", "record/apply.py", "commands/run_cmd.py")


def _journal_cmd_stamp() -> str:
    from fr.commands.journal_cmd import _timestamp

    return _timestamp()


def _record_stamp() -> str:
    from fr.record.apply import _stamp

    return _stamp()


@pytest.fixture
def _restore_tz(monkeypatch: pytest.MonkeyPatch):
    yield
    monkeypatch.undo()
    time.tzset()


def _in_zone(monkeypatch: pytest.MonkeyPatch, zone: str) -> None:
    monkeypatch.setenv("TZ", zone)
    time.tzset()


@pytest.mark.parametrize("writer", [_journal_cmd_stamp, _record_stamp])
@pytest.mark.parametrize("reader_zone", ["Asia/Tokyo", "America/Los_Angeles"])
def test_a_stamp_written_in_utc_reads_as_the_same_instant_in_another_zone(
    monkeypatch: pytest.MonkeyPatch, _restore_tz: None,
    writer: Callable[[], str], reader_zone: str,
) -> None:  # fmt: skip
    _in_zone(monkeypatch, "UTC")
    before = _dt.datetime.now(_dt.UTC).replace(microsecond=0)
    stamp = writer()
    after = _dt.datetime.now(_dt.UTC)

    _in_zone(monkeypatch, reader_zone)
    read = parse_timestamp(journal_stamp_as_utc(stamp))

    assert read is not None
    assert before <= read <= after, f"{stamp!r} read in {reader_zone} as {read}"


@pytest.mark.parametrize("module", _WRITER_MODULES)
def test_no_journal_writer_stamps_naive_local_time(module: str) -> None:
    """The third writer (`fr run`'s decision entry) is inline, so it is pinned
    by source: a bare `datetime.now()` anywhere in a writer module is a stamp
    with no zone."""
    text = (_SRC / module).read_text()
    assert not re.search(r"datetime\.now\(\)", text), f"{module} calls naive datetime.now()"


def test_a_review_written_in_a_utc_container_is_accepted_on_a_utc_plus_9_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _restore_tz: None
) -> None:
    _in_zone(monkeypatch, "UTC")
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, {**_REVIEW, "created": _journal_cmd_stamp()})

    _in_zone(monkeypatch, "Asia/Tokyo")
    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 0, result.output
