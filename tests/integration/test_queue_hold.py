"""The hold handshake over real git and a fake forge (spec 2026-11-19-wave-merge-queue R17,
R19, R27, R31; Test Plan 11, 18, 20).

`refs/heads/fr-hold/queue` is pushed by the executor: `open` at queue open and refreshed
once it is old, `drained` after the last landing, `cleared` by the driver under
`release: none`. Every write is leased on what the ref held when read; a lost lease is
reported and never forced. A vanished, cleared or expired `open` hold is re-armed with one
Need; another scope's hold opens and lands nothing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fr.triage import queue_exec
from fr.triage.model import QueueClearedEvent, QueueDrainEvent
from fr.triage.queue_exec import read_hold
from fr.triage.wave_queue import HOLD_REF, QueueConfig, QueueSnapshot, hold_message, plan_queue

from tests.integration.queue_git import REPO, SCOPE, FakeForge, World, git, world
from tests.integration.test_queue_resume import Driver, KilledError


class DispatchingForge(FakeForge):
    def __init__(self, w: World, worker: Path) -> None:
        super().__init__(w, worker)
        self.dispatched: list[tuple[str, str, dict[str, str]]] = []
        self.dispatch_error: Exception | None = None

    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        if self.dispatch_error is not None:
            raise self.dispatch_error
        self.dispatched.append((repo, workflow, inputs))


class HoldDriver(Driver):
    """The resume driver with the hold read into each snapshot, as the command does."""

    def snapshot(self) -> QueueSnapshot:
        self.w.fetch()
        snap = super().snapshot()
        record = self.records[-1] if self.records else None
        cut = (
            self.w.checkout.release_commits(record.base, "origin/main") if record is not None
            else ()
        )  # fmt: skip
        return replace(
            snap, hold=read_hold(self.w.checkout), hold_read=True,
            releases=tuple(f"{s.removeprefix('release: ')} at {sha[:12]}" for sha, s in cut),
            base=self.w.main(),
        )  # fmt: skip


def _driver(tmp_path: Path, config: QueueConfig | None = None) -> HoldDriver:
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"})
    w.pr(2, {"c.txt": "charlie\n"})
    w.fetch()
    f = DispatchingForge(w, tmp_path / "worker")
    git(tmp_path, "clone", "--quiet", str(w.origin), str(tmp_path / "worker"))
    f.worker = tmp_path / "worker"
    d = HoldDriver(w, f, config=config or QueueConfig(ci="none"))
    return d


def _hold_of(w: World) -> tuple[str, str, str]:
    """(sha, parent, message) of origin's hold ref."""
    sha = w.remote(HOLD_REF)
    return (
        sha,
        git(w.origin, "rev-parse", f"{sha}^"),
        git(w.origin, "log", "-1", "--format=%B", sha),
    )


def _run_to_drain(d: HoldDriver, passes: int = 6) -> None:
    for _ in range(passes):
        d.one_pass()


def test_queue_open_pushes_the_hold_open_on_the_base_leased_on_absent(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    base = d.w.main()
    lines = d.one_pass()
    sha, parent, message = _hold_of(d.w)
    assert parent == base
    assert message.startswith(f"fr-hold: open scope {SCOPE} wave 1 opened ")
    assert " refreshed " in message and any("hold open" in line for line in lines)
    assert d.records[-1].base == base
    # the hold is no queue slot: it sits outside fr-queue/, so no queue CI runs on it
    assert not HOLD_REF.startswith("refs/heads/fr-queue/")


def test_a_fresh_hold_is_left_alone_and_an_old_one_is_refreshed(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))  # never lands: the queue stays open
    d.one_pass()
    first, _, first_msg = _hold_of(d.w)
    d.clock += timedelta(minutes=10)
    d.one_pass()
    assert _hold_of(d.w)[0] == first  # not due
    d.clock += timedelta(hours=2)
    lines = d.one_pass()
    second, parent, message = _hold_of(d.w)
    assert second != first and parent == d.records[-1].base
    assert any("hold open" in line for line in lines)
    opened = first_msg.split(" opened ")[1].split(" refreshed ")[0]
    assert f" opened {opened} refreshed " in message  # the open time is kept
    assert message != first_msg


