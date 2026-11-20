"""The planner and the executor over real git and a fake forge, pass by pass (spec
2026-11-19-wave-merge-queue R4, R9, R10, R24, R33, R35; Test Plan 1, 16, 25).

A small driver loop stands in for `fr triage batch drive`: it builds a `QueueSnapshot`
from the in-memory records and the fake forge, resumes, plans, gates and executes. A
driver killed after `queue_built` and again after the landing push resumes from the
events and the remote, and never lands twice; `post_merge` runs once per landing.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.approval import First
from fr.triage.batch_drive import LivePr
from fr.triage.model import (
    Batch,
    PostMergeEvent,
    QueueBuiltEvent,
    QueueLandEvent,
    QueueOpenEvent,
    QueueRecord,
)
from fr.triage.queue_exec import EntryInput, QueueExecutor, QueuePorts, slot_ref
from fr.triage.wave_queue import QueueConfig, QueueSnapshot, plan_queue

from tests.integration.queue_git import REPO, SCOPE, FakeForge, World, forge, world


class KilledError(Exception):
    """The driver died here."""


class Driver:
    def __init__(self, w: World, f: FakeForge, *, config: QueueConfig) -> None:
        self.w, self.f, self.config = w, f, config
        self.records: list[QueueRecord] = []
        self.batches = {f"b{n}": _batch(f"b{n}", n) for n in w.prs}
        self.post_merges: list[tuple[str, ...]] = []
        self.post_merge_fails: str | None = None
        self.kill_on: Callable[[Any], bool] = lambda e: False
        self.clock = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
        self.executor = QueueExecutor(self.ports())

    def now(self) -> datetime:
        self.clock += timedelta(seconds=1)
        return self.clock

    def ports(self) -> QueuePorts:
        return QueuePorts(
            checkout=self.w.checkout, client=self.f, repo=REPO, scope=SCOPE, default="main",
            method="squash", version=None, config=self.config, scratch=self.w.scratch,
            record=self.record, entry_of=self.entry_of, pr_of=self.pr_of,
            post_merge=self.post_merge, now=self.now,
        )  # fmt: skip

    def record(self, event: Any, *, wave: int | None = None, base: str = "") -> None:
        if isinstance(event, QueueOpenEvent):
            self.records.append(QueueRecord(repo=REPO, wave=wave, scope=SCOPE, base=base))
        last = self.records[-1]
        self.records[-1] = last.model_copy(update={"events": [*last.events, event]})
        if self.kill_on(event):
            raise KilledError(event.kind)

    def entry_of(self, key: str) -> EntryInput | None:
        return self.w.entry(int(key[1:]))

    def pr_of(self, key: str) -> tuple[int, str] | None:
        n = int(key[1:])
        return n, self.w.prs[n]

    def post_merge(self, keys: tuple[str, ...]) -> str | None:
        self.post_merges.append(keys)
        if self.post_merge_fails is not None:
            return self.post_merge_fails
        for k in keys:
            b = self.batches[k]
            event = PostMergeEvent(kind="post_merge", at=self.now())
            self.batches[k] = b.model_copy(update={"events": [*b.events, event]})
        return None

    def snapshot(self) -> QueueSnapshot:
        live = {k: _live(self.f.pr_view(REPO, int(k[1:])), int(k[1:])) for k in self.batches}
        stages = {k: "merged" if pr.state == "MERGED" else "pr-open" for k, pr in live.items()}
        return QueueSnapshot(
            repo=REPO, scope=SCOPE, config=self.config, now=self.clock,
            batches=tuple(self.batches.values()), stages=stages,  # type: ignore[arg-type]
            live=live, approvals={k: First(pr.head) for k, pr in live.items()},
            records=tuple(self.records), base=self.w.main(),
            conflicts=dict(self.executor.conflicts),
        )  # fmt: skip

    def one_pass(self) -> list[str]:
        record = self.records[-1] if self.records else None
        lines = self.executor.resume(record)
        record = self.records[-1] if self.records else None
        plan = plan_queue(self.snapshot())
        plan = self.executor.gate(plan, record, self.batches.values())
        return lines + self.executor.execute(plan, record)

    def events(self, kind: type) -> list[Any]:
        return [e for r in self.records for e in r.events if isinstance(e, kind)]


def _batch(bid: str, n: int) -> Batch:
    return Batch.model_validate({
        "id": bid, "title": bid, "ids": [f"demo#{n}"], "wave": 1,
        "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": f"feat/pr-{n}"}],
    })  # fmt: skip


def _live(view: dict[str, Any], n: int) -> LivePr:
    return LivePr(number=n, state=view["state"], draft=False, head=view["head_oid"],
                  head_ref=view["head_ref"])  # fmt: skip


def _driver(tmp_path: Path, config: QueueConfig | None = None) -> Driver:
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"})
    w.pr(2, {"c.txt": "charlie\n"})
    w.fetch()
    return Driver(w, forge(w, tmp_path), config=config or QueueConfig(ci="none"))


def test_a_wave_opens_builds_lands_once_runs_post_merge_once_and_drains(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    for _ in range(5):
        d.one_pass()
    lands = d.events(QueueLandEvent)
    assert len(lands) == 1 and [e.batch for e in lands[0].entries] == ["b1", "b2"]
    assert d.w.main() == lands[0].main
    built = d.events(QueueBuiltEvent)
    assert d.w.main() == built[-1].sha  # exactly the tested commit (R9)
    assert d.post_merges == [("b1", "b2")]  # once per landing (R33)
    assert [e.kind for e in d.records[-1].events][-1] == "queue_drain"
    assert d.w.remote(slot_ref(SCOPE, 1)) and d.w.remote(slot_ref(SCOPE, 2))


def test_a_driver_killed_after_queue_built_resumes_and_lands_once(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    d.one_pass()  # open
    d.kill_on = lambda e: isinstance(e, QueueBuiltEvent)
    with pytest.raises(KilledError):
        d.one_pass()  # slot-1 recorded, never pushed
    d.kill_on = lambda e: False
    recorded = d.events(QueueBuiltEvent)[0].sha
    lines = d.executor.resume(d.records[-1])
    assert any("re-pushed" in line for line in lines)
    assert d.w.remote(slot_ref(SCOPE, 1)) == recorded
    for _ in range(5):
        d.one_pass()
    landed = [e.batch for land in d.events(QueueLandEvent) for e in land.entries]
    assert sorted(landed) == ["b1", "b2"] and len(set(landed)) == 2  # each landed once
    assert [f.pr_view(REPO, n)["state"] for f in [d.f] for n in (1, 2)] == ["MERGED"] * 2


def test_a_driver_killed_after_the_land_push_records_it_and_never_lands_again(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path)
    d.one_pass()  # open
    d.one_pass()  # build both
    d.kill_on = lambda e: isinstance(e, QueueLandEvent)
    with pytest.raises(KilledError):
        d.one_pass()  # pushed, then died before anything else
    d.records[-1] = d.records[-1].model_copy(
        update={"events": [e for e in d.records[-1].events if not isinstance(e, QueueLandEvent)]}
    )  # the record never reached the file
    d.kill_on = lambda e: False
    main = d.w.main()
    lines = d.one_pass()
    assert any("recorded, not pushed again" in line for line in lines)
    for _ in range(3):
        d.one_pass()
    assert d.w.main() == main and len(d.events(QueueLandEvent)) == 1
    assert d.post_merges == [("b1", "b2")]


def test_a_failed_post_merge_pauses_landings_with_a_need(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", depth=1))
    d.post_merge_fails = "make install: exit 2"
    for _ in range(3):
        d.one_pass()  # open, build b1, land b1 (post_merge fails)
    assert len(d.events(QueueLandEvent)) == 1
    record = d.records[-1]
    plan = d.executor.gate(plan_queue(d.snapshot()), record, d.batches.values())
    assert not any(a.kind == "queue-land" for a in plan.actions)
    assert any(a.kind == "queue-need" and "make install" in a.detail for a in plan.actions)
    d.post_merge_fails = None
    for _ in range(4):
        d.one_pass()
    assert len(d.events(QueueLandEvent)) == 2


def test_a_landed_pr_the_forge_still_shows_open_pauses_the_queue(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", depth=1))
    d.f.sticky.add(1)
    lines: list[str] = []
    for _ in range(3):
        lines += d.one_pass()
    assert any("did not mark #1 merged" in line for line in lines)
    for _ in range(3):
        lines += d.one_pass()  # b2 is built and green, but nothing lands behind #1
    assert len(d.events(QueueLandEvent)) == 1
    assert any("lands nothing until" in line or "did not mark #1" in line for line in lines)
    plan = d.executor.gate(plan_queue(d.snapshot()), d.records[-1], d.batches.values())
    assert any(a.kind == "queue-need" and "did not mark #1 merged" in a.detail
               for a in plan.actions)  # fmt: skip
    d.f.sticky.clear()
    for _ in range(3):
        d.one_pass()
    assert len(d.events(QueueLandEvent)) == 2
