"""One collected close-out per wave (spec 2026-11-19-wave-merge-queue R15).

`drive_pass` step 2 starts a wave's close-out only once every batch of the wave is terminal
and, where the repo runs a `post_merge`, every landed one has it recorded; it takes the
wave's landed batches that no post-merge gate holds; a gated batch's close-out is owed after
its gate passes and is its own, between waves. Under quiet or stealth placement the queue
holds batch PRs only.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fr.triage.batch_drive import (
    Admitted,
    GateLedger,
    drive_pass,
    queue_snapshot,
    wave_landings_done,
)

from tests.unit.test_triage_batch_drive import NOW, REPO, _batch, _dispatched, _live, _snap

POST_MERGE = {"kind": "post_merge", "at": "2026-10-02T11:00:00Z"}


def _wave(batches: dict[str, tuple[int | None, str]], **kw: Any) -> Any:
    """Batches by id -> (wave, stage); the landed ones merged an hour ago."""
    made = [_dispatched(b, i, wave=w, events=kw.pop(f"{b}_events", []))
            for i, (b, (w, _)) in enumerate(batches.items(), 1)]  # fmt: skip
    stages = {b: stage for b, (_, stage) in batches.items()}
    merged_at = {b: NOW - timedelta(hours=1) for b, s in stages.items() if s == "merged"}
    return _snap(made, stages, merged_at=merged_at, **kw)


def _closeouts(snap: Any) -> list[tuple[str, ...]]:
    return [a.items for a in drive_pass(snap).actions if a.kind == "closeout"]


def test_a_waves_close_out_waits_for_every_batch_of_the_wave_to_land() -> None:
    snap = _wave({"a": (1, "merged"), "b": (1, "pr-open")})
    assert _closeouts(snap) == []  # b has not landed: the wave's landings are not over


def test_a_deferred_or_cancelled_batch_does_not_hold_the_waves_close_out() -> None:
    snap = _wave({"a": (1, "merged"), "b": (1, "cancelled"), "c": (1, "abandoned")})
    assert _closeouts(snap) == [("a",)]


def test_one_close_out_takes_the_whole_wave_and_another_wave_gets_its_own() -> None:
    snap = _wave({"a": (1, "merged"), "b": (1, "merged"), "c": (2, "merged")})
    plan = drive_pass(snap)
    (first,) = [a for a in plan.actions if a.kind == "closeout"]
    assert first.items == ("a", "b")  # the lowest wave; one at a time per repo (R15)


def test_the_post_merge_of_every_landing_is_planned_before_the_waves_close_out() -> None:
    snap = _wave({"a": (1, "merged"), "b": (1, "merged")}, post_merge_repos=frozenset({REPO}),
                 a_events=[POST_MERGE])  # fmt: skip
    kinds = [(a.kind, a.batch) for a in drive_pass(snap).actions]
    # R15: b's landing has none yet, so the wave's close-out waits for it (never starts
    # with a alone)
    assert kinds == [("post-merge", "b"), ("held", "b")]
    done = _wave({"a": (1, "merged"), "b": (1, "merged")}, post_merge_repos=frozenset({REPO}),
                 a_events=[POST_MERGE], b_events=[POST_MERGE])  # fmt: skip
    assert [a.kind for a in drive_pass(done).actions] == ["closeout"]


def test_a_tester_gated_batch_is_left_out_and_its_own_close_out_follows_its_gate() -> None:
    gated = {"b": GateLedger(pr=7, labels=frozenset({"gate:tester"}))}
    snap = _wave({"a": (1, "merged"), "b": (1, "merged")}, ledgers=gated)
    assert _closeouts(snap) == [("a",)]
    # the gate passed: the batch is owed a close-out of its own, in a later pass
    passed = {"b": GateLedger(pr=7, labels=frozenset({"gate:tester", "gate:tester-passed"}))}
    later = _wave({"a": (1, "merged"), "b": (1, "merged")}, ledgers=passed,
                  a_events=[{"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake",
                             "handle": "h", "run": "r", "archive": "chore/closeout-x-1",
                             "archived": 9}])  # fmt: skip
    assert _closeouts(later) == [("b",)]


def test_a_batch_with_no_wave_stands_alone() -> None:
    snap = _wave({"a": (None, "merged"), "b": (1, "pr-open")})
    assert wave_landings_done(snap, REPO, None) and _closeouts(snap) == [("a",)]


def test_under_quiet_or_stealth_the_queue_holds_batch_prs_only() -> None:
    batches = [_batch("a", 1)]
    for placement in ("quiet", "stealth"):
        snap = _snap(batches, {"a": "pr-open"}, placements={REPO: placement},
                     queue_closeouts={REPO: False}, wave_queues={REPO: _config()})  # fmt: skip
        qs = queue_snapshot(snap, REPO, admitted=[_closeout_entry()])
        assert qs.closeout_landed is None and qs.others == ()
    repo_snap = _snap(batches, {"a": "pr-open"}, queue_closeouts={REPO: False},
                      wave_queues={REPO: _config()})  # fmt: skip
    qs = queue_snapshot(repo_snap, REPO, admitted=[_closeout_entry()])
    assert qs.closeout_landed is False and [o.kind for o in qs.others] == ["closeout"]


def _closeout_entry() -> Admitted:
    return Admitted("closeout", REPO, _live(900, "h900", head_ref="chore/closeout-x-1"),
                    batch="a", wave=1, at=NOW)  # fmt: skip


def _config() -> Any:
    from fr.triage.wave_queue import QueueConfig

    return QueueConfig()


def test_p6_r6_one_member_without_its_post_merge_holds_the_whole_close_out() -> None:
    """Wave {a, b}: b's post_merge has not succeeded, so no close-out starts, not even for a;
    once it has, exactly one close-out takes both."""
    repos = frozenset({REPO})
    held = _wave({"a": (1, "merged"), "b": (1, "merged")}, post_merge_repos=repos,
                 a_events=[POST_MERGE])  # fmt: skip
    assert _closeouts(held) == []
    assert [a.kind for a in drive_pass(held).actions if a.kind == "held"] == ["held"]
    done = _wave({"a": (1, "merged"), "b": (1, "merged")}, post_merge_repos=repos,
                 a_events=[POST_MERGE], b_events=[POST_MERGE])  # fmt: skip
    assert _closeouts(done) == [("a", "b")]
