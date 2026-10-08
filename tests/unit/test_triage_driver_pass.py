"""`fr triage drive pass` and `fr triage drive record`: the cloud driver's pass per wake
(spec 2026-10-07-cloud-triage R9, R12, R13, §E, Test Plan 9).

The world, clone and runner fakes are `test_triage_batch_drive_cmd`'s; the cloud runner
is a `FakeRunner` that also keeps a mailbox (`fr.triage.driver.Mailbox`), as
`claude-cloud` will. Every state ref is pushed to a bare repo under `tmp_path`.
"""

from __future__ import annotations

import json
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd, triage_drive_cmd
from fr.triage import batch_drive
from fr.triage.lease import driver_identity, holder_of, lease_duration, load_lease, take_or_renew
from fr.triage.model import Scope, load_judgements
from fr.triage.scope_config import scope_id
from fr.triage.state_ref import ref_name
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    _state,
    checkout_fixture,
    world_fixture,
)

SCOPE = Scope(kind="repo", target=REPO)
HOST_ID = "0123456789abcdef"
CONFIG = {"defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "m"}}}


class MailboxRunner(FakeRunner):
    """A cloud runner: each dispatch is a pending request until the agent records it."""

    def __init__(self) -> None:
        super().__init__()
        self.opened: list[tuple[Path, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self.recorded: list[dict[str, Any]] = []

    def open_mailbox(self, state_dir: Any, statuses: Any) -> None:
        self.opened.append((Path(state_dir), statuses))

    def dispatch(self, item: Any) -> str | None:
        super().dispatch(item)
        rid = f"{item.id}:dispatch:1"
        self.requests.append({"id": rid, "kind": "dispatch", "item": item.id})
        return f"pending:{rid}"

    def outbox(self) -> list[dict[str, Any]]:
        return list(self.requests)

    def record_results(self, results: list[dict[str, Any]]) -> list[str]:
        mine = {r["id"] for r in self.requests}
        applied = [r for r in results if r.get("id") in mine]
        self.recorded += applied
        state = self.opened[-1][0]
        (state / "sessions.yaml").write_text(
            yaml.safe_dump({"sessions": [dict(r) for r in self.recorded]})
        )
        return [r["id"] for r in applied]


class Runners:
    def __init__(self) -> None:
        self.by_name: dict[str, FakeRunner] = {"claude-cloud": MailboxRunner()}
        self.asked: list[str] = []

    def __call__(self, name: str) -> FakeRunner:
        self.asked.append(name)
        return self.by_name.setdefault(name, FakeRunner())

    @property
    def cloud(self) -> MailboxRunner:
        runner = self.by_name["claude-cloud"]
        assert isinstance(runner, MailboxRunner)
        return runner


class _Private:
    def __init__(self) -> None:
        self.asked: list[str] = []

    def repo_visibility(self, repo: str) -> str:
        self.asked.append(repo)
        return "private"


@pytest.fixture
def runners(monkeypatch: pytest.MonkeyPatch) -> Runners:
    found = Runners()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", found)
    return found


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    now = [NOW]
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: now[0])
    monkeypatch.setattr(triage_drive_cmd, "_now", lambda: now[0])
    monkeypatch.setenv("FR_HOST_ID", HOST_ID)
    return now


@pytest.fixture
def visibility(monkeypatch: pytest.MonkeyPatch) -> _Private:
    client = _Private()
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: client)
    return client


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bare = tmp_path / "state.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(bare))
    monkeypatch.setattr(triage_cmd, "state_remote", lambda state_repo: str(bare))
    return bare


def _ref(remote: Path) -> str:
    out = _git(remote, "for-each-ref", "--format=%(objectname)", ref_name(scope_id(SCOPE)))
    return out.strip()


def _workspace(tmp_path: Path, name: str) -> tuple[Path, Path]:
    ws = tmp_path / name
    _git(tmp_path, "init", "--quiet", str(ws))
    return ws, ws / ".fr" / "triage-state" / SCOPE.name


def _batch(bid: str, n: int, *, events: str = "") -> str:
    ev = f"    events:\n{events}" if events else ""
    return f'  - id: {bid}\n    title: {bid}\n    ids: ["super-fr#{n}"]\n    wave: 1\n{ev}'


def _world(world: World, state: Path) -> None:
    """Two proposed batches and one whose PR is green and ready to merge."""
    world.config = CONFIG
    world.issues.update({1: "open", 2: "open", 3: "open"})
    world.pr(103, "feat/batch-b3", [3])
    dispatched = ("      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: claude-cloud, "
                  "handle: h, branch: feat/batch-b3}\n")  # fmt: skip
    state.mkdir(parents=True, exist_ok=True)
    _state(state, world, _batch("b1", 1), _batch("b2", 2), _batch("b3", 3, events=dispatched))


def _pass(state: Path, outbox: Path, *extra: str) -> Any:
    return CliRunner().invoke(
        app,
        ["triage", "drive", "pass", "--repo", REPO, "--dir", str(state),
         "--outbox", str(outbox), *extra],
    )  # fmt: skip


def _record(state: Path, outbox: Path, results: Path) -> Any:
    return CliRunner().invoke(
        app,
        ["triage", "drive", "record", "--repo", REPO, "--dir", str(state),
         "--outbox", str(outbox), "--result", str(results)],
    )  # fmt: skip


# ------------------------------------------------- one policy, two adapters (R13)


def test_the_pass_makes_the_decisions_the_host_loop_makes_for_the_same_facts(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plans: list[list[batch_drive.Action]] = []
    real = triage_batch_cmd.drive_pass

    def spy(snap: Any) -> Any:
        plan = real(snap)
        plans.append(list(plan.actions))
        return plan

    monkeypatch.setattr(triage_batch_cmd, "drive_pass", spy)
    host, cloud = tmp_path / "host", tmp_path / "cloud"
    _world(world, host)
    _world(world, cloud)

    hosted = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--once", "--repo", REPO, "--dir", str(host)]
    )
    passed = _pass(cloud, tmp_path / "outbox.json")

    assert hosted.exit_code == 0, hosted.output
    assert passed.exit_code == 0, passed.output
    host_plan, cloud_plan = plans
    assert [a.kind for a in host_plan].count("dispatch") == 2
    assert [a.kind for a in host_plan].count("merge") == 1
    assert cloud_plan == host_plan


def test_a_pass_acts_writes_the_runners_requests_to_the_outbox_and_exits_0(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners, clock: list[Any]
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    statuses = tmp_path / "statuses.json"
    statuses.write_text(json.dumps({"derio-net/super-fr/run/batch-b3": "working"}))
    outbox = tmp_path / "outbox.json"

    result = _pass(state, outbox, "--statuses", str(statuses))

    assert result.exit_code == 0, result.output
    assert world.merged and world.merged[0][0] == 103  # forge actions: fr's own
    cloud = runners.cloud
    assert cloud.opened[0] == (state, {"derio-net/super-fr/run/batch-b3": "working"})
    requests = json.loads(outbox.read_text())["requests"]
    assert [r["item"] for r in requests] == [
        "derio-net/super-fr/run/batch-b1",
        "derio-net/super-fr/run/batch-b2",
    ]
    assert set(runners.asked) == {"claude-cloud"}
    lease = load_lease(state)
    assert lease is not None
    assert lease.holder == holder_of(scope_id(SCOPE), driver_identity("cloud", HOST_ID))
    assert lease.last_pass == NOW and lease.expires == NOW + lease_duration()


def test_nothing_left_but_waiting_exits_3(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners, clock: list[Any]
) -> None:
    state = tmp_path / "state"
    world.config = CONFIG
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True)
    dispatched = ("      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: claude-cloud, "
                  "handle: h, branch: feat/batch-b1}\n")  # fmt: skip
    state.mkdir()
    _state(state, world, _batch("b1", 1, events=dispatched))

    result = _pass(state, tmp_path / "outbox.json")

    assert result.exit_code == 3, result.output
    assert json.loads((tmp_path / "outbox.json").read_text()) == {"requests": []}


def test_a_wake_within_the_interval_only_renews_the_lease(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners, clock: list[Any]
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    assert _pass(state, tmp_path / "o1.json").exit_code == 0
    passes = len(world.passes)  # type: ignore[attr-defined]
    clock[0] = NOW + timedelta(minutes=2)

    result = _pass(state, tmp_path / "o2.json", "--interval", "5")

    assert result.exit_code == 3, result.output
    assert len(world.passes) == passes, "no collect, no pass"  # type: ignore[attr-defined]
    assert "renewed" in result.output
    lease = load_lease(state)
    assert lease is not None and lease.expires == clock[0] + lease_duration()
    assert lease.last_pass == NOW
    assert json.loads((tmp_path / "o2.json").read_text()) == {"requests": []}

    clock[0] = NOW + timedelta(minutes=6)
    assert _pass(state, tmp_path / "o3.json", "--interval", "5").exit_code in (0, 3)
    assert len(world.passes) == passes + 1  # type: ignore[attr-defined]


def test_another_drivers_live_lease_refuses_the_pass_naming_holder_and_expiry(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners, clock: list[Any]
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    other = driver_identity("host", "fedcba9876543210")
    take_or_renew(state, other, NOW, scope_id=scope_id(SCOPE))
    before = (state / "judgements.yaml").read_bytes()

    result = _pass(state, tmp_path / "outbox.json")

    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert holder_of(scope_id(SCOPE), other) in flat
    assert (NOW + lease_duration()).isoformat() in flat
    assert world.passes == []  # type: ignore[attr-defined]
    assert runners.cloud.dispatched == [] and world.merged == []
    assert (state / "judgements.yaml").read_bytes() == before


# ----------------------------------------------------- the ref: restore and push


def test_a_fresh_workspace_restores_from_the_ref_renews_the_lease_and_pushes(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: _Private,
) -> None:
    _, seeded = _workspace(tmp_path, "a")
    _world(world, seeded)
    (seeded / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    assert triage_cmd.push_now(SCOPE, seeded) is not None
    before = _ref(remote)
    ws, fresh = _workspace(tmp_path, "b")

    result = CliRunner().invoke(
        app,
        ["triage", "drive", "pass", "--repo", REPO, "--workspace", str(ws),
         "--state-repo", REPO, "--outbox", str(tmp_path / "outbox.json")],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert load_judgements(fresh / "judgements.yaml").batches[0].id == "b1"
    after = _ref(remote)
    assert after and after != before
    pushed = yaml.safe_load(_git(remote, "show", f"{after}:lease.yaml"))
    assert pushed["holder"] == holder_of(scope_id(SCOPE), driver_identity("cloud", HOST_ID))
    assert REPO in visibility.asked  # the privacy guard read the state repo before the push
    assert "b1" in _git(remote, "show", f"{after}:judgements.yaml")


def test_record_applies_every_result_empties_the_outbox_and_pushes_the_ref(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: _Private,
) -> None:
    ws, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    outbox = tmp_path / "outbox.json"
    assert _pass(state, outbox).exit_code == 0
    after_pass = _ref(remote)
    requests = json.loads(outbox.read_text())["requests"]
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"id": r["id"], "session": f"session-{i}"} for i, r in enumerate(requests)])
    )

    result = _record(state, outbox, results)

    assert result.exit_code == 0, result.output
    assert [r["id"] for r in runners.cloud.recorded] == [r["id"] for r in requests]
    assert json.loads(outbox.read_text()) == {"requests": []}
    assert _ref(remote) != after_pass
    assert "session-0" in _git(remote, "show", f"{_ref(remote)}:sessions.yaml")


def test_record_refuses_a_result_no_request_names_and_a_foreign_lease(
    tmp_path: Path, world: World, checkout: DriveCheckout, runners: Runners, clock: list[Any]
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    outbox = tmp_path / "outbox.json"
    assert _pass(state, outbox).exit_code == 0
    results = tmp_path / "results.json"
    results.write_text(json.dumps([{"id": "nobody:dispatch:9", "session": "s"}]))

    result = _record(state, outbox, results)

    assert result.exit_code == 2, result.output
    assert "nobody:dispatch:9" in result.output

    take_or_renew(
        state, driver_identity("host", "fedcba9876543210"), NOW, scope_id=scope_id(SCOPE),
        force=True,
    )  # fmt: skip
    results.write_text("[]")
    result = _record(state, outbox, results)
    assert result.exit_code == 2, result.output
    assert "host:fedcba9876543210" in " ".join(result.output.split())


def test_the_host_loop_takes_and_releases_the_lease_with_a_state_repo(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: _Private,
) -> None:
    """R9: the lease replaces drive.lock as the cross-host check; the host renews it every
    pass (each pass pushed) and releases it on a clean stop."""
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    other = driver_identity("cloud", "fedcba9876543210")
    take_or_renew(state, other, NOW, scope_id=scope_id(SCOPE))

    held = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--once", "--yes", "--repo", REPO, "--dir", str(state)]
    )
    assert held.exit_code == 2, held.output
    assert holder_of(scope_id(SCOPE), other) in " ".join(held.output.split())
    assert world.passes == []  # type: ignore[attr-defined]

    (state / "lease.yaml").unlink()
    done = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--once", "--yes", "--repo", REPO, "--dir", str(state)]
    )
    assert done.exit_code == 0, done.output
    assert load_lease(state) is None, "released on a clean stop"
    log = _git(remote, "log", "--format=%H", _ref(remote))
    shas = log.split()
    leases = [
        _git(remote, "show", f"{sha}:lease.yaml") if "lease.yaml" in _git(
            remote, "ls-tree", "--name-only", sha) else ""
        for sha in shas
    ]  # fmt: skip
    assert any(f"host:{HOST_ID}" in text for text in leases), "the lease was pushed"
    assert leases[0] == "", "the release was pushed last"