def test_the_drain_pushes_drained_on_the_drained_main_and_dispatches_the_release(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", release_workflow="release.yml"))
    _run_to_drain(d)
    assert [e.kind for e in d.records[-1].events][-1] == "queue_drain"
    _, parent, message = _hold_of(d.w)
    assert message.startswith(f"fr-hold: drained scope {SCOPE} wave 1 opened ")
    assert parent == d.w.main()  # the drained main, which a release's base must contain
    assert d.f.dispatched == [(REPO, "release.yml", {})]  # type: ignore[attr-defined]
    before = _hold_of(d.w)[0]
    d.one_pass()
    assert _hold_of(d.w)[0] == before  # releasing: the driver writes nothing more


def test_a_forge_failure_on_dispatch_is_a_warning(tmp_path: Path) -> None:
    from fr.gh import GhError

    d = _driver(tmp_path, QueueConfig(ci="none", release_workflow="release.yml"))
    d.f.dispatch_error = GhError("HTTP 404: no workflow_dispatch trigger")  # type: ignore[attr-defined]
    lines: list[str] = []
    for _ in range(6):
        lines += d.one_pass()
    assert any("warning: dispatching release.yml failed" in line for line in lines)
    assert "fr-hold: drained scope" in _hold_of(d.w)[2]


def test_under_release_none_the_driver_clears_its_own_hold_at_drain(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", release="none", release_workflow="release.yml"))
    _run_to_drain(d)
    assert _hold_of(d.w)[2].startswith(f"fr-hold: cleared scope {SCOPE} wave 1 opened ")
    assert d.events(QueueClearedEvent) and d.events(QueueDrainEvent)
    assert d.f.dispatched == []  # nothing releases: there is no workflow to start


def test_a_lease_failure_on_the_hold_is_reported_never_forced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none"))
    for _ in range(3):
        d.one_pass()  # open, build, land
    before = _hold_of(d.w)
    monkeypatch.setattr(queue_exec, "read_hold", lambda checkout: None)  # a stale read
    lines = d.one_pass()  # drain: leased on "absent", the ref exists
    assert any("another writer moved the hold: not written, never forced" in x for x in lines)
    assert _hold_of(d.w) == before  # still open: nothing was forced over it
    monkeypatch.undo()


def test_a_drain_recorded_but_never_pushed_is_pushed_by_the_next_pass(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    for _ in range(3):
        d.one_pass()
    d.kill_on = lambda e: isinstance(e, QueueDrainEvent)
    with pytest.raises(KilledError):
        d.one_pass()  # the drain is recorded, the driver dies before the hold is written
    d.kill_on = lambda e: False
    assert "fr-hold: open" in _hold_of(d.w)[2]
    lines = d.one_pass()
    assert "fr-hold: drained" in _hold_of(d.w)[2]
    assert any("drain pushed" in x for x in lines)
    assert len(d.events(QueueDrainEvent)) == 1  # recorded once


def test_a_vanished_hold_is_re_armed_with_one_need_naming_a_release(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))
    d.one_pass()
    base = d.records[-1].base
    git(d.w.origin, "update-ref", "-d", HOLD_REF)  # someone deleted the hold
    d.w.move_main({"pyproject.toml": '[project]\nname = "demo"\nversion = "1.0.1"\n'})
    git(d.w.seed, "commit", "--quiet", "--amend", "-m", "release: v1.0.1")
    git(d.w.seed, "push", "--quiet", "--force", "origin", "HEAD:main")
    plan = plan_queue(d.snapshot())
    (need,) = [a for a in plan.actions if a.kind == "queue-need"]
    assert "gone" in need.detail and "v1.0.1 at " in need.detail
    lines = d.executor.execute(plan, d.records[-1], d.records)
    assert any("hold open" in x for x in lines)
    _, parent, message = _hold_of(d.w)
    assert parent == base and message.startswith(f"fr-hold: open scope {SCOPE} wave 1 opened ")
    # re-armed: the next pass has no hold need
    again = plan_queue(d.snapshot())
    assert not any(a.kind == "queue-need" and "hold" in a.detail for a in again.actions)


def test_a_hold_cleared_by_the_release_mid_queue_is_re_armed_leased_on_the_cleared_one(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))
    d.one_pass()
    sha, parent, _ = _hold_of(d.w)
    cleared = git(d.w.seed, "commit-tree", f"{parent}^{{tree}}", "-p", parent, "-m",
                  hold_message("cleared", SCOPE, 1, d.clock, d.clock))  # fmt: skip
    git(d.w.seed, "push", "--quiet", "--force", "origin", f"{cleared}:{HOLD_REF}")
    plan = plan_queue(d.snapshot())
    assert next(a for a in plan.actions if a.kind == "queue-hold").reason == "rearm"
    assert any("cleared by the release" in a.detail for a in plan.actions
               if a.kind == "queue-need")  # fmt: skip
    d.executor.execute(plan, d.records[-1], d.records)
    assert "fr-hold: open" in _hold_of(d.w)[2] and _hold_of(d.w)[0] not in (sha, cleared)


def test_an_expired_hold_is_re_armed_on_the_drivers_return(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))
    d.one_pass()
    old = _hold_of(d.w)[0]
    d.clock += timedelta(hours=25)  # no driver pass for a day
    plan = plan_queue(d.snapshot())
    assert next(a for a in plan.actions if a.kind == "queue-hold").reason == "rearm"
    d.executor.execute(plan, d.records[-1], d.records)
    assert _hold_of(d.w)[0] != old and "fr-hold: open" in _hold_of(d.w)[2]


