"""The drive activity log (spec 2026-11-19-batch-train-truth R22)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import fr.commands.triage_batch_cmd as batch
import pytest
from fr.triage.drive_log import LOG_FILE, DriveLog

NOW = datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)


def test_append_writes_a_timestamp_a_kind_and_the_line(tmp_path: Path) -> None:
    DriveLog(tmp_path).append("pass", "3 done", NOW)
    assert (tmp_path / LOG_FILE).read_text() == "2026-11-19T12:00:05Z pass 3 done\n"


def test_a_multi_line_message_is_one_entry(tmp_path: Path) -> None:
    DriveLog(tmp_path).append("transient", "a\n  b\nc", NOW)
    assert DriveLog(tmp_path).tail() == ["2026-11-19T12:00:05Z transient a b c"]


def test_a_write_that_would_pass_the_limit_rotates_keeping_one_previous(tmp_path: Path) -> None:
    log = DriveLog(tmp_path, limit=120)
    for i in range(12):
        log.append("action", f"line {i:02d}", NOW)
    assert (tmp_path / "drive.log.1").exists()
    assert not (tmp_path / "drive.log.2").exists()
    assert (tmp_path / LOG_FILE).stat().st_size <= 120
    # the newest line is in the live file; one previous file holds the older ones
    assert log.tail(1)[0].endswith("line 11")


def test_tail_spans_the_rotation_boundary_and_returns_the_newest_n(tmp_path: Path) -> None:
    log = DriveLog(tmp_path, limit=100)
    for i in range(8):
        log.append("action", f"n{i}", NOW)
    got = log.tail(5)
    assert [x.rsplit(" ", 1)[1] for x in got] == ["n3", "n4", "n5", "n6", "n7"]
    assert (tmp_path / "drive.log.1").exists()
    assert DriveLog(tmp_path / "none").tail() == []


def test_follow_yields_lines_appended_after_a_rotation(tmp_path: Path) -> None:
    log = DriveLog(tmp_path, limit=100)
    log.append("action", "old", NOW)
    steps = iter(["a", "b", "c", "d", "e"])
    seen: list[str] = []

    def poll(_: float) -> None:  # the fake clock: each wait appends one line
        try:
            log.append("action", next(steps) * 20, NOW)
        except StopIteration:
            raise KeyboardInterrupt from None

    with pytest.raises(KeyboardInterrupt):
        for line in log.follow(sleep=poll):
            seen.append(line)
    assert [x.rsplit(" ", 1)[1] for x in seen] == [c * 20 for c in "abcde"]
    assert (tmp_path / "drive.log.1").exists()  # it did rotate while followed


class _Console:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, line: str, **_: object) -> None:
        self.lines.append(line)


def test_say_prints_and_appends_only_while_a_log_is_attached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _Console()
    monkeypatch.setattr(batch, "console", out)
    monkeypatch.setattr(batch, "_now", lambda: NOW)
    batch._emit("action", "no log attached")  # plan mode and --once: unchanged output
    assert not (tmp_path / LOG_FILE).exists()
    with batch.drive_log_attached(DriveLog(tmp_path)):
        batch._emit("pass", "attached")
        batch._say("also routed")
    batch._emit("pass", "detached again")
    assert out.lines == ["no log attached", "attached", "also routed", "detached again"]
    assert DriveLog(tmp_path).tail() == [
        "2026-11-19T12:00:05Z pass attached",
        "2026-11-19T12:00:05Z action also routed",
    ]


def test_a_log_that_cannot_be_written_never_stops_the_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _Console()
    monkeypatch.setattr(batch, "console", out)
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the state directory should be")
    with batch.drive_log_attached(DriveLog(blocked)):
        batch._emit("pass", "still printed")
    assert out.lines == ["still printed"]


def test_the_supervisors_restart_line_lands_in_the_same_file(tmp_path: Path) -> None:
    from fr.triage.supervise import Supervisor

    sup = Supervisor(lambda pid: ["true"], tmp_path, now=lambda: NOW + timedelta(seconds=1))
    sup._say("restart", "the driver crashed (SIGKILL); restart 1 in 5s")
    log = DriveLog(tmp_path)
    log.append("pass", "from the driver", NOW)
    assert [x.split(" ", 2)[1] for x in log.tail()] == ["restart", "pass"]
