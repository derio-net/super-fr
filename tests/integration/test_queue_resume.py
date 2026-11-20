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
    QueueHaltEvent,
    QueueLandEvent,
    QueueOpenEvent,
    QueueRecord,
    QueueSlotLostEvent,
)
from fr.triage.queue_exec import EntryInput, QueueExecutor, QueuePorts, slot_ref
from fr.triage.wave_queue import QueueConfig, QueueSnapshot, plan_queue

from tests.integration.queue_git import REPO, SCOPE, FakeForge, World, forge, git, world


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
        lines = self.executor.resume(record, self.records)
        record = self.records[-1] if self.records else None
        plan = plan_queue(self.snapshot())
        plan = self.executor.gate(plan, record, self.batches.values())
        self.last_plan = plan
        return lines + self.executor.execute(plan, record, self.records)

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


# ------------------------------------------------ a halted queue stays halted (p3-r1)


def _pushed_to_slot(d: Driver, slot: int, files: dict[str, str]) -> str:
    """Another writer's push to slot *slot*: a commit on main writing *files*."""
    seed = d.w.seed
    git(seed, "fetch", "--quiet", "origin")
    git(seed, "checkout", "--quiet", "-B", "intruder", "origin/main")
    for path, text in files.items():
        (seed / path).write_text(text)
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "not the queue's")
    git(seed, "push", "--quiet", "--force", "origin", f"intruder:{slot_ref(SCOPE, slot)}")
    git(seed, "checkout", "--quiet", "--detach")
    return d.w.remote(slot_ref(SCOPE, slot))


