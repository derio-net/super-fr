"""The drive lease: one driver per scope (spec 2026-10-07-cloud-triage R9, §D, Test Plan 8).

`lease.yaml` rides on the state ref; taking or renewing it is a write followed by the
compare-and-swap push, so of two drivers that read the same old ref the second push fails.
Every remote here is a bare repo under `tmp_path`.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd
from fr.triage import lease
from fr.triage.lease import (
    Lease,
    LeaseExpired,
    LeaseHeld,
    acquire,
    driver_identity,
    lease_duration,
    load_lease,
    release,
    take_or_renew,
)
from fr.triage.model import Scope
from fr.triage.scope_config import scope_id
from fr.triage.state_ref import StateRefConflict, fetch_state, push_state, read_base, ref_name
from typer.testing import CliRunner

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
SID = "s-0123abcd"
HOST = driver_identity("host", "0123456789abcdef")
CLOUD = driver_identity("cloud", "0123456789abcdef")
OTHER = driver_identity("cloud", "fedcba9876543210")
DUR = lease_duration()


# ------------------------------------------------------------------ the model


def test_the_identity_strings_name_the_kind_and_the_host_id() -> None:
    assert HOST == "host:0123456789abcdef"
    assert CLOUD == "cloud:0123456789abcdef"
    with pytest.raises(ValueError):
        driver_identity("pod", "0123456789abcdef")  # type: ignore[arg-type]


def test_the_duration_is_three_wake_intervals_plus_the_routine_period() -> None:
    assert lease_duration(interval_min=5, routine_min=60) == timedelta(minutes=75)
    assert lease_duration() == timedelta(minutes=75)
    assert lease_duration(interval_min=10, routine_min=30) == timedelta(minutes=60)
    assert lease_duration(interval_min=0.5, routine_min=0) == timedelta(seconds=90)


def test_a_free_lease_is_taken_and_written_to_lease_yaml(tmp_path: Path) -> None:
    got = take_or_renew(tmp_path, HOST, NOW, scope_id=SID)

    assert got == Lease(holder=f"{SID} {HOST}", started=NOW, expires=NOW + DUR)
    assert load_lease(tmp_path) == got
    assert "holder:" in (tmp_path / "lease.yaml").read_text()


def test_the_same_holder_renews_and_keeps_its_start(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)
    later = NOW + timedelta(minutes=5)

    got = take_or_renew(tmp_path, HOST, later, scope_id=SID)

    assert (got.started, got.expires) == (NOW, later + DUR)


def test_the_same_holder_renews_its_own_expired_lease(tmp_path: Path) -> None:
    take_or_renew(tmp_path, CLOUD, NOW, scope_id=SID)
    late = NOW + DUR + timedelta(hours=3)

    got = take_or_renew(tmp_path, CLOUD, late, scope_id=SID)

    assert got.holder == f"{SID} {CLOUD}" and got.expires == late + DUR


def test_a_rehomed_cloud_driver_with_the_same_host_id_is_the_same_holder(tmp_path: Path) -> None:
    """A new session (new pid, new container) keeps the host id its brief carries."""
    take_or_renew(tmp_path, driver_identity("cloud", "0123456789abcdef"), NOW, scope_id=SID)

    got = take_or_renew(
        tmp_path, driver_identity("cloud", "0123456789abcdef"), NOW + timedelta(1), scope_id=SID
    )

    assert got.started == NOW


def test_another_holder_is_refused_while_the_lease_is_live(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)
    before = (tmp_path / "lease.yaml").read_bytes()

    with pytest.raises(LeaseHeld) as caught:
        take_or_renew(tmp_path, OTHER, NOW + timedelta(minutes=1), scope_id=SID)

    message = str(caught.value)
    assert f"{SID} {HOST}" in message and (NOW + DUR).isoformat() in message
    assert caught.value.lease.holder == f"{SID} {HOST}"
    assert (tmp_path / "lease.yaml").read_bytes() == before


def test_an_expired_foreign_lease_is_reported_and_not_taken(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)
    before = (tmp_path / "lease.yaml").read_bytes()

    with pytest.raises(LeaseExpired) as caught:
        take_or_renew(tmp_path, OTHER, NOW + DUR + timedelta(seconds=1), scope_id=SID)

    assert "fr triage lease take" in str(caught.value) and "--yes" in str(caught.value)
    assert f"{SID} {HOST}" in str(caught.value)
    assert (tmp_path / "lease.yaml").read_bytes() == before


def test_force_takes_a_foreign_lease_live_or_expired(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)

    got = take_or_renew(tmp_path, OTHER, NOW + timedelta(minutes=1), scope_id=SID, force=True)

    assert got.holder == f"{SID} {OTHER}" and got.started == NOW + timedelta(minutes=1)


def test_release_removes_only_the_holders_own_lease(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)
    assert release(tmp_path, OTHER, scope_id=SID) is False
    assert load_lease(tmp_path) is not None
    assert release(tmp_path, HOST, scope_id=SID) is True
    assert load_lease(tmp_path) is None


def test_an_unreadable_lease_is_refused_never_replaced(tmp_path: Path) -> None:
    (tmp_path / "lease.yaml").write_text("holder: [not, a, string]\n")

    with pytest.raises(lease.TriageError):
        take_or_renew(tmp_path, HOST, NOW, scope_id=SID)


def test_the_last_pass_is_kept_across_a_renewal(tmp_path: Path) -> None:
    take_or_renew(tmp_path, CLOUD, NOW, scope_id=SID)
    lease.mark_pass(tmp_path, NOW)

    got = take_or_renew(tmp_path, CLOUD, NOW + timedelta(minutes=1), scope_id=SID)

    assert got.last_pass == NOW


# ---------------------------------------------- acquire: write, then the CAS push


class _Private:
    def repo_visibility(self, repo: str) -> str:
        return "private"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _workspace(tmp_path: Path, name: str) -> Path:
    ws = tmp_path / name
    _git(tmp_path, "init", "--quiet", str(ws))
    state = ws / ".fr" / "triage-state" / "o--r"
    state.mkdir(parents=True)
    return state


def _pusher(state: Path, remote: Path) -> Any:
    def push() -> str:
        url = str(remote)
        return push_state(
            state,
            url,
            SID,
            expected_old=read_base(state, remote=url, ref=ref_name(SID)),
            scope=Scope(kind="repo", target="o/r"),
            state_repo="o/r",
            client=_Private(),
        )

    return push


def test_two_drivers_reading_the_same_old_ref_the_second_push_fails(tmp_path: Path) -> None:
    remote = tmp_path / "state.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(remote))
    a, b = _workspace(tmp_path, "a"), _workspace(tmp_path, "b")
    (a / "judgements.yaml").write_text("schema: 6\n")
    _pusher(a, remote)()  # the old ref both drivers read
    assert fetch_state(b, str(remote), SID) is not None
    old = read_base(a)

    acquire(a, HOST, NOW, scope_id=SID, push=_pusher(a, remote))
    with pytest.raises(StateRefConflict):
        acquire(b, OTHER, NOW, scope_id=SID, push=_pusher(b, remote))

    on_remote = _git(remote, "show", f"{ref_name(SID)}:lease.yaml")
    assert f"{SID} {HOST}" in on_remote
    assert read_base(a) != old
    assert load_lease(b) is None, "the loser's lease write is taken back"


def test_a_lost_push_restores_the_previous_lease_bytes(tmp_path: Path) -> None:
    take_or_renew(tmp_path, HOST, NOW, scope_id=SID)
    before = (tmp_path / "lease.yaml").read_bytes()

    def refused() -> str:
        raise StateRefConflict("moved")

    with pytest.raises(StateRefConflict):
        acquire(tmp_path, HOST, NOW + timedelta(minutes=5), scope_id=SID, push=refused)

    assert (tmp_path / "lease.yaml").read_bytes() == before


# ------------------------------------------------- fr triage lease show|take


@pytest.fixture
def scoped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FR_HOST_ID", "0123456789abcdef")
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: _Private())
    return tmp_path / "state"


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(app, ["triage", "lease", *args])


def test_lease_show_says_free_then_names_the_holder(scoped: Path) -> None:
    result = _invoke("show", "--repo", "o/r", "--dir", str(scoped))
    assert result.exit_code == 0, result.output
    assert "free" in result.output

    sid = scope_id(Scope(kind="repo", target="o/r"))
    take_or_renew(scoped, OTHER, NOW, scope_id=sid)
    result = _invoke("show", "--repo", "o/r", "--dir", str(scoped))
    assert result.exit_code == 0, result.output
    assert f"{sid} {OTHER}" in result.output and (NOW + DUR).isoformat() in result.output


def test_lease_take_without_yes_changes_nothing(scoped: Path) -> None:
    sid = scope_id(Scope(kind="repo", target="o/r"))
    take_or_renew(scoped, OTHER, NOW, scope_id=sid)
    before = (scoped / "lease.yaml").read_bytes()

    result = _invoke("take", "--repo", "o/r", "--dir", str(scoped))

    assert result.exit_code == 2, result.output
    assert "--yes" in result.output and f"{sid} {OTHER}" in result.output
    assert (scoped / "lease.yaml").read_bytes() == before


def test_lease_take_yes_takes_it_for_this_host(scoped: Path) -> None:
    sid = scope_id(Scope(kind="repo", target="o/r"))
    take_or_renew(scoped, OTHER, NOW, scope_id=sid)

    result = _invoke("take", "--yes", "--repo", "o/r", "--dir", str(scoped))

    assert result.exit_code == 0, result.output
    got = load_lease(scoped)
    assert got is not None and got.holder == f"{sid} host:0123456789abcdef"

    result = _invoke("take", "--yes", "--as", "cloud", "--repo", "o/r", "--dir", str(scoped))
    got = load_lease(scoped)
    assert got is not None and got.holder == f"{sid} cloud:0123456789abcdef"


# ------------------------------------------------------- the generation (§D, p6-r4)


def test_a_lease_with_no_generation_reads_as_generation_zero_and_is_written_without_one(
    tmp_path: Path,
) -> None:
    (tmp_path / lease.LEASE_FILE).write_text(
        f"holder: {SID} {CLOUD}\nstarted: '{NOW.isoformat()}'\nexpires: '{NOW.isoformat()}'\n"
    )
    assert load_lease(tmp_path).generation == 0  # type: ignore[union-attr]

    take_or_renew(tmp_path, CLOUD, NOW, scope_id=SID)
    assert "generation" not in (tmp_path / lease.LEASE_FILE).read_text()


def test_a_bumped_generation_survives_a_renewal_and_a_newer_session_raises_it(
    tmp_path: Path,
) -> None:
    take_or_renew(tmp_path, CLOUD, NOW, scope_id=SID)
    assert lease.bump_generation(tmp_path).generation == 1
    assert "generation: 1" in (tmp_path / lease.LEASE_FILE).read_text()

    renewed = take_or_renew(tmp_path, CLOUD, NOW + timedelta(minutes=5), scope_id=SID)
    assert renewed.generation == 1, "an older session's renewal never lowers it"
    raised = take_or_renew(tmp_path, CLOUD, NOW, scope_id=SID, generation=3)
    assert raised.generation == 3