def test_a_rearm_lands_nothing_untested_and_moves_no_pr_branch(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))
    d.one_pass()
    d.one_pass()  # built, slots pushed, CI pending: nothing lands
    main, heads = d.w.main(), {n: d.w.head(n) for n in d.w.prs}
    git(d.w.origin, "update-ref", "-d", HOLD_REF)
    d.one_pass()
    assert d.w.main() == main
    assert {n: d.w.head(n) for n in d.w.prs} == heads


def test_another_scopes_hold_opens_nothing_and_is_never_written_over(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    git(d.w.seed, "fetch", "--quiet", "origin")
    parent = d.w.main()
    foreign = git(d.w.seed, "commit-tree", f"{parent}^{{tree}}", "-p", parent, "-m",
                  hold_message("open", "s-22222222", 2, d.clock, d.clock))  # fmt: skip
    git(d.w.seed, "push", "--quiet", "origin", f"{foreign}:{HOLD_REF}")
    lines = d.one_pass()
    assert d.records == [] and d.w.remote(HOLD_REF) == foreign
    assert d.last_plan.actions[0].kind == "queue-held"
    assert "s-22222222" in d.last_plan.actions[0].detail
    assert not any("opened" in x for x in lines)


def test_a_race_that_takes_the_hold_between_planning_and_opening_opens_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _driver(tmp_path)
    git(d.w.seed, "fetch", "--quiet", "origin")
    parent = d.w.main()
    foreign = git(d.w.seed, "commit-tree", f"{parent}^{{tree}}", "-p", parent, "-m",
                  hold_message("drained", "s-22222222", 2, d.clock, d.clock))  # fmt: skip
    git(d.w.seed, "push", "--quiet", "origin", f"{foreign}:{HOLD_REF}")
    monkeypatch.setattr("fr.triage.queue_exec.read_hold", read_hold)
    plan = plan_queue(replace(d.snapshot(), hold=None, hold_read=False))  # planned before it
    assert [a.kind for a in plan.actions][:1] == ["queue-open"]
    lines = d.executor.execute(plan, None, [])
    assert d.records == [] and any("not opened: the hold is drained for scope" in x for x in lines)
    assert d.w.remote(HOLD_REF) == foreign


def test_the_hold_commit_carries_the_base_tree_and_one_parent(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    d.one_pass()
    sha, parent, _ = _hold_of(d.w)
    assert git(d.w.origin, "rev-parse", f"{sha}^{{tree}}") == git(
        d.w.origin, "rev-parse", f"{parent}^{{tree}}")  # fmt: skip
    assert git(d.w.origin, "rev-list", "--parents", "-1", sha).split()[1:] == [parent]