def test_a_land_merge_tree_mismatch_stops_the_queue_until_the_operator_acts(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", land="merge"))
    d.f.main_after_merge = "drift.txt"
    lines: list[str] = []
    for _ in range(3):
        lines += d.one_pass()  # open, build both, land: the tree check fails
    assert any("stopped" in line and "tree" in line for line in lines)
    (halt,) = d.events(QueueHaltEvent)
    assert halt.state == "stopped" and halt.land == "merge" and halt.main == d.w.main()
    merges, lands = len(d.f.merges), len(d.events(QueueLandEvent))
    for _ in range(3):
        d.one_pass()
    assert len(d.f.merges) == merges and len(d.events(QueueLandEvent)) == lands
    assert len(d.events(QueueBuiltEvent)) == 2  # nothing is built either
    (need,) = d.last_plan.actions
    assert need.kind == "queue-need" and "stopped" in need.detail and "tree" in need.detail


def test_a_push_the_protection_refuses_holds_the_queue_with_a_need(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    hook = d.w.origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 0\n")  # the hold and the slots push fine
    hook.chmod(0o755)
    d.one_pass()  # open: the hold is written
    d.one_pass()  # build
    hook.write_text('#!/bin/sh\necho "error: GH013: Repository rule violations found" >&2\n'
                    'echo x >> "$GIT_DIR/refused"\nexit 1\n')  # fmt: skip
    main = d.w.main()
    d.one_pass()  # land: refused
    (halt,) = d.events(QueueHaltEvent)
    assert halt.state == "held" and "GH013" in halt.detail and "queue.land: merge" in halt.detail
    tries = (d.w.origin / "refused").read_text().count("x")
    for _ in range(2):
        d.one_pass()
    assert (d.w.origin / "refused").read_text().count("x") == tries  # no push tried again
    assert d.w.main() == main and d.events(QueueLandEvent) == []
    (need,) = d.last_plan.actions
    assert need.kind == "queue-need" and "GH013" in need.detail and "held" in need.detail
    hook.write_text("#!/bin/sh\nexit 0\n")  # the forge's own merges are not refused
    d.config = QueueConfig(ci="none", land="merge")  # the operator acts
    d.executor.ports = d.ports()
    for _ in range(3):
        d.one_pass()
    assert len(d.events(QueueLandEvent)) == 1  # lands through the forge now


# ------------------------------------------------ resume reads the forge (R24; p3-r3)


def test_a_land_push_killed_then_main_moved_foreign_is_recorded_and_never_repushed(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path)
    d.one_pass()  # open
    d.one_pass()  # build both
    d.kill_on = lambda e: isinstance(e, QueueLandEvent)
    with pytest.raises(KilledError):
        d.one_pass()
    d.records[-1] = d.records[-1].model_copy(
        update={"events": [e for e in d.records[-1].events if not isinstance(e, QueueLandEvent)]}
    )  # the record never reached the file
    d.kill_on = lambda e: False
    tip = d.w.main()
    foreign = d.w.move_main({"f.txt": "foreign\n"})  # someone merged on top meanwhile
    lines = d.one_pass()
    assert any("recorded, not pushed again" in line and "moved on" in line for line in lines)
    (land,) = d.events(QueueLandEvent)
    assert land.main == tip and [e.batch for e in land.entries] == ["b1", "b2"]
    for _ in range(3):
        d.one_pass()
    assert len(d.events(QueueLandEvent)) == 1 and d.w.main() == foreign


def _kill_after_merge(d: Driver, number: int) -> None:
    real = d.f.pr_merge

    def merge(repo: str, n: int, **kw: Any) -> None:
        real(repo, n, **kw)
        if n == number:
            raise KilledError(f"after merging #{n}")

    d.f.pr_merge = merge  # type: ignore[method-assign]


def test_a_land_merge_killed_after_its_first_merge_records_it_and_lands_the_rest(
    tmp_path: Path,
) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", land="merge"))
    d.one_pass()  # open
    d.one_pass()  # build both
    _kill_after_merge(d, 1)
    with pytest.raises(KilledError):
        d.one_pass()  # #1 merged through the forge, then the driver died
    d.f.pr_merge = FakeForge.pr_merge.__get__(d.f)  # type: ignore[method-assign]
    assert d.events(QueueLandEvent) == []
    lines = d.one_pass()
    assert any("b1 had merged through the forge" in line for line in lines)
    first = d.events(QueueLandEvent)[0]
    assert [e.batch for e in first.entries] == ["b1"] and d.events(QueueHaltEvent) == []
    for _ in range(4):
        d.one_pass()
    assert [n for n, _, _ in d.f.merges] == [1, 2]  # each merged once
    assert [[e.batch for e in x.entries] for x in d.events(QueueLandEvent)] == [["b1"], ["b2"]]


def test_a_land_merge_killed_after_every_merge_records_the_whole_landing(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="none", land="merge"))
    d.one_pass()
    d.one_pass()
    _kill_after_merge(d, 2)
    with pytest.raises(KilledError):
        d.one_pass()
    d.f.pr_merge = FakeForge.pr_merge.__get__(d.f)  # type: ignore[method-assign]
    d.one_pass()
    (land,) = d.events(QueueLandEvent)
    assert [e.batch for e in land.entries] == ["b1", "b2"] and land.main == d.w.main()
    for _ in range(3):
        d.one_pass()
    assert [n for n, _, _ in d.f.merges] == [1, 2] and len(d.events(QueueLandEvent)) == 1


# ------------------------------------------------ slot leases (R4; p3-r8)


def test_a_slot_another_writer_moved_is_never_overwritten_by_a_rebuild(tmp_path: Path) -> None:
    d = _driver(tmp_path, QueueConfig(ci="push"))
    d.one_pass()  # open
    d.one_pass()  # build both (pending: no checks)
    theirs = _pushed_to_slot(d, 1, {"x.txt": "theirs\n"})
    d.w.push_to(1, {"b.txt": "bravo, edited\n"})  # b1's head moves: it is built again
    d.w.fetch()
    lines = d.executor.execute(plan_queue(d.snapshot()), d.records[-1], d.records)  # the build
    assert any("slot 1 was moved by another writer" in line for line in lines), lines
    assert d.w.remote(slot_ref(SCOPE, 1)) == theirs  # refused, reported
    (lost,) = d.events(QueueSlotLostEvent)
    assert lost.slot == 1 and lost.found == theirs
    d.executor.resume(d.records[-1], d.records)
    assert d.w.remote(slot_ref(SCOPE, 1)) == theirs  # resume does not overwrite it either
    lines = d.one_pass()  # built again, leased on what the queue recorded it holds
    last = [e for e in d.events(QueueBuiltEvent) if e.slot == 1][-1]
    assert d.w.remote(slot_ref(SCOPE, 1)) == last.sha != theirs, lines
    assert len(d.events(QueueSlotLostEvent)) == 1


def test_resume_never_repushes_over_a_slot_another_writer_moved(tmp_path: Path) -> None:
    d = _driver(tmp_path)
    d.one_pass()  # open
    d.kill_on = lambda e: isinstance(e, QueueBuiltEvent)
    with pytest.raises(KilledError):
        d.one_pass()  # slot-1 recorded, never pushed
    d.kill_on = lambda e: False
    theirs = _pushed_to_slot(d, 1, {"x.txt": "theirs\n"})
    lines = d.executor.resume(d.records[-1], d.records)
    assert any("moved by another writer" in line for line in lines), lines
    assert d.w.remote(slot_ref(SCOPE, 1)) == theirs
    assert [e.found for e in d.events(QueueSlotLostEvent)] == [theirs]
    assert d.executor.resume(d.records[-1], d.records) == []  # said once, never retried
