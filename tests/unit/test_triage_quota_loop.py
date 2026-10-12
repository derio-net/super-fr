# ruff: noqa: F811 - pytest fixtures imported from the sibling test modules
"""The drive waits for the reset instead of spending the exhausted budget (spec
2026-10-12-quota-pacing R2-R5, R16).

The loop cases drive `_host_loop` with a stub driver, a fake clock that `_sleep` advances
and a fake `/rate_limit`, so a wait is a number in a list; the lease and CLI cases use the
leased-drive world of `test_triage_driver_pass`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage import pacing_state
from fr.triage.errors import ForgeError
from fr.triage.lease import (
    DEFAULT_ROUTINE_MIN,
    driver_identity,
    lease_duration,
    load_lease,
    take_or_renew,
)
from fr.triage.model import Facts, Skipped
from fr.triage.pacing_state import PacingState
from typer.testing import CliRunner

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    checkout_fixture,
    runner_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import (  # noqa: F401 - fixtures
    HOST_ID,
    SCOPE,
    Runners,
    _pass,
    _ref,
    _workspace,
    _world,
    clock,
    remote,
    runners,
    visibility,
)
from tests.unit.triage_fixtures import rate_limit_answer

RATE_LIMITED = "GraphQL: API rate limit exceeded for user ID 1."
SECONDARY = "You have exceeded a secondary rate limit (HTTP 403)"
from fr.triage.scope_config import scope_id  # noqa: E402


def _reset(minutes: float) -> int:
    return int((NOW + timedelta(minutes=minutes)).timestamp())


def _exhausted(minutes: float) -> dict[str, Any]:
    return rate_limit_answer(graphql=0, reset=_reset(minutes))


class Meter:
    """`/rate_limit`: each read answers the next scripted answer (the last repeats)."""

    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers) or [rate_limit_answer()]
        self.reads = 0

    def rate_limit(self) -> dict[str, Any]:
        self.reads += 1
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def now(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    """A clock only `_sleep` moves; `sleeps` is what the loop waited, in order."""
    clock_: list[datetime] = [NOW]
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: clock_[0])
    return clock_


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch, now: list[datetime]) -> list[float]:
    out: list[float] = []

    def nap(seconds: float) -> None:
        out.append(seconds)
        now[0] += timedelta(seconds=seconds)
        assert len(out) < 20, "the loop did not end"

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    return out


class StubDriver:
    yes = True
    restart_to = None

    def __init__(self, target: Path) -> None:
        self.target = target
        self.read_failures: set[str] = set()
        self.leased = False
        self.renewed = 0

    def observation_owed(self) -> bool:
        return False

    def warn_single_pass(self) -> None:
        pass

    def take_lease(self) -> None:
        self.renewed += 1


def _summary(*, done: bool) -> SimpleNamespace:
    return SimpleNamespace(done=done, stalled=False)


def _script(
    monkeypatch: pytest.MonkeyPatch, now: list[datetime], *outcomes: str | bool
) -> list[datetime]:
    """one_pass: each call takes the next outcome — a rate-limit text raises, True ends the
    drive, False is a clean pass with work left. Returns when each call happened."""
    calls: list[datetime] = []
    queue = list(outcomes)

    def one_pass(driver: Any) -> Any:
        calls.append(now[0])
        outcome = queue.pop(0)
        if isinstance(outcome, str):
            raise triage_batch_cmd.ForgeReadError(outcome, code=2)
        return False, _summary(done=outcome), []

    monkeypatch.setattr(triage_batch_cmd, "one_pass", one_pass)
    return calls


def _loop(
    tmp_path: Path,
    meter: Meter,
    monkeypatch: pytest.MonkeyPatch,
    *,
    interval: int = 120,
    driver: StubDriver | None = None,
) -> StubDriver:
    monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: meter)
    driver = driver or StubDriver(tmp_path)
    pacer = triage_batch_cmd.make_pacer(tmp_path, quota_floor=None, interval_s=interval)
    assert triage_batch_cmd._host_loop(driver, once=False, interval=interval, pacer=pacer) is None  # type: ignore[arg-type]
    return driver


def test_a_rate_limited_pass_waits_for_the_reset_and_spends_nothing_until_then(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    now: list[datetime],
    sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = _script(monkeypatch, now, RATE_LIMITED, True)
    meter = Meter(rate_limit_answer(), _exhausted(20), rate_limit_answer())

    _loop(tmp_path, meter, monkeypatch)

    assert sleeps == [20 * 60 + 30], "to the reset plus 30 s, in one go"
    assert calls == [NOW, NOW + timedelta(seconds=20 * 60 + 30)], "no forge call before then"
    out = " ".join(capsys.readouterr().out.split())
    assert "quota: graphql 0/5000 (0%), resets 12:" in out and "waiting 21m" in out
    wait = pacing_state.load(tmp_path)[0]
    assert wait.wait_until is None, "a clean pass after the wait ends it"


def test_an_exhausted_budget_at_pass_start_runs_no_pass_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, now: list[datetime], sleeps: list[float]
) -> None:
    calls = _script(monkeypatch, now, True)
    meter = Meter(_exhausted(5), rate_limit_answer())

    _loop(tmp_path, meter, monkeypatch)

    assert sleeps == [5 * 60 + 30]
    assert calls == [NOW + timedelta(seconds=5 * 60 + 30)], "R3: nothing collected before"


def test_a_wait_is_recorded_so_another_loop_honours_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, now: list[datetime]
) -> None:
    _script(monkeypatch, now, RATE_LIMITED, True)
    seen: list[PacingState] = []

    def nap(seconds: float) -> None:
        seen.append(pacing_state.load(tmp_path)[0])
        now[0] += timedelta(seconds=seconds)

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    _loop(
        tmp_path,
        Meter(rate_limit_answer(), _exhausted(9)),
        monkeypatch,
    )

    assert seen[0].wait_until == NOW + timedelta(minutes=9, seconds=30)


def test_a_secondary_limit_backs_off_from_the_interval_and_a_clean_pass_resets_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, now: list[datetime], sleeps: list[float]
) -> None:
    # budget left each time: limit, limit, clean (work left), limit, done
    _script(monkeypatch, now, SECONDARY, SECONDARY, False, SECONDARY, True)

    _loop(tmp_path, Meter(), monkeypatch)

    assert sleeps == [120, 240, 120, 120], "interval, double, (clean pass + interval), interval"
    assert pacing_state.load(tmp_path)[0].backoff == 0


def test_the_backoff_stops_at_fifteen_minutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, now: list[datetime], sleeps: list[float]
) -> None:
    _script(monkeypatch, now, *([SECONDARY] * 6), True)

    _loop(tmp_path, Meter(), monkeypatch)

    assert sleeps == [120, 240, 480, 900, 900, 900]


def test_an_unreadable_rate_limit_runs_the_pass_and_warns_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    now: list[datetime],
    sleeps: list[float],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = _script(monkeypatch, now, False, True)

    _loop(tmp_path, Meter(ForgeError("HTTP 500")), monkeypatch)

    assert len(calls) == 2, "pacing failed open: both passes ran"
    err = " ".join(capsys.readouterr().err.split())
    assert err.count("could not be read") == 1 and "HTTP 500" in err


def test_a_wait_longer_than_the_lease_renews_it_and_sleeps_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, now: list[datetime], sleeps: list[float]
) -> None:
    """R16, at --interval 1: the lease lasts 60 min + 3 s, the reset is 70 minutes away."""
    duration = lease_duration(1 / 60, DEFAULT_ROUTINE_MIN)
    take_or_renew(tmp_path, "host:x", NOW, scope_id="s", duration=duration)
    driver = StubDriver(tmp_path)
    driver.leased = True

    def renew() -> None:
        driver.renewed += 1
        take_or_renew(tmp_path, "host:x", now[0], scope_id="s", duration=duration)

    driver.take_lease = renew  # type: ignore[method-assign]
    calls = _script(monkeypatch, now, RATE_LIMITED, True)

    _loop(
        tmp_path,
        Meter(rate_limit_answer(), _exhausted(70), rate_limit_answer()),
        monkeypatch,
        interval=1,
        driver=driver,
    )

    bound = (duration - timedelta(minutes=5)).total_seconds()
    assert sleeps[0] == bound, "wakes at the lease's expiry minus five minutes"
    assert driver.renewed == 1 and len(sleeps) == 2
    assert sum(sleeps) == 70 * 60 + 30 and max(sleeps) <= bound
    assert calls[-1] == NOW + timedelta(seconds=70 * 60 + 30)


# ---------------------------------------------------------------- through the CLI


def _loop_cli(state: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    """Loop mode; Ctrl-C at the first nap."""

    def nap(seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    return CliRunner().invoke(
        app, ["triage", "batch", "drive", "--yes", "--repo", REPO, "--dir", str(state), *args]
    )


def test_a_rate_limited_skip_in_the_collect_ends_the_pass_before_the_snapshot(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runner: Any,
    monkeypatch: pytest.MonkeyPatch,
    now: list[datetime],
) -> None:
    """R2: a repo skipped for a rate limit does not raise, so the pass must end itself."""
    from tests.unit.test_triage_batch_drive_cmd import _batch, _state

    world.issues[1] = "open"
    _state(tmp_path, world, _batch("b1", 1))
    monkeypatch.setattr(triage_batch_cmd, "recollect", _REAL_RECOLLECT)

    def collect_into(scope: Any, target: Path, **kw: Any) -> Any:
        facts: Facts = world.facts().model_copy(
            update={"skipped": [Skipped(repo=REPO, reason=RATE_LIMITED)]}
        )
        return facts, target / "facts.json", SimpleNamespace(viewed=0, carried=0, ignored={})

    monkeypatch.setattr(triage_batch_cmd, "collect_into", collect_into)
    snapshots: list[int] = []
    monkeypatch.setattr(triage_batch_cmd._Driver, "snapshot", lambda *a, **k: snapshots.append(1))
    monkeypatch.setattr(
        triage_batch_cmd,
        "_pace_forge",
        lambda: Meter(_exhausted(3)),
    )

    result = _loop_cli(tmp_path, monkeypatch)

    assert snapshots == [] and "pr_view" not in " ".join(world.calls)
    assert "quota: graphql 0/5000 (0%)" in " ".join(result.output.split()), result.output


_REAL_RECOLLECT = triage_batch_cmd.recollect


def test_a_rate_limited_unviewed_key_ends_the_pass_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.model import Unviewed

    facts = Facts(
        schema=3, scope="s", kind="repo", collected_at="2026-10-01T00:00:00+00:00", repos=["o/r"],
        issues=[], prs=[], unviewed=[Unviewed(key="r#1", reason=SECONDARY)],
    )  # fmt: skip
    monkeypatch.setattr(
        triage_batch_cmd,
        "collect_into",
        lambda *a, **k: (facts, tmp_path, SimpleNamespace(viewed=0, carried=0, ignored={})),
    )
    with pytest.raises(triage_batch_cmd.ForgeReadError, match="secondary rate limit"):
        _REAL_RECOLLECT(SCOPE, tmp_path)


def _leased_cloud_state(tmp_path: Path, world: World) -> Path:
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    return state


def test_the_cloud_pass_exits_3_on_an_exhausted_budget_and_takes_no_lease(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _leased_cloud_state(tmp_path, world)
    monkeypatch.setattr(
        triage_batch_cmd,
        "_pace_forge",
        lambda: Meter(_exhausted(30)),
    )

    result = _pass(state, tmp_path / "outbox.json")

    assert result.exit_code == 3, result.output
    assert "quota: graphql 0/5000 (0%)" in " ".join(result.output.split())
    assert world.passes == [], "no collect"  # type: ignore[attr-defined]
    assert load_lease(state) is None and _ref(remote) == "", "no lease taken, nothing pushed"


def test_the_cloud_pass_renews_a_lease_that_would_lapse_before_its_next_wake(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _leased_cloud_state(tmp_path, world)
    take_or_renew(
        state, driver_identity("cloud", HOST_ID), NOW, scope_id=scope_id(SCOPE),
        duration=timedelta(minutes=2),
    )  # fmt: skip
    monkeypatch.setattr(
        triage_batch_cmd,
        "_pace_forge",
        lambda: Meter(_exhausted(30)),
    )

    result = _pass(state, tmp_path / "outbox.json", "--interval", "5")

    assert result.exit_code == 3, result.output
    held = load_lease(state)
    assert held is not None and held.expires >= NOW + timedelta(minutes=5)
    assert _ref(remote), "the renewal was pushed"
    assert world.passes == []  # type: ignore[attr-defined]


def _lapsing_lease(state: Path, expires_in: timedelta) -> None:
    take_or_renew(
        state, driver_identity("cloud", HOST_ID), NOW, scope_id=scope_id(SCOPE),
        duration=expires_in,
    )  # fmt: skip


def test_the_cloud_pass_renews_a_lease_expiring_just_inside_the_margin(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """p1-r5: R16's five-minute margin counts: a lease expiring one second after the
    next wake (now + interval) would lapse inside the margin, so it is renewed."""
    state = _leased_cloud_state(tmp_path, world)
    _lapsing_lease(state, timedelta(minutes=5, seconds=1))
    monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: Meter(_exhausted(30)))

    result = _pass(state, tmp_path / "outbox.json", "--interval", "5")

    assert result.exit_code == 3, result.output
    held = load_lease(state)
    assert held is not None and held.expires > NOW + timedelta(minutes=5, seconds=1)


def test_the_cloud_pass_leaves_a_lease_with_room_to_spare_alone(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _leased_cloud_state(tmp_path, world)
    _lapsing_lease(state, timedelta(minutes=10, seconds=1))
    before = load_lease(state)
    monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: Meter(_exhausted(30)))

    result = _pass(state, tmp_path / "outbox.json", "--interval", "5")

    assert result.exit_code == 3, result.output
    assert load_lease(state) == before


def test_a_failed_renewal_while_waiting_warns_and_still_exits_3(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """p1-r3: the renewal's visibility read can hit the very rate limit that put the
    drive to wait; that is a warning, not an exit 2, and the quota line is still printed."""
    from fr.triage.privacy import VisibilityUnreadable

    state = _leased_cloud_state(tmp_path, world)
    _lapsing_lease(state, timedelta(minutes=2))

    def unreadable(repo: str) -> str:
        raise VisibilityUnreadable(f"cannot read the visibility of {repo}: API rate limit exceeded")

    monkeypatch.setattr(visibility, "repo_visibility", unreadable)
    monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: Meter(_exhausted(30)))

    result = _pass(state, tmp_path / "outbox.json", "--interval", "5")

    out = " ".join(result.output.split())
    assert result.exit_code == 3, result.output
    assert "cannot renew the lease" in out
    assert "quota: graphql 0/5000" in out


def test_the_cloud_pass_honours_a_recorded_wait(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
) -> None:
    state = _leased_cloud_state(tmp_path, world)
    pacing_state.save(state, PacingState(wait_until=NOW + timedelta(minutes=10)))

    result = _pass(state, tmp_path / "outbox.json")

    assert result.exit_code == 3, result.output
    assert "recorded wait" in " ".join(result.output.split())
    assert world.passes == []  # type: ignore[attr-defined]


def test_an_unusable_quota_floor_is_refused_naming_the_flag(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any
) -> None:
    result = CliRunner().invoke(
        app,
        ["triage", "batch", "drive", "--yes", "--quota-floor", "1.5", "--repo", REPO,
         "--dir", str(tmp_path)],
    )  # fmt: skip
    assert result.exit_code == 2 and "--quota-floor" in " ".join(result.output.split())
