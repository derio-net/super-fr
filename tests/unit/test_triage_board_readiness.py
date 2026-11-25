"""The board's cards carry the queue plan's verdicts (spec 2026-11-24-batch-merge-readiness
§C, R4, R7, R8).

`build_board` reads the readiness map from the plan it already builds; the board's `LivePr`
carries the PR's merge state; the board and the queue, fed one set of facts, agree.
"""

from __future__ import annotations

from typing import Any

import pytest
from fr.triage.kanban import _default_plan, build_board
from fr.triage.readiness import snapshot_readiness
from fr.triage.scope_config import scope_id
from fr.triage.views import drive_snapshot
from fr.triage.wave_queue import plan_queue

from tests.unit.triage_board_fixtures import (
    DELIVERED,
    REPO,
    dispatch,
    facts,
    issue,
    j,
    judgements,
    pr,
)
from tests.unit.triage_board_fixtures import batch as mk_batch

APPROVED = ["approved-fr"]
CLOSEOUT = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "hand", "handle": "c",
            "archive": "chore/archive-m", "run": "r-m"}  # fmt: skip


def _world(extra: dict[str, Any] | None = None, **kw: Any) -> Any:
    kw.setdefault("labels", APPROVED)
    p = pr(11, "feat/batch-a", **{**DELIVERED, **kw})
    f = facts([issue(1, prs=[p])], schema=12, config={REPO: {"queue": {"ci": "push"}}})
    jd = judgements({"widgets#1": j(1)}, [mk_batch("a", [1], events=[dispatch("a")])],
                    **(extra or {}))  # fmt: skip
    return f, jd


def test_a_batch_pr_card_carries_the_plans_verdict_and_facts() -> None:
    f, jd = _world()
    card = build_board(f, jd, {}).card("a")
    assert card.readiness is not None
    assert (card.readiness.kind, card.readiness.verdict) == ("merges-next", "Approved, merges next")
    assert card.readiness.facts.delivered == "yes"
    assert card.readiness.facts.merge == "unknown"  # the fixture names no merge state


def test_an_undelivered_card_says_so_whatever_its_label_says() -> None:
    f, jd = _world(cursor={"run": "r1", "step": "deliver", "kind": "none", "unit": None})
    card = build_board(f, jd, {}).card("a")
    assert card.readiness is not None
    assert card.readiness.verdict == "Approved, not delivered"
    assert not card.readiness.admits


def test_a_card_with_no_open_pr_has_no_verdict() -> None:
    f = facts([issue(1)])
    jd = judgements({"widgets#1": j(1)}, [mk_batch("a", [1])])
    card = build_board(f, jd, {}).card("a")
    assert card.readiness is None and card.others == ()


def test_the_boards_live_pr_carries_the_merge_state() -> None:
    f, jd = _world(mergeable="CONFLICTING", merge_state="DIRTY")
    live = drive_snapshot(f, jd).live["a"]
    assert (live.mergeable, live.merge_state) == ("CONFLICTING", "DIRTY")
    card = build_board(f, jd, {}).card("a")
    assert card.readiness is not None
    assert card.readiness.facts.merge.startswith("conflicting")


@pytest.mark.parametrize(
    "kw",
    [{}, {"labels": []}, {"checks": {"pass": 1, "fail": 1, "pending": 0}},
     {"checks": {"pass": 1, "fail": 0, "pending": 1}}, {"mergeable": "CONFLICTING"},
     {"cursor": {"run": "r1", "step": "review", "kind": "none", "unit": None}}],
)  # fmt: skip
def test_the_board_and_the_queue_read_one_verdict_from_one_set_of_facts(kw: dict[str, Any]) -> None:
    from fr.triage.batch_drive import queue_snapshot

    f, jd = _world(**kw)
    snapshot, plan = _default_plan(f, jd)
    batch = jd.batches[0]
    queue = plan_queue(queue_snapshot(snapshot, REPO)).readiness["a"]
    board = build_board(f, jd, {}).card("a").readiness
    assert board is not None
    assert (board.verdict, board.admits) == (queue.verdict, queue.admits)
    assert snapshot_readiness(snapshot, batch).admits == board.admits
    assert plan.queues[0].readiness["a"].verdict == board.verdict


def test_a_queue_held_repos_card_reads_not_ready_queue_held() -> None:
    halt = {"kind": "queue_halt", "at": "2026-10-02T10:00:00Z", "state": "held",
            "detail": "the remote refused the push", "land": "push"}  # fmt: skip
    record = {"repo": REPO, "wave": None, "scope": scope_id("example-org--widgets"),
              "base": "m" * 40, "events": [{"kind": "queue_open", "at": "2026-10-02T09:00:00Z"},
                                           halt]}  # fmt: skip
    f, jd = _world(extra={"schema": 13, "queues": [record]})
    card = build_board(f, jd, {}).card("a")
    assert card.readiness is not None
    assert card.readiness.verdict == "Not ready: queue held: held: the remote refused the push"


def _closing(archive: dict[str, Any]) -> Any:
    f = facts([issue(1, state="closed", prs=[pr(10, "feat/batch-m", state="MERGED")]),
               issue(2, prs=[archive])],
              config={REPO: {"queue": {"ci": "push"}}})  # fmt: skip
    jd = judgements({k: j(1) for k in ("widgets#1", "widgets#2")},
                    [mk_batch("m", [1], events=[dispatch("m"), CLOSEOUT])])  # fmt: skip
    return f, jd


def test_an_archive_pr_on_a_card_carries_its_verdict() -> None:
    """R8: the board's facts name no default branch, so the card says what it cannot judge."""
    archive = pr(30, "chore/archive-m", files=["docs/superpowers/runs/r-m.yaml"])
    f, jd = _closing(archive)
    card = build_board(f, jd, {}).card("m")
    (other,) = card.others
    assert other.entry is not None and other.entry.key == "archive#30"
    assert not other.admits
    assert other.verdict.startswith("Not ready: ")
    assert other.facts.delivered == other.reason


def test_a_conflicting_archive_pr_reads_conflicting() -> None:
    archive = pr(30, "chore/archive-m", files=["docs/superpowers/runs/r-m.yaml"],
                 mergeable="CONFLICTING")  # fmt: skip
    f, jd = _closing(archive)
    (other,) = build_board(f, jd, {}).card("m").others
    assert other.verdict == "Not ready: conflicts with the default branch"


def test_plan_entries_with_no_batch_are_the_boards_not_a_cards() -> None:
    from dataclasses import replace

    from fr.triage.batch_drive import LivePr
    from fr.triage.kanban import _others_of
    from fr.triage.readiness import other_readiness
    from fr.triage.wave_queue import OtherEntry

    snapshot, plan = _default_plan(*_world())
    live = LivePr(7, "OPEN", False, "h7", "green", base="main")
    export = OtherEntry("export#7", "export", 7)
    qs = replace(
        __import__("fr.triage.batch_drive", fromlist=["queue_snapshot"]).queue_snapshot(
            snapshot, REPO
        ),
        others=(export,),
    )
    qs = replace(qs, live={**qs.live, "export#7": live})
    queue = replace(plan.queues[0], readiness={"export#7": other_readiness("export#7", qs)})
    grouped = _others_of(replace(plan, queues=(queue,)))
    assert [r.entry.key for r in grouped[""] if r.entry] == ["export#7"]
