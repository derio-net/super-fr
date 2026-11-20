"""`fr triage drive status` and `fr triage drive log` (spec 2026-11-19-batch-train-truth R14,
R22)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_drive_cmd
from fr.triage.drive_log import DriveLog
from fr.triage.driver_record import (
    DriverRecord,
    LastRefusal,
    save_record,
)
from fr.triage.lease import Lease, driver_identity, holder_of
from typer.testing import CliRunner

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
SCOPE = ["--repo", "example-org/widgets"]
HERE = "h-aaaa1111"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(triage_drive_cmd, "host_id", lambda: HERE)
    monkeypatch.setattr(triage_drive_cmd, "_now", lambda: NOW)


def _lease(tmp: Path, host: str = HERE, *, expires: timedelta = timedelta(hours=1)) -> None:
    lease = Lease(
        holder=holder_of("example-org--widgets", driver_identity("host", host)),
        started=NOW - timedelta(hours=2),
        expires=NOW + expires,
        last_pass=NOW - timedelta(minutes=3),
    )
    (tmp / "lease.yaml").write_text(
        "holder: {}\nstarted: {}\nexpires: {}\nlast_pass: {}\n".format(
            lease.holder, lease.started.isoformat(), lease.expires.isoformat(),
            lease.last_pass.isoformat() if lease.last_pass else "",
        )
    )  # fmt: skip


def _status(tmp: Path) -> Any:
    return CliRunner().invoke(app, ["triage", "drive", "status", *SCOPE, "--dir", str(tmp)])


def test_a_live_driver_exits_zero_and_the_block_names_its_facts(tmp_path: Path) -> None:
    _lease(tmp_path)
    save_record(
        tmp_path,
        DriverRecord(
            pid=os.getpid(), started=NOW - timedelta(hours=2), supervised=4321, restarts=2,
            last_crash="SIGKILL", last_pass=NOW - timedelta(minutes=1),
            last_refusal=LastRefusal(cause="lease-held", message="held", at=NOW - timedelta(days=1),
                                     fr_version="8.3.0", resume="run it again"),
        ),
    )  # fmt: skip
    result = _status(tmp_path)
    assert result.exit_code == 0, result.output
    out = result.output
    assert f"pid {os.getpid()}" in out and "alive" in out
    assert "supervised by pid 4321" in out
    assert "restarts: 2" in out and "SIGKILL" in out
    assert "last pass: 2026-11-19T11:59:00" in out
    assert "lease-held" in out and "run it again" in out


def test_an_unsupervised_driver_says_so(tmp_path: Path) -> None:
    _lease(tmp_path)
    save_record(tmp_path, DriverRecord(pid=os.getpid()))
    result = _status(tmp_path)
    assert result.exit_code == 0 and "not supervised" in result.output
    assert "last refusal: none" in result.output


def test_a_dead_pid_exits_three(tmp_path: Path) -> None:
    _lease(tmp_path)
    save_record(tmp_path, DriverRecord(pid=2**22 + 12345))  # no such process
    result = _status(tmp_path)
    assert result.exit_code == 3
    assert "not running" in result.output


def test_no_lease_and_no_record_exits_three(tmp_path: Path) -> None:
    result = _status(tmp_path)
    assert result.exit_code == 3
    assert "no driver holds" in result.output


def test_another_hosts_lease_is_not_probed_and_is_reported_as_held_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lease(tmp_path, host="h-bbbb2222")
    save_record(tmp_path, DriverRecord(pid=2**22 + 12345))  # would read dead if it were probed

    def boom(pid: int, sig: int) -> None:
        raise AssertionError("another host's pid must not be probed")

    monkeypatch.setattr(triage_drive_cmd.os, "kill", boom)
    result = _status(tmp_path)
    assert result.exit_code == 0
    assert "held elsewhere" in result.output and "h-bbbb2222" in result.output


def test_an_expired_lease_on_another_host_is_no_driver(tmp_path: Path) -> None:
    _lease(tmp_path, host="h-bbbb2222", expires=-timedelta(minutes=1))
    assert _status(tmp_path).exit_code == 3


def test_status_writes_nothing(tmp_path: Path) -> None:
    _lease(tmp_path)
    save_record(tmp_path, DriverRecord(pid=os.getpid()))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    _status(tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


# ------------------------------------------------------------------------------- the log


def _log(tmp: Path, *args: str) -> Any:
    return CliRunner().invoke(app, ["triage", "drive", "log", *SCOPE, "--dir", str(tmp), *args])


def test_log_prints_the_last_fifty_lines_by_default_and_n_lines_on_request(
    tmp_path: Path,
) -> None:
    log = DriveLog(tmp_path)
    for i in range(60):
        log.append("action", f"entry {i}", NOW)
    lines = _log(tmp_path).output.splitlines()
    assert len(lines) == 50 and lines[0].endswith("entry 10") and lines[-1].endswith("entry 59")
    lines = _log(tmp_path, "-n", "2").output.splitlines()
    assert [x.rsplit(" ", 1)[1] for x in lines] == ["58", "59"]


def test_log_with_no_file_says_no_driver_has_run(tmp_path: Path) -> None:
    result = _log(tmp_path)
    assert result.exit_code == 0 and "no driver has run" in result.output


def test_log_follow_prints_what_is_appended_until_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = DriveLog(tmp_path)
    log.append("action", "before", NOW)
    steps = iter(["one", "two"])

    def sleep(_: float) -> None:
        try:
            log.append("pass", next(steps), NOW)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(triage_drive_cmd, "_follow_sleep", sleep)
    result = _log(tmp_path, "-f", "-n", "1")
    lines = result.output.splitlines()
    assert [x.rsplit(" ", 1)[1] for x in lines] == ["before", "one", "two"]
    assert result.exit_code == 0  # an interrupt is how follow ends
