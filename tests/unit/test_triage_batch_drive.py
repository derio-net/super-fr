"""The wave driver's pure pass (wave-driver spec §B, §C; Test Plan 2, 3, 4, 11).

`fr.triage.batch_drive.drive_pass` is a function of a `Snapshot` alone: no
forge, no runner, no git, no clock. Every test here builds a snapshot by hand
and reads the ordered actions it returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.batch import ForeignPr, QueueEntry, batch_item_id
from fr.triage.batch_drive import (
    CLOSEOUT_FALLBACK,
    Action,
    LivePr,
    Snapshot,
    Train,
    action_line,
    attributed,
    checks_verdict,
    closeout_brief,
    closeout_item_id,
    default_selection,
    drive_pass,
    find_run,
    housekeeping_branch,
    is_archived,
    is_finished,
    summary_line,
    train_line,
    unfinished_waves,
    wave_group,
)
from fr.triage.model import Batch, Export, PullRequest

REPO = "derio-net/super-fr"
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
DISPATCHED = "2026-10-01T10:00:00Z"
RUNS = "docs/superpowers/runs"


def _batch(bid: str, n: int, *, wave: int | None = 1, **kw: Any) -> Batch:
    doc: dict[str, Any] = {"id": bid, "title": bid, "ids": [f"super-fr#{n}"], "wave": wave, **kw}
    return Batch.model_validate(doc)


def _dispatched(bid: str, n: int, **kw: Any) -> Batch:
    skill = kw.get("skill", "goal")
    branch = f"{'fix' if skill == 'debug' else 'feat'}/batch-{bid}"
    events = [
        {"kind": "dispatch", "at": DISPATCHED, "runner": "fake", "handle": "h", "branch": branch},
        *kw.pop("events", []),
    ]
    return _batch(bid, n, events=events, **kw)


def _pr(bid: str, n: int, head: str = "", **kw: Any) -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=n,
        title=bid,
        state=kw.pop("state", "OPEN"),
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{n}",
        head_ref=kw.pop("head_ref", f"feat/batch-{bid}"),
        head_oid=head or f"head-{bid}",
        **kw,
    )


def _live(n: int, head: str, **kw: Any) -> LivePr:
    return LivePr(number=n, state=kw.pop("state", "OPEN"), draft=kw.pop("draft", False),
                  head=head, checks=kw.pop("checks", "green"), **kw)  # fmt: skip


def _snap(
    batches: Sequence[Batch],
    stages: dict[str, str],
    *,
    live: dict[str, LivePr] | None = None,
    repos: dict[str, str] | None = None,
    **kw: Any,
) -> Snapshot:
    queue = tuple(
        QueueEntry(batch=b, pr=_pr(b.id, 1000 + i)) for i, b in enumerate(batches)
        if stages.get(b.id) == "pr-open"
    )  # fmt: skip
    live = live if live is not None else {
        e.batch.id: _live(e.pr.number, e.pr.head_oid) for e in queue
    }  # fmt: skip
    kw.setdefault("default_branch", {REPO: "main"})
    return Snapshot(
        batches=tuple(batches),
        stages=stages,  # type: ignore[arg-type]
        queue=queue,
        live=live,
        repos=repos if repos is not None else {b.id: REPO for b in batches},
        now=kw.pop("now", NOW),
        **kw,
    )


def _kinds(actions: Sequence[Action]) -> list[tuple[str, str]]:
    return [(a.kind, a.batch) for a in actions]


# ------------------------------------------------------------ dispatch (R3)


def test_the_in_flight_cap_holds_and_waves_go_in_order() -> None:
    batches = [
        _batch("w2-a", 1, wave=2),
        _batch("w1-c", 2, wave=1),
        _batch("w1-a", 3, wave=1),
        _batch("w1-b", 4, wave=1, order=1),
        _batch("w2-b", 5, wave=2),
        _batch("w1-d", 6, wave=1),
    ]
    stages = {b.id: "proposed" for b in batches}
    got = drive_pass(_snap(batches, stages, max_inflight=4))
    # wave first, then merge order (explicit `order` first), then id
    assert _kinds(got.actions) == [
        ("dispatch", "w1-b"),
        ("dispatch", "w1-a"),
        ("dispatch", "w1-c"),
        ("dispatch", "w1-d"),
        ("held", "w2-a"),
        ("held", "w2-b"),
    ]
    assert got.summary.in_flight == 4 and got.summary.pending == 2


def test_in_flight_batches_count_against_the_cap() -> None:
    batches = [_dispatched("old", 1), _batch("new", 2), _batch("newer", 3)]
    stages = {"old": "dispatched", "new": "proposed", "newer": "proposed"}
    got = drive_pass(_snap(batches, stages, max_inflight=2))
    assert _kinds(got.actions) == [("dispatch", "new"), ("held", "newer")]
    # a slot this pass's own dispatch took is named with the rest
    assert got.actions[-1].detail == "the in-flight cap (2) is full: new, old"


def test_a_batch_the_cap_holds_says_so_and_names_the_occupants() -> None:
    """gh#913: with the cap full of unselected batches, the selection's summary reads
    idle (in flight 0, pending 2); the plan must say what holds it."""
    others = [_dispatched(f"o{n}", n) for n in range(1, 5)]
    batches = [*others, _batch("new-a", 5), _batch("new-b", 6)]
    stages = {**{b.id: "dispatched" for b in others}, "new-a": "proposed", "new-b": "proposed"}
    got = drive_pass(_snap(batches, stages, selected=frozenset({"new-a", "new-b"})))
    assert [action_line(a) for a in got.actions] == [
        "held new-a: the in-flight cap (4) is full: o1, o2, o3, o4",
        "held new-b: the in-flight cap (4) is full: o1, o2, o3, o4",
    ]
    assert got.summary.in_flight == 0 and got.summary.pending == 2


def test_a_batch_waiting_on_an_unmerged_dependency_is_skipped() -> None:
    batches = [_dispatched("base", 1), _batch("child", 2, after=["base"]), _batch("free", 3)]
    stages = {"base": "dispatched", "child": "proposed", "free": "proposed"}
    got = drive_pass(_snap(batches, stages))
    assert _kinds(got.actions) == [("dispatch", "free")]
    assert got.summary.pending == 1


def test_a_merged_dependency_lets_the_dependent_start() -> None:
    batches = [_dispatched("base", 1), _batch("child", 2, after=["base"])]
    stages = {"base": "merged", "child": "proposed"}
    got = drive_pass(_snap(batches, stages, released=frozenset({"base"}), existing=frozenset()))
    assert ("dispatch", "child") in _kinds(got.actions)


@pytest.mark.parametrize("dep_stage", ["cancelled", "abandoned", "partial"])
def test_an_unsatisfiable_dependency_blocks_and_never_dispatches(dep_stage: str) -> None:
    batches = [_dispatched("base", 1), _batch("child", 2, after=["base"])]
    stages = {"base": dep_stage, "child": "proposed"}
    got = drive_pass(_snap(batches, stages, released=frozenset({"base"})))
    assert ("blocked", "child") in _kinds(got.actions)
    assert ("dispatch", "child") not in _kinds(got.actions)
    blocked = next(a for a in got.actions if a.kind == "blocked")
    assert "base" in blocked.detail and dep_stage in blocked.detail


def test_a_merge_frees_a_slot_used_in_the_same_pass() -> None:
    batches = [_dispatched("done", 1), _batch("next", 2)]
    stages = {"done": "pr-open", "next": "proposed"}
    got = drive_pass(_snap(batches, stages, max_inflight=1))
    assert _kinds(got.actions) == [("merge", "done"), ("dispatch", "next")]


def test_only_proposed_batches_are_dispatched() -> None:
    batches = [_dispatched("gone", 1, events=[{"kind": "cancel", "at": "2026-10-01T11:00:00Z"}])]
    got = drive_pass(_snap(batches, {"gone": "cancelled"}))
    assert got.actions == ()
    assert got.summary.done


# ------------------------------------------------------------- merge (R4)


@pytest.mark.parametrize(
    ("live", "why"),
    [
        (dict(draft=True), "draft"),
        (dict(checks="pending"), "pending"),
        (dict(checks="failing", failing=("lint",)), "failing"),
    ],
)
def test_a_pr_that_is_not_ready_and_green_is_never_merged(live: dict[str, Any], why: str) -> None:
    b = _dispatched("x", 1)
    got = drive_pass(_snap([b], {"x": "pr-open"}, live={"x": _live(1000, "head-x", **live)}))
    assert "merge" not in [a.kind for a in got.actions]
    assert got.summary.in_flight == 1


def test_a_moved_head_is_never_merged() -> None:
    b = _dispatched("x", 1)
    got = drive_pass(_snap([b], {"x": "pr-open"}, live={"x": _live(1000, "elsewhere")}))
    assert got.actions == ()


def test_a_ready_green_pr_is_merged_at_its_head() -> None:
    b = _dispatched("x", 1)
    (action,) = drive_pass(_snap([b], {"x": "pr-open"})).actions
    assert (action.kind, action.pr, action.head) == ("merge", 1000, "head-x")


def test_a_failing_check_warns_once_per_head_sha() -> None:
    b = _dispatched("x", 1)
    live = {"x": _live(1000, "head-x", checks="failing", failing=("lint",))}
    first = drive_pass(_snap([b], {"x": "pr-open"}, live=live))
    assert _kinds(first.actions) == [("warn", "x")]
    assert first.actions[0].head == "head-x" and "lint" in first.actions[0].detail
    again = drive_pass(_snap([b], {"x": "pr-open"}, live=live, warned=frozenset({"head-x"})))
    assert again.actions == ()


def _foreign(n: int, reason: str = "opened from a fork") -> ForeignPr:
    return ForeignPr(pr=_pr("x", n, head_ref="feat/batch-x"), reason=reason)


def test_a_foreign_pr_on_a_batch_branch_is_reported_once_and_never_merged() -> None:
    """gh#936: the PR is reported (the key is what the driver remembers), never merged."""
    b = _dispatched("x", 1)
    foreign = {"x": (_foreign(80), _foreign(81, "by mallory, not an allowed author"))}
    first = drive_pass(_snap([b], {"x": "dispatched"}, foreign=foreign))
    assert _kinds(first.actions) == [("foreign", "x"), ("foreign", "x")]
    assert [(a.pr, a.head) for a in first.actions] == [
        (80, f"foreign:{REPO}#80"),
        (81, f"foreign:{REPO}#81"),
    ]
    assert first.actions[0].detail == (
        "PR #80 on feat/batch-x is not this batch's: opened from a fork; it is never merged"
    )
    again = drive_pass(
        _snap([b], {"x": "dispatched"}, foreign=foreign, warned=frozenset({f"foreign:{REPO}#80"}))
    )
    assert [a.pr for a in again.actions] == [81]
    assert "merge" not in [a.kind for a in [*first.actions, *again.actions]]


def test_a_foreign_pr_is_reported_only_for_a_selected_batch() -> None:
    b = _dispatched("x", 1)
    got = drive_pass(
        _snap([b], {"x": "dispatched"}, foreign={"x": (_foreign(80),)}, selected=frozenset())
    )
    assert got.actions == ()


def test_merges_follow_the_merge_order() -> None:
    batches = [_dispatched("b", 1, order=2), _dispatched("a", 2, order=1)]
    got = drive_pass(_snap(batches, {"a": "pr-open", "b": "pr-open"}))
    assert _kinds(got.actions) == [("merge", "a"), ("merge", "b")]


def test_checks_verdict_uses_required_checks_when_the_branch_has_any() -> None:
    required = [{"name": "test", "bucket": "pass"}, {"name": "x", "bucket": "skipping"}]
    assert checks_verdict(required, {"pass": 1, "fail": 3, "pending": 0}, ci_none=False) == (
        "green",
        (),
    )
    failing = [{"name": "lint", "bucket": "fail"}]
    assert checks_verdict(failing, {}, ci_none=False) == ("failing", ("lint",))
    pending = [{"name": "test", "bucket": "pending"}]
    assert checks_verdict(pending, {}, ci_none=False)[0] == "pending"


def test_checks_verdict_falls_back_to_all_checks_without_required_ones() -> None:
    assert checks_verdict([], {"pass": 2, "fail": 1, "pending": 0}, ci_none=False)[0] == "failing"
    assert checks_verdict([], {"pass": 2, "fail": 0, "pending": 1}, ci_none=False)[0] == "pending"
    assert checks_verdict([], {"pass": 2, "fail": 0, "pending": 0}, ci_none=False)[0] == "green"


def test_a_ci_none_repo_is_green_on_non_draft_alone() -> None:
    assert checks_verdict([{"name": "t", "bucket": "pending"}], {"pending": 4}, ci_none=True) == (
        "green",
        (),
    )


# -------------------------------------------------------- close-out (R5, R14)


def _merged(bid: str, n: int, **kw: Any) -> Batch:
    return _dispatched(bid, n, **kw)


def test_one_closeout_per_merged_batch_once_released() -> None:
    b = _merged("x", 1)
    got = drive_pass(_snap([b], {"x": "merged"}, released=frozenset({"x"}), merged_at={"x": NOW}))
    (action,) = got.actions
    assert (action.kind, action.batch, action.recorded, action.post_merge) == (
        "closeout", "x", False, True,
    )  # fmt: skip
    assert got.summary.closing == 1


def test_no_closeout_before_the_release_commit_or_the_fallback() -> None:
    b = _merged("x", 1)
    snap = _snap([b], {"x": "merged"}, merged_at={"x": NOW - timedelta(minutes=9)})
    got = drive_pass(snap)
    assert got.actions == ()
    assert got.summary.closing == 1 and not got.summary.done


def test_the_ten_minute_fallback_starts_the_closeout_without_a_release() -> None:
    b = _merged("x", 1)
    snap = _snap([b], {"x": "merged"}, merged_at={"x": NOW - CLOSEOUT_FALLBACK})
    assert _kinds(drive_pass(snap).actions) == [("closeout", "x")]


def test_a_partial_batch_still_gets_its_closeout() -> None:
    b = _merged("x", 1)
    snap = _snap([b], {"x": "partial"}, released=frozenset({"x"}))
    assert _kinds(drive_pass(snap).actions) == [("closeout", "x")]


def test_a_closed_out_batch_is_not_closed_out_again() -> None:
    event = {"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h"}
    b = _merged("x", 1, events=[event])
    got = drive_pass(_snap([b], {"x": "merged"}, released=frozenset({"x"})))
    assert got.actions == ()


def test_an_existing_closeout_tab_is_recorded_not_redispatched() -> None:
    b = _merged("x", 1)
    snap = _snap(
        [b],
        {"x": "merged"},
        released=frozenset({"x"}),
        existing=frozenset({closeout_item_id(REPO, "x")}),
    )
    (action,) = drive_pass(snap).actions
    assert (action.kind, action.recorded) == ("closeout", True)


def test_post_merge_is_owed_only_until_its_event_exists() -> None:
    event = {"kind": "post_merge", "at": "2026-10-02T11:00:00Z"}
    b = _merged("x", 1, events=[event])
    (action,) = drive_pass(_snap([b], {"x": "merged"}, released=frozenset({"x"}))).actions
    assert action.post_merge is False


def test_an_archived_batch_is_not_closed_out() -> None:
    """Closed out by hand before the driver existed: no close-out event, but its
    run's artifacts are archived on the default branch (debug 2026-10-03: 50 such
    batches on this repo were each planned a close-out)."""
    b = _merged("old", 1, wave=None)
    snap = _snap([b], {"old": "merged"}, released=frozenset({"old"}),
                 archived=frozenset({"old"}))  # fmt: skip
    got = drive_pass(snap)
    # recorded once, so no later pass re-probes it and the board sees it (gh#899, gh#900)
    assert [(a.kind, a.batch, a.pr, a.archived) for a in got.actions] == [("adopt", "old", None, 0)]
    assert got.summary.closing == 0 and got.summary.done


def test_an_open_hand_opened_closeout_pr_is_adopted_not_doubled() -> None:
    """gh#912: a close-out started by hand left its PR open on
    `chore/closeout-<batch branch>`; the driver records it instead of starting a
    second session, due or not, and the batch is still closing."""
    b = _merged("x", 1)
    hand = _live(895, "h895", head_ref="chore/closeout-feat-batch-x")
    for released in (frozenset(), frozenset({"x"})):
        got = drive_pass(_snap([b], {"x": "merged"}, released=released, adopted={"x": hand}))
        assert [(a.kind, a.pr, a.archived) for a in got.actions] == [("adopt", 895, None)]
        assert got.summary.closing == 1


def test_a_merged_hand_opened_closeout_pr_finishes_the_batch() -> None:
    b = _merged("x", 1)
    hand = _live(895, "", state="MERGED", head_ref="chore/closeout-feat-batch-x")
    got = drive_pass(_snap([b], {"x": "merged"}, adopted={"x": hand}))
    assert [(a.kind, a.pr, a.archived) for a in got.actions] == [("adopt", 895, 895)]
    assert got.summary.closing == 0 and got.summary.done


def test_a_recorded_closeout_is_never_adopted() -> None:
    event = {"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h"}
    b = _merged("x", 1, events=[event])
    hand = _live(895, "h895", head_ref="chore/closeout-feat-batch-x")
    snap = _snap([b], {"x": "merged"}, adopted={"x": hand}, archived=frozenset({"x"}))
    assert all(a.kind != "adopt" for a in drive_pass(snap).actions)


def test_a_merged_batch_without_a_wave_is_still_closed_out() -> None:
    """Having no wave is no reason to skip a close-out: an unnamed drive on a repo
    with no waves dispatches wave-less batches, and each must close out (and run
    its post_merge) once it merges."""
    loose = _merged("loose", 1, wave=None)
    snap = _snap([loose], {"loose": "merged"}, released=frozenset({"loose"}))
    assert _kinds(drive_pass(snap).actions) == [("closeout", "loose")]


@pytest.mark.parametrize(
    ("added", "live", "archived"),
    [
        (["docs/superpowers/journals/debug/d.md"], set(), True),
        (["docs/superpowers/journals/debug/d.md"], {"docs/superpowers/journals/debug/d.md"}, False),
        (["docs/superpowers/plans/p/_meta.yaml", "docs/superpowers/runs/r.yaml"],
         {"docs/superpowers/runs/r.yaml"}, False),
        (["docs/superpowers/plans/p/_meta.yaml", "docs/superpowers/specs/s.md",
          "docs/superpowers/usage/r.yaml", "packages/x.py"], {"packages/x.py"}, True),
        # no evidence: the PR added no run artifact (or the merge is unknown)
        ([], set(), False),
        (["packages/x.py", "docs/superpowers/implemented/specs/s.md"], set(), False),
    ],
)  # fmt: skip
def test_is_archived_needs_an_added_run_artifact_and_none_still_live(
    added: list[str], live: set[str], archived: bool
) -> None:
    assert is_archived(added, live.__contains__) is archived


def test_closeout_comes_before_dispatch_in_a_pass() -> None:
    batches = [_merged("x", 1), _batch("y", 2)]
    snap = _snap(batches, {"x": "merged", "y": "proposed"}, released=frozenset({"x"}))
    assert _kinds(drive_pass(snap).actions) == [("closeout", "x"), ("dispatch", "y")]


def test_the_closeout_item_id_is_a_run_item_per_batch() -> None:
    assert closeout_item_id(REPO, "x") == f"{REPO}/run/closeout-x"


def test_find_run_picks_the_cursor_naming_the_batch_branch() -> None:
    cursors = [
        {"run": "r-other", "branch": "feat/other"},
        {
            "run": "r-x",
            "branch": "feat/batch-x",
            "steps": {"plan": {"emitted": {"plan": "docs/superpowers/plans/2026-10-01-x"}}},
        },
        "not a mapping",
    ]
    assert find_run(cursors, "feat/batch-x") == ("r-x", "2026-10-01-x")
    assert find_run(cursors, "fix/batch-y") is None


def test_the_brief_uses_run_for_a_cursor_else_branch() -> None:
    goal = closeout_brief(_merged("x", 1), run="r-x", checkout=Path("/w/x"))
    assert "fr pickup --run r-x" in goal and "/w/x" in goal
    debug = closeout_brief(_merged("y", 2, skill="debug"), run=None, checkout=Path("/w/y"))
    assert "fr pickup --branch fix/batch-y" in debug


def test_housekeeping_branch_mirrors_closeout_naming() -> None:
    assert (
        housekeeping_branch("feat/batch-x", "r-x", "2026-10-01-x") == "chore/archive-2026-10-01-x"
    )
    assert housekeeping_branch("feat/batch-x", "r-x", None) == "chore/closeout-r-x"
    assert housekeeping_branch("fix/batch-y", None, None) == "chore/closeout-fix-batch-y"


# ------------------------------------------------------------- archive (R5)


def _closed(bid: str, n: int, *, archive: str | None = None, run: str | None = None) -> Batch:
    event: dict[str, Any] = {
        "kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h",
        "run": run, "archive": archive,
    }  # fmt: skip
    return _merged(bid, n, events=[event])


def _archive(n: int, head_ref: str, **kw: Any) -> LivePr:
    """An archive PR candidate based on the default branch, as `_snap` names it."""
    return _live(n, f"h{n}", head_ref=head_ref, trusted=kw.pop("trusted", True),
                 base=kw.pop("base", "main"), **kw)  # fmt: skip


def test_an_attributed_ready_green_archive_pr_is_merged() -> None:
    b = _closed("x", 1, archive="chore/archive-2026-10-01-x", run="r-x")
    pr = _archive(7, "chore/archive-2026-10-01-x", files=("docs/superpowers/runs/r-x.yaml",))
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (pr,)}))
    (action,) = got.actions
    assert (action.kind, action.pr, action.head) == ("archive", 7, "h7")


@pytest.mark.parametrize("kw", [dict(draft=True), dict(checks="pending"), dict(checks="failing")])
def test_an_archive_pr_not_ready_and_green_waits(kw: dict[str, Any]) -> None:
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    pr = _archive(7, "chore/archive-p", files=(f"{RUNS}/r-x.yaml",), **kw)
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (pr,)}))
    assert [a.kind for a in got.actions if a.kind == "archive"] == []
    assert got.summary.closing == 1


def test_an_unattributed_archive_pr_is_never_merged() -> None:
    b = _closed("x", 1, archive="chore/archive-p")
    other = _archive(8, "chore/archive-someone-else", files=("docs/a.md",))
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (other,)}))
    assert got.actions == ()


def test_attribution_by_head_or_by_the_run_file() -> None:
    b = _closed("x", 1, run="r-x")
    event = b.events[-1]
    by_branch = _archive(1, "chore/closeout-feat-batch-x")
    by_file = _archive(2, "chore/archive-other", files=("docs/superpowers/runs/r-x.yaml",))
    stray = _archive(3, "feat/thing", files=("docs/superpowers/runs/r-x.yaml",))
    assert attributed(by_branch, b, event)  # type: ignore[arg-type]
    assert attributed(by_file, b, event)  # type: ignore[arg-type]
    assert not attributed(stray, b, event)  # type: ignore[arg-type]


def test_an_untrusted_archive_pr_is_never_attributed_or_merged() -> None:
    """gh#936: a fork or a foreign author can name a head `chore/closeout-<branch>`
    and touch the run file; neither attributes a PR whose identity is not trusted."""
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    event = b.events[-1]
    by_head = _archive(1, "chore/closeout-feat-batch-x", trusted=False)
    by_file = _archive(2, "chore/archive-p", files=(f"{RUNS}/r-x.yaml",), trusted=False)
    assert not attributed(by_head, b, event)  # type: ignore[arg-type]
    assert not attributed(by_file, b, event)  # type: ignore[arg-type]
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (by_head, by_file)}))
    assert "archive" not in [a.kind for a in got.actions]


def test_a_live_pr_is_untrusted_unless_said_otherwise() -> None:
    assert LivePr(number=1, state="OPEN", draft=False, head="h").trusted is False


def test_a_merged_archive_pr_finishes_the_batch() -> None:
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    merged = _archive(7, "chore/archive-p", state="MERGED", files=(f"{RUNS}/r-x.yaml",))
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (merged,)}))
    # Merged by someone else: recorded once, so `batch list` reads it (gh#882).
    assert [(a.kind, a.batch, a.pr, a.archived) for a in got.actions] == [("adopt", "x", 7, 7)]
    assert got.summary.closing == 0 and got.summary.done


def test_a_recorded_archive_is_not_recorded_again() -> None:
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    recorded = b.events[-1].model_copy(update={"at": NOW, "archived": 7})
    b = b.model_copy(update={"events": [*b.events, recorded]})
    merged = _archive(7, "chore/archive-p", state="MERGED", files=(f"{RUNS}/r-x.yaml",))
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (merged,)}))
    assert got.actions == ()


# --------------------------------------------------------------- lines (R13)


def test_one_line_per_action_and_a_summary() -> None:
    a = Action(kind="merge", batch="x", detail="PR #1000 at head-x", pr=1000, head="head-x")
    assert action_line(a) == "merge x: PR #1000 at head-x"
    assert action_line(a, "merged PR #1000") == "merge x: merged PR #1000"
    batches = [_dispatched("x", 1)]
    got = drive_pass(_snap(batches, {"x": "pr-open"}))
    assert summary_line(got.summary) == "in flight 0, merged 1, pending 0, closing 1"


# ------------------------------------------------------------- purity (R8)


def test_the_pass_module_reaches_no_runner_git_process_or_clock() -> None:
    import ast

    from tests.unit.triage_fixtures import forbidden_imports

    path = Path(__file__).resolve().parents[2] / "packages/fr/src/fr/triage/batch_drive.py"
    banned = ("fr_dispatch", "subprocess", "fr.triage.gitseam", "os", "time", "shutil")
    assert forbidden_imports(path, "fr.triage", banned) == []
    calls = {
        n.func.attr
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert not calls & {"now", "utcnow", "today"}


# ------------------------------------------- review fixes (phase 2 review rg-*)


def test_the_cap_counts_in_flight_batches_outside_the_selection() -> None:
    """rg-3: `drive b5` with four other batches in flight dispatches nothing."""
    others = [_dispatched(f"o{i}", i) for i in range(1, 5)]
    b5 = _batch("b5", 5)
    stages = {**{b.id: "dispatched" for b in others}, "b5": "proposed"}
    got = drive_pass(_snap([*others, b5], stages, selected=frozenset({"b5"}), max_inflight=4))
    assert _kinds(got.actions) == [("held", "b5")]  # held, and says so (gh#913)
    assert got.summary.pending == 1 and not got.summary.done


def test_a_dependency_outside_the_selection_resolves_by_its_stage() -> None:
    """rg-3: `drive b2` where b1 (unselected) is merged does not report b2 blocked."""
    batches = [_dispatched("b1", 1), _batch("b2", 2, after=["b1"])]
    stages = {"b1": "merged", "b2": "proposed"}
    got = drive_pass(_snap(batches, stages, selected=frozenset({"b2"})))
    assert _kinds(got.actions) == [("dispatch", "b2")]


def test_only_selected_batches_are_acted_on() -> None:
    batches = [_dispatched("in", 1), _dispatched("out", 2), _batch("p", 3)]
    stages = {"in": "pr-open", "out": "pr-open", "p": "proposed"}
    got = drive_pass(_snap(batches, stages, selected=frozenset({"in", "p"})))
    assert _kinds(got.actions) == [("merge", "in"), ("dispatch", "p")]


def test_unknown_merge_time_is_not_yet_due() -> None:
    """rg-9: no merge time and no release is not a reason to close out now."""
    snap = _snap([_merged("x", 1)], {"x": "merged"})
    got = drive_pass(snap)
    assert got.actions == () and got.summary.closing == 1


@pytest.mark.parametrize("all_checks", [{}, {"pass": 0, "fail": 0, "pending": 0}])
def test_zero_reported_checks_are_pending_not_green(all_checks: dict[str, int]) -> None:
    """rg-4: no check registered yet (a fresh push, a just-readied PR) is not green."""
    assert checks_verdict([], all_checks, ci_none=False)[0] == "pending"
    assert checks_verdict([], all_checks, ci_none=True)[0] == "green"


def test_head_only_attribution_is_the_branch_named_closeout_alone() -> None:
    """rg-12: `chore/archive-<plan>` and `chore/closeout-<run>` need the run file or
    the journal in their files; only `chore/closeout-<batch branch>` is head-only."""
    b = _closed("x", 1, archive="chore/archive-2026-10-01-x", run="r-x")
    event = b.events[-1]
    bare = _archive(1, "chore/archive-2026-10-01-x")
    by_run = _archive(2, "chore/archive-2026-10-01-x", files=("docs/superpowers/runs/r-x.yaml",))
    journal = "docs/superpowers/journals/plans/2026-10-01-x.md"
    by_journal = _archive(3, "chore/archive-2026-10-01-x", files=(journal,))
    run_head = _archive(4, "chore/closeout-r-x")
    branch_head = _archive(5, "chore/closeout-feat-batch-x")
    assert not attributed(bare, b, event)  # type: ignore[arg-type]
    assert attributed(by_run, b, event)  # type: ignore[arg-type]
    assert attributed(by_journal, b, event)  # type: ignore[arg-type]
    assert not attributed(run_head, b, event)  # type: ignore[arg-type]
    assert attributed(branch_head, b, event)  # type: ignore[arg-type]


def test_a_recorded_archive_finishes_the_batch_without_the_pr_in_view() -> None:
    """rg-6: an archive the driver merged is recorded on the close-out event; the
    batch is finished even when no candidate lists that PR any more."""
    event: dict[str, Any] = {
        "kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h",
        "run": "r-x", "archive": "chore/archive-p", "archived": 77,
    }  # fmt: skip
    b = _merged("x", 1, events=[event])
    got = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: ()}))
    assert got.actions == () and got.summary.closing == 0 and got.summary.done


def test_only_blocked_work_left_is_not_done() -> None:
    """rg-11: blocked work needs the operator; the pass does not call it done."""
    batches = [_dispatched("base", 1), _batch("child", 2, after=["base"])]
    got = drive_pass(_snap(batches, {"base": "cancelled", "child": "proposed"}))
    assert got.summary.blocked == 1
    assert not got.summary.done and got.summary.waiting_on_operator


def test_settle_moves_a_merge_that_did_not_land_back_in_flight() -> None:
    """rg-1: the summary must not claim a merge that did not happen."""
    from fr.triage.batch_drive import settle

    batches = [_dispatched("b1", 1), _batch("b2", 2, after=["b1"])]
    got = drive_pass(_snap(batches, {"b1": "pr-open", "b2": "proposed"}))
    assert got.summary.merged == 1
    settled = settle(got.summary, unlanded=1, held=1)
    assert (settled.in_flight, settled.merged, settled.pending, settled.closing) == (1, 0, 1, 0)


def test_archived_evidence_wins_over_a_hand_pr_and_an_unselected_batch_is_adopted_too() -> None:
    """Adopting a finished close-out is bookkeeping, so it ignores the selection
    (gh#990, reversing #922's selection-only adoption)."""
    hand = _live(895, "h895", head_ref="chore/closeout-feat-batch-x")
    x, y = _merged("x", 1), _merged("y", 2)
    snap = _snap([x, y], {"x": "merged", "y": "merged"}, archived=frozenset({"x", "y"}),
                 adopted={"x": hand}, selected=frozenset({"x"}))  # fmt: skip
    assert [(a.kind, a.batch, a.archived) for a in drive_pass(snap).actions] == [
        ("adopt", "x", 0), ("adopt", "y", 0),
    ]  # fmt: skip


def test_a_wave_less_finished_batch_is_adopted_but_only_the_selection_is_closed_out() -> None:
    """gh#990: once any batch has a wave, the default selection drops every wave-less
    one, and 49 merged batches stayed "close-out not recorded" forever. Recording a
    close-out that already finished dispatches nothing, so it runs on every landed
    batch; starting a close-out session (a real action) still follows the selection."""
    waved = _batch("w", 1)
    done, owed = _merged("done", 2, wave=None), _merged("owed", 3, wave=None)
    by_hand, open_hand = _merged("by-hand", 4, wave=None), _merged("open-hand", 5, wave=None)
    merged_pr = _live(895, "", state="MERGED", head_ref="chore/closeout-feat-batch-by-hand")
    open_pr = _live(896, "h896", head_ref="chore/closeout-feat-batch-open-hand")
    landed = {"done": "merged", "owed": "merged", "by-hand": "merged", "open-hand": "merged"}
    snap = _snap([waved, done, owed, by_hand, open_hand], {"w": "proposed", **landed},
                 released=frozenset({"owed"}), archived=frozenset({"done"}),
                 adopted={"by-hand": merged_pr, "open-hand": open_pr},
                 selected=frozenset({"w"}))  # fmt: skip
    got = drive_pass(snap)
    assert [(a.kind, a.batch, a.archived) for a in got.actions] == [
        ("adopt", "done", 0), ("adopt", "by-hand", 895), ("dispatch", "w", None),
    ]  # fmt: skip
    assert got.summary.closing == 0


def test_a_batch_whose_closeout_evidence_was_unreadable_is_neither_closed_out_nor_adopted() -> None:
    """gh#991: a clone the plan could not read is no evidence that the batch is not
    archived, so no close-out is planned for it; it stays closing."""
    b = _merged("x", 1)
    snap = _snap([b], {"x": "merged"}, released=frozenset({"x"}), unverified=frozenset({"x"}))
    got = drive_pass(snap)
    assert got.actions == ()
    assert got.summary.closing == 1 and not got.summary.idle


# ------------------------------------------------------------- wave groups


def test_wave_group_names_the_workspace_a_wave_runs_in() -> None:
    assert wave_group("drive", 2) == "drive-wave-2"
    assert wave_group("bugfix", None) == "bugfix-no-wave"


@pytest.mark.parametrize("prefix", ["", "   "])
def test_wave_group_refuses_a_blank_prefix(prefix: str) -> None:
    with pytest.raises(ValueError):
        wave_group(prefix, 1)


# ------------------------------------------------------- finished sessions (R7, R10)

_CLOSEOUT = {"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h"}


def _finished(bid: str = "x", n: int = 1) -> Batch:
    return _merged(bid, n, events=[{**_CLOSEOUT, "archived": 7}])


def _sessions(bid: str = "x") -> frozenset[str]:
    return frozenset({batch_item_id(REPO, bid), closeout_item_id(REPO, bid)})


def test_is_finished_when_the_closeout_event_records_its_archive() -> None:
    assert is_finished(_finished(), "merged", ())


def test_is_finished_on_an_attributed_merged_archive_pr_with_no_archived() -> None:
    b = _merged("x", 1, events=[_CLOSEOUT])
    pr = _live(5, "h", state="MERGED", head_ref="chore/closeout-feat-batch-x", trusted=True)
    assert is_finished(b, "merged", (pr,))


@pytest.mark.parametrize("why", ["no event", "not landed", "open archive", "unattributed"])
def test_is_finished_is_false_otherwise(why: str) -> None:
    b = _merged("x", 1, events=[_CLOSEOUT])
    stage = "merged"
    prs: tuple[LivePr, ...] = ()
    if why == "no event":
        b = _merged("x", 1)
    elif why == "not landed":
        stage = "pr-open"
    elif why == "open archive":
        prs = (_live(5, "h", head_ref="chore/closeout-feat-batch-x", trusted=True),)
    else:
        prs = (_live(5, "h", state="MERGED", head_ref="chore/closeout-feat-batch-x"),)
    assert not is_finished(b, stage, prs)  # type: ignore[arg-type]


def _closing_snap(**kw: Any) -> Snapshot:
    fin = _finished()
    prop = _batch("p", 2)
    return _snap([fin, prop], {"x": "merged", "p": "proposed"}, **kw)


def test_a_finished_batchs_live_sessions_are_closed_after_the_dispatches() -> None:
    got = drive_pass(_closing_snap(close_sessions=True, sessions=_sessions()))
    assert _kinds(got.actions) == [("dispatch", "p"), ("close", "x")]


def test_closing_adds_nothing_to_the_summary() -> None:
    plain = drive_pass(_closing_snap())
    closing = drive_pass(_closing_snap(close_sessions=True, sessions=_sessions()))
    assert closing.summary == plain.summary


def test_no_close_without_close_sessions_or_a_live_session() -> None:
    assert not any(
        a.kind == "close" for a in drive_pass(_closing_snap(sessions=_sessions())).actions
    )
    got = drive_pass(_closing_snap(close_sessions=True))
    assert not any(a.kind == "close" for a in got.actions)


def test_an_unselected_finished_batch_is_not_closed() -> None:
    snap = _closing_snap(close_sessions=True, sessions=_sessions(), selected=frozenset({"p"}))
    assert not any(a.kind == "close" for a in drive_pass(snap).actions)


def test_an_unfinished_batch_is_not_closed() -> None:
    b = _merged("x", 1, events=[_CLOSEOUT])
    snap = _snap([b], {"x": "merged"}, close_sessions=True, sessions=_sessions())
    assert not any(a.kind == "close" for a in drive_pass(snap).actions)


# ------------------------------------------------------- the merge train (§A, §C)


def _ids(*names: str) -> tuple[list[Batch], dict[str, str]]:
    return [_dispatched(n, i + 1) for i, n in enumerate(names)], {n: "pr-open" for n in names}


def _train_snap(names: tuple[str, ...], live: dict[str, Any] | None = None, **kw: Any) -> Snapshot:
    batches, stages = _ids(*names)
    snap = _snap(batches, stages, **kw)
    if live:
        snap = Snapshot(**{**snap.__dict__, "live": {**snap.live, **{
            k: _live(snap.live[k].number, v.pop("head", snap.live[k].head), **v)
            for k, v in live.items()}}})  # fmt: skip
    return snap


def test_ready_green_prs_form_one_train_in_order() -> None:
    got = drive_pass(_train_snap(("c", "a", "b")))
    assert _kinds(got.actions) == [("merge", "a"), ("merge", "b"), ("merge", "c")]
    assert {a.train for a in got.actions} == {REPO}
    assert got.trains == (
        Train(repo=REPO, head="a", candidates=("a", "b", "c"), queued=(), stepped=(),
              numbers={"a": 1001, "b": 1002, "c": 1000}),
    )  # fmt: skip


def test_a_pending_head_waits_and_the_rest_are_queued() -> None:
    got = drive_pass(_train_snap(("a", "b", "c"), {"a": {"checks": "pending"}}))
    assert "merge" not in [a.kind for a in got.actions]
    (train,) = got.trains
    assert (train.head, train.candidates, train.queued) == ("a", (), ("b", "c"))
    assert got.summary.queued == 2


def test_a_moved_head_waits_the_train() -> None:
    got = drive_pass(_train_snap(("a", "b", "c"), {"a": {"head": "elsewhere"}}))
    assert got.actions == ()
    (train,) = got.trains
    assert (train.head, train.queued) == ("a", ("b", "c"))


def test_a_failing_head_is_stepped_over_and_the_next_leads() -> None:
    live = {"a": {"checks": "failing", "failing": ("lint",)}}
    got = drive_pass(_train_snap(("a", "b", "c"), live))
    assert _kinds(got.actions) == [("warn", "a"), ("merge", "b"), ("merge", "c")]
    (train,) = got.trains
    assert (train.head, train.stepped, train.candidates) == ("b", ("a",), ("b", "c"))


def test_green_pending_green_merges_one_and_queues_the_rest() -> None:
    got = drive_pass(_train_snap(("a", "b", "c"), {"b": {"checks": "pending"}}))
    assert _kinds(got.actions) == [("merge", "a")]
    (train,) = got.trains
    assert (train.head, train.candidates, train.queued) == ("a", ("a",), ("b", "c"))
    assert got.summary.queued == 2


def test_a_failing_member_behind_the_stop_is_warned_and_stepped_over() -> None:
    live = {"a": {"checks": "pending"}, "b": {"checks": "failing", "failing": ("lint",)}}
    got = drive_pass(_train_snap(("a", "b", "c"), live))
    assert _kinds(got.actions) == [("warn", "b")]
    (train,) = got.trains
    assert (train.head, train.queued, train.stepped) == ("a", ("c",), ("b",))
    assert got.summary.queued == 1


def test_each_repo_has_its_own_train() -> None:
    other = "derio-net/other"
    got = drive_pass(
        _train_snap(
            ("a", "b", "c"),
            repos={"a": other, "b": REPO, "c": REPO},
        )
    )
    assert [(t.repo, t.head, t.candidates) for t in got.trains] == [
        (other, "a", ("a",)),
        (REPO, "b", ("b", "c")),
    ]


def test_the_train_order_survives_a_member_leaving() -> None:
    """merge_order would rearrange b and c once a leaves (shared files); the train does not."""
    batches, stages = _ids("a", "b", "c")
    entries = tuple(
        QueueEntry(batch=b, pr=_pr(b.id, 1000 + i, files=["x.py"])) for i, b in enumerate(batches)
    )
    snap = _snap(batches, stages)
    first = drive_pass(Snapshot(**{**snap.__dict__, "queue": entries}))
    assert [a.batch for a in first.actions] == ["a", "b", "c"]
    rest = Snapshot(**{**snap.__dict__, "queue": entries[1:]})
    assert drive_pass(rest).trains[0].head == "b"


def test_a_green_member_ahead_is_the_head_with_no_stored_state() -> None:
    """R5: a stepped-over PR that is green again takes back its place."""
    got = drive_pass(_train_snap(("a", "b"), {"b": {"checks": "pending"}}))
    assert _kinds(got.actions) == [("merge", "a")] and got.trains[0].head == "a"


def test_a_waiting_head_is_not_counted_as_queued() -> None:
    got = drive_pass(_train_snap(("a", "b"), {"a": {"checks": "pending"}}))
    assert got.summary.queued == 1


# ------------------------------------------------------------- lines (C)


def _train(**kw: Any) -> Train:
    base: dict[str, Any] = {
        "repo": "derio-net/super-fr",
        "head": "a",
        "candidates": ("a", "b", "c"),
        "queued": ("d",),
        "stepped": ("e",),
        "numbers": {"a": 12, "b": 13, "c": 14, "d": 15, "e": 16},
    }
    return Train(**{**base, **kw})


def test_train_line_names_head_then_queued_and_stepped() -> None:
    assert train_line(_train()) == (
        "train derio-net/super-fr: head a (PR #12) · then b (#13), c (#14) · "
        "queued d (#15) · stepped over e (#16)"
    )


def test_train_line_leaves_empty_parts_out() -> None:
    line = train_line(_train(candidates=("a",), queued=(), stepped=()))
    assert line == "train derio-net/super-fr: head a (PR #12)"


def test_train_line_without_a_head() -> None:
    line = train_line(_train(head=None, candidates=(), queued=()))
    assert line == "train derio-net/super-fr: no head · stepped over e (#16)"


def test_summary_line_adds_queued_between_closing_and_blocked() -> None:
    from fr.triage.batch_drive import Summary

    s = Summary(in_flight=1, merged=0, pending=0, closing=2, blocked=3, queued=4)
    assert summary_line(s) == ("in flight 1, merged 0, pending 0, closing 2, queued 4, blocked 3")
    assert "queued" not in summary_line(Summary(1, 0, 0, 0))


# ------------------------------- per-wave state export (pages-goal R13, §I step 3b)

_EXPORTED_AT = datetime(2026, 10, 2, 11, 0, tzinfo=UTC)


def _export(wave: str = "1", **kw: Any) -> Export:
    kw.setdefault("head", "export-head-40")  # the SHA the driver pushed or adopted
    return Export(wave=wave, repo=REPO, at=_EXPORTED_AT, **kw)


def _export_snap(
    *,
    exports: Sequence[Export] = (),
    prs: dict[tuple[str, str], LivePr] | None = None,
    export_path: dict[str, str] | None = None,
    finished: frozenset[str] = frozenset({"1"}),
    orphans: tuple[LivePr, ...] = (),
    **kw: Any,
) -> Snapshot:
    """Wave 1 finished (one batch closed out and archived), wave 2 still live."""
    batches = [_finished("a", 1), _merged("b", 2, wave=2)]
    stages = {"a": "merged", "b": "merged"}
    return _snap(
        batches,
        stages,
        export_path={REPO: "docs/triage"} if export_path is None else export_path,
        default_branch={REPO: "main"},
        exports=tuple(exports),
        export_prs=prs or {},
        finished=finished,
        export_orphans={REPO: orphans} if orphans else {},
        **kw,
    )


def _exports(got: Any) -> list[tuple[str, str, str | None, int | None]]:
    return [(a.kind, a.batch, a.wave, a.pr) for a in got.actions if a.wave is not None]


def _trusted(n: int = 40, **kw: Any) -> LivePr:
    """An export PR from this repo by an allowed author: one commit on the default
    branch, changing only the export directory, on the head of wave *wave*."""
    kw.setdefault("files", ("docs/triage/judgements.yaml",))
    kw.setdefault("base", "main")
    wave = kw.pop("wave", "1")
    return _live(n, kw.pop("head", f"export-head-{n}"), head_ref=f"chore/triage-state-wave-{wave}",
                 trusted=kw.pop("trusted", True), **kw)  # fmt: skip


def test_a_finished_wave_with_no_export_and_no_pr_is_exported() -> None:
    got = drive_pass(_export_snap())
    assert _exports(got) == [("export", REPO, "1", None)]
    assert got.summary.closing >= 1 and not got.summary.done


def test_an_open_trusted_pr_with_no_record_is_reused_by_an_export() -> None:
    """p4-r12: its content is never adopted; the export pushes the driver's own commit
    onto that PR's branch and records the PR."""
    got = drive_pass(_export_snap(orphans=(_trusted(40, checks="pending"),)))
    assert _exports(got) == [("export", REPO, "1", 40)]
    (export,) = [a for a in got.actions if a.wave is not None]
    assert export.head == ""  # nothing of the PR's is pinned
    assert "reusing open PR #40" in export.detail


def test_an_open_untrusted_pr_with_no_record_warns_and_blocks() -> None:
    got = drive_pass(_export_snap(orphans=(_trusted(40, trusted=False),)))
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert "not trusted" in got.actions[-1].detail
    assert got.summary.blocked == 1


def test_a_merged_export_needs_nothing() -> None:
    got = drive_pass(_export_snap(exports=[_export(pr=40, merged=True)]))
    assert _exports(got) == []


def test_an_export_that_changed_nothing_needs_nothing() -> None:
    got = drive_pass(_export_snap(exports=[_export(pr=None)]))
    assert _exports(got) == []


def test_a_recorded_open_green_ready_trusted_pr_is_merged_at_its_head() -> None:
    got = drive_pass(_export_snap(exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40)}))
    assert _exports(got) == [("export-merge", REPO, "1", 40)]
    (merge,) = [a for a in got.actions if a.kind == "export-merge"]
    assert merge.head == "export-head-40"
    assert not got.summary.done


def test_a_recorded_pr_with_pending_checks_waits_and_counts_closing() -> None:
    snap = _export_snap(exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40, checks="pending")})
    base = drive_pass(_export_snap(exports=[_export(pr=40, merged=True)])).summary
    got = drive_pass(snap)
    assert _exports(got) == []
    assert got.summary.closing == base.closing + 1
    assert not got.summary.done and got.summary.blocked == 0


@pytest.mark.parametrize(
    ("live", "why"),
    [
        ({"checks": "failing", "failing": ("lint",)}, "failing"),
        ({"trusted": False}, "not trusted"),
        ({"draft": True}, "draft"),
    ],
    ids=["failing", "untrusted", "draft"],
)
def test_a_recorded_pr_that_cannot_merge_warns_every_pass_and_blocks(
    live: dict[str, Any], why: str
) -> None:
    snap = _export_snap(
        exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40, **live)}, warned=frozenset({""})
    )
    got = drive_pass(snap)
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert why in [a for a in got.actions if a.wave][0].detail
    assert got.summary.blocked == 1 and not got.summary.done


def test_an_unfinished_wave_is_never_exported() -> None:
    got = drive_pass(_export_snap(finished=frozenset()))
    assert _exports(got) == []


def test_without_export_config_no_export_action_exists() -> None:
    got = drive_pass(_export_snap(export_path={}))
    assert _exports(got) == []
    assert all(not a.kind.startswith("export") for a in got.actions)


def test_a_multi_repo_scope_that_opts_in_gets_one_warn_naming_repo() -> None:
    got = drive_pass(_export_snap(export_path={}, export_refused=frozenset({REPO})))
    warns = [a for a in got.actions if a.kind == "warn"]
    assert len(warns) == 1
    assert warns[0].batch == REPO and "--repo" in warns[0].detail
    assert not any(a.kind.startswith("export") for a in got.actions)


def _three_waves(**kw: Any) -> Snapshot:
    """Waves 1, 2 and 10 finished; 11 still live."""
    done = [{**_CLOSEOUT, "archived": 8}]
    batches = [
        _finished("a", 1),
        _merged("b", 2, wave=2, events=done),
        _merged("c", 3, wave=10, events=done),
        _merged("d", 4, wave=11),
    ]
    stages = {b.id: "merged" for b in batches}
    kw.setdefault("finished", frozenset({"1", "2", "10"}))
    kw.setdefault("default_branch", {REPO: "main"})
    return _snap(batches, stages, export_path={REPO: "docs/triage"}, **kw)


def test_one_export_covers_every_unexported_finished_wave_named_for_the_highest() -> None:
    got = drive_pass(_three_waves())
    (export,) = [a for a in got.actions if a.wave is not None]
    assert (export.kind, export.wave, export.covers) == ("export", "10", ("1", "2", "10"))
    assert "chore/triage-state-wave-10" in export.detail
    base = drive_pass(_three_waves(finished=frozenset())).summary
    assert got.summary.closing == base.closing + 1  # one owed export per PR, not per wave


def _covering(
    pr: int | None, *, merged: bool = False, waves: tuple[str, ...] = ("1", "2", "10")
) -> list[Export]:
    return [_export(w, pr=pr, merged=merged) for w in waves]


def test_an_open_covering_pr_is_merged_once_for_all_its_waves() -> None:
    got = drive_pass(_three_waves(exports=_covering(40), export_prs={(REPO, "10"): _trusted(40)}))
    exports = [a for a in got.actions if a.wave is not None]
    assert [(a.kind, a.wave, a.pr) for a in exports] == [("export-merge", "10", 40)]


def test_a_wave_finishing_while_an_export_pr_is_open_waits_for_its_merge() -> None:
    finished = frozenset({"1", "2", "10", "11"})
    snap = _three_waves(
        finished=finished,
        exports=_covering(40),
        export_prs={(REPO, "10"): _trusted(40, checks="pending")},
    )
    got = drive_pass(snap)
    assert [a for a in got.actions if a.wave is not None] == []  # no second PR
    base = drive_pass(_three_waves(finished=frozenset())).summary
    assert got.summary.closing == base.closing + 1  # the one PR, still owed

    after = drive_pass(_three_waves(finished=finished, exports=_covering(40, merged=True)))
    (export,) = [a for a in after.actions if a.wave is not None]
    assert (export.kind, export.wave, export.covers) == ("export", "11", ("11",))


def test_waves_recorded_with_no_pr_are_covered_and_never_exported_again() -> None:
    got = drive_pass(_three_waves(exports=_covering(None)))
    assert [a for a in got.actions if a.wave is not None] == []


def test_a_reused_pr_covers_every_owed_wave_on_its_own_branch() -> None:
    got = drive_pass(_three_waves(export_orphans={REPO: (_trusted(40, wave="2"),)}))
    (export,) = [a for a in got.actions if a.wave is not None]
    assert (export.kind, export.wave, export.covers, export.pr) == (
        "export",
        "2",
        ("1", "2", "10"),
        40,
    )


def test_export_target_names_the_newest_unmerged_pr_and_its_waves() -> None:
    from fr.triage.batch_drive import export_target

    snap = _three_waves(
        exports=[*_covering(39, merged=True, waves=("1",)), *_covering(40, waves=("2", "10"))]
    )
    target = export_target(REPO, snap.batches, snap.repos, snap.finished, snap.exports)
    assert target is not None
    assert (target.wave, target.covers, target.recorded and target.recorded.pr) == (
        "10",
        ("2", "10"),
        40,
    )


def test_an_export_action_line_names_the_wave_and_the_repo() -> None:
    action = Action("export", REPO, "to docs/triage", wave="3")
    assert action_line(action) == f"export wave 3 {REPO}: to docs/triage"
    assert action_line(action, "opened PR #9") == f"export wave 3 {REPO}: opened PR #9"


def test_the_export_branch_is_never_attributed_as_an_archive() -> None:
    from fr.triage.batch_drive import ARCHIVE_PREFIXES, export_branch

    assert export_branch("3") == "chore/triage-state-wave-3"
    assert not export_branch("3").startswith(ARCHIVE_PREFIXES)


# ------------------------------------------------ pinned merges (p4-sec-unpinned-merge)


def test_the_merge_is_pinned_to_the_recorded_head() -> None:
    got = drive_pass(
        _export_snap(
            exports=[_export(pr=40, head="pushed")], prs={(REPO, "1"): _trusted(40, head="pushed")}
        )
    )
    (merge,) = [a for a in got.actions if a.kind == "export-merge"]
    assert merge.head == "pushed"


def test_a_foreign_commit_on_the_export_branch_blocks_the_merge() -> None:
    got = drive_pass(
        _export_snap(
            exports=[_export(pr=40, head="pushed")], prs={(REPO, "1"): _trusted(40, head="foreign")}
        )
    )
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert "pushed" in got.actions[-1].detail and "foreign" in got.actions[-1].detail
    assert got.summary.blocked == 1 and not got.summary.done


def test_a_recorded_export_with_no_head_is_never_merged() -> None:
    got = drive_pass(
        _export_snap(exports=[_export(pr=40, head=None)], prs={(REPO, "1"): _trusted(40)})
    )
    assert _exports(got) == [("warn", REPO, "1", 40)]


@pytest.mark.parametrize(
    "files",
    [("docs/triage/j.yaml", ".github/workflows/x.yml"), ("docs/triage-evil/j.yaml",), ()],
    ids=["outside", "sibling-prefix", "unknown"],
)
def test_a_file_outside_the_export_dir_blocks_the_merge(files: tuple[str, ...]) -> None:
    merge = drive_pass(
        _export_snap(exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40, files=files)})
    )
    assert _exports(merge) == [("warn", REPO, "1", 40)]
    assert merge.summary.blocked == 1


# ------------------------------------- out-of-band merges and closes (p4-r1, p4-r6)


def test_a_recorded_pr_merged_outside_the_driver_is_reconciled() -> None:
    """p4-r1: merged by hand, or a pass died between the merge and its record."""
    got = drive_pass(
        _three_waves(exports=_covering(40), export_prs={(REPO, "10"): _trusted(40, state="MERGED")})
    )
    exports = [a for a in got.actions if a.wave is not None]
    assert [(a.kind, a.wave, a.pr) for a in exports] == [("export-reconcile", "10", 40)]
    assert "merged outside the driver" in exports[0].detail
    assert not got.summary.done  # recorded this pass; the next one exports what is owed


def test_after_a_reconciled_merge_the_next_wave_exports() -> None:
    finished = frozenset({"1", "2", "10", "11"})
    after = drive_pass(_three_waves(finished=finished, exports=_covering(40, merged=True)))
    (export,) = [a for a in after.actions if a.wave is not None]
    assert (export.kind, export.covers) == ("export", ("11",))


def test_a_recorded_pr_closed_unmerged_is_recorded_closed_once() -> None:
    """p4-r6: never a block forever; its waves are owed again."""
    got = drive_pass(
        _three_waves(exports=_covering(40), export_prs={(REPO, "10"): _trusted(40, state="CLOSED")})
    )
    exports = [a for a in got.actions if a.wave is not None]
    assert [(a.kind, a.wave, a.pr) for a in exports] == [("export-closed", "10", 40)]
    assert "closed without a merge" in exports[0].detail
    assert got.summary.blocked == 0 and not got.summary.done


def test_waves_of_a_closed_export_are_owed_again() -> None:
    closed = [e.model_copy(update={"closed": True}) for e in _covering(40)]
    got = drive_pass(_three_waves(exports=closed))
    (export,) = [a for a in got.actions if a.wave is not None]
    assert (export.kind, export.wave, export.covers) == ("export", "10", ("1", "2", "10"))


# ------------------------------ adoption on any wave's branch, narrowly (p4-r3, r7, r8)


def test_a_crash_then_a_new_wave_reuses_the_orphan_and_opens_no_second_pr() -> None:
    """p4-r3, p4-r13: PR #40 on wave 1's branch was opened but never recorded; wave 2
    has finished since. One export reuses #40 for both waves."""
    batches = [_finished("a", 1), _merged("b", 2, wave=2, events=[{**_CLOSEOUT, "archived": 8}])]
    snap = _snap(
        batches, {"a": "merged", "b": "merged"}, export_path={REPO: "docs/triage"},
        default_branch={REPO: "main"},
        finished=frozenset({"1", "2"}), export_orphans={REPO: (_trusted(40, wave="1"),)},
    )  # fmt: skip
    got = drive_pass(snap)
    exports = [a for a in got.actions if a.wave is not None]
    assert [(a.kind, a.wave, a.covers, a.pr) for a in exports] == [("export", "1", ("1", "2"), 40)]


def test_an_untrusted_orphan_is_warned_and_no_export_runs() -> None:
    got = drive_pass(_export_snap(orphans=(_trusted(40, trusted=False),)))
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert not any(a.kind == "export" for a in got.actions)


# ------------------------------------------------ the PR's base (p4-r15), extra orphans (p4-r16)


@pytest.mark.parametrize("base", ["release/1.x", ""], ids=["retargeted", "unknown"])
def test_a_recorded_export_pr_not_based_on_the_default_branch_is_never_merged(base: str) -> None:
    """p4-r15: a retargeted base would take the driver's commit, and every default-branch
    commit that branch lacks, somewhere nobody asked."""
    got = drive_pass(
        _export_snap(exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40, base=base)})
    )
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert "base" in got.actions[-1].detail
    assert got.summary.blocked == 1
    assert not any(a.kind == "export-merge" for a in got.actions)


@pytest.mark.parametrize("base", ["release/1.x", ""], ids=["retargeted", "unknown"])
def test_an_orphan_not_based_on_the_default_branch_is_never_reused(base: str) -> None:
    got = drive_pass(_export_snap(orphans=(_trusted(40, base=base),)))
    assert _exports(got) == [("warn", REPO, "1", 40)]
    assert "base" in got.actions[-1].detail
    assert got.summary.blocked == 1
    assert not any(a.kind == "export" for a in got.actions)


def test_the_happy_path_is_based_on_the_default_branch() -> None:
    got = drive_pass(_export_snap(exports=[_export(pr=40)], prs={(REPO, "1"): _trusted(40)}))
    assert [a.kind for a in got.actions if a.wave is not None] == ["export-merge"]


def test_every_orphan_besides_the_reused_one_is_warned_stale_once() -> None:
    """p4-r16: extra unrecorded export PRs are named, not left silent."""
    orphans = (_trusted(40, wave="1"), _trusted(41, wave="3"), _trusted(42, wave="2"))
    got = drive_pass(_three_waves(export_orphans={REPO: orphans}))
    export = [a for a in got.actions if a.kind == "export"]
    assert [(a.pr, a.wave) for a in export] == [(41, "3")]
    stale = [a for a in got.actions if a.kind == "warn" and "stale" in a.detail]
    assert sorted(a.pr for a in stale if a.pr is not None) == [40, 42]
    assert all("safe to close" in a.detail and a.head for a in stale)
    assert got.summary.blocked == 0  # stale PRs block nothing

    again = drive_pass(
        _three_waves(export_orphans={REPO: orphans}, warned=frozenset(a.head for a in stale))
    )
    assert not [a for a in again.actions if a.kind == "warn" and "stale" in a.detail]


def test_default_selection_is_the_waved_batches() -> None:
    waved, unwaved = _batch("a", 1, wave=1), _batch("b", 2, wave=None)
    assert default_selection([waved, unwaved]) == frozenset({"a"})


def test_default_selection_is_every_batch_when_none_has_a_wave() -> None:
    a, b = _batch("a", 1, wave=None), _batch("b", 2, wave=None)
    assert default_selection([a, b]) == frozenset({"a", "b"})


def test_a_batch_whose_members_all_await_a_live_walk_is_held_not_dispatched() -> None:
    """p4-r2 (spec 2026-10-06-verification-strategies §F, R18): a planned batch whose
    open members all await their live walk is no work. It is `held`, saying why, and
    it does not count as pending, so it never keeps a drive alive."""
    a, b = _batch("a", 1), _batch("b", 2)

    got = drive_pass(_snap([a, b], {"a": "proposed", "b": "proposed"}, awaiting=frozenset({"b"})))

    assert _kinds(got.actions) == [("dispatch", "a"), ("held", "b")]
    held = got.actions[1]
    assert "await" in held.detail and "live walk" in held.detail
    assert got.summary.pending == 0


# ------------------------------------------- dedupe: a wave finishing (triage-dedupe R10)

_CLOSEOUT_DONE = {
    "kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake", "handle": "h",
    "archived": 5,
}  # fmt: skip
CHECK = "fr triage check --repo o/r"


def _wave(bid: str, n: int, wave: int, *, done: bool) -> Batch:
    return _merged(bid, n, wave=wave, events=[_CLOSEOUT_DONE] if done else [])


def test_unfinished_waves_are_the_wave_keys_finished_does_not_hold() -> None:
    """The dedupe step reads `snap.finished` (main's one `finished_waves` predicate);
    `unfinished_waves` is only its complement over the state file's wave keys."""
    done, open_, loose = (
        _wave("a", 1, 2, done=True),
        _wave("b", 2, 3, done=False),
        _batch("c", 3, wave=None),
    )
    stages = {"a": "merged", "b": "merged", "c": "proposed"}
    snap = _snap([done, open_, loose], stages, finished=frozenset({"2"}))

    assert unfinished_waves(snap) == {"3"}  # a batch with no wave makes no wave


def _dedupe_snap(**kw: Any) -> Snapshot:
    done = _wave("a", 1, 2, done=True)
    kw.setdefault("finished", frozenset({"2"}))
    return _snap([done], {"a": "merged"}, dedupe_command=CHECK, **kw)


def test_a_wave_going_from_unfinished_to_finished_reports_the_candidates_last() -> None:
    got = drive_pass(_dedupe_snap(unfinished_waves=frozenset({"2"}), duplicate_groups=3))

    assert got.actions[-1] == Action(
        "dedupe", "",
        "3 duplicate candidate groups after wave 2 finished; run `fr triage check --repo o/r` "
        "to judge them",
    )  # fmt: skip
    assert [a.kind for a in got.actions].count("dedupe") == 1
    assert action_line(got.actions[-1]).startswith("dedupe: 3 duplicate candidate groups")


def test_one_group_reads_singular() -> None:
    got = drive_pass(_dedupe_snap(unfinished_waves=frozenset({"2"}), duplicate_groups=1))
    assert "1 duplicate candidate group after" in got.actions[-1].detail


@pytest.mark.parametrize(
    "kw",
    [
        dict(unfinished_waves=None, duplicate_groups=3),  # the first pass
        dict(unfinished_waves=frozenset(), duplicate_groups=3),  # finished last pass too
        dict(unfinished_waves=frozenset({"2"}), duplicate_groups=0),  # nothing to report
    ],
)
def test_no_dedupe_line_unless_a_wave_just_finished_with_candidates(kw: dict[str, Any]) -> None:
    assert all(a.kind != "dedupe" for a in drive_pass(_dedupe_snap(**kw)).actions)


def test_two_waves_finishing_together_report_in_numeric_order() -> None:
    batches = [_wave("b", 2, 10, done=True), _wave("a", 1, 9, done=True)]
    snap = _snap(batches, {"a": "merged", "b": "merged"}, dedupe_command=CHECK,
                 finished=frozenset({"9", "10"}), unfinished_waves=frozenset({"9", "10"}),
                 duplicate_groups=2)  # fmt: skip
    lines = [a.detail for a in drive_pass(snap).actions if a.kind == "dedupe"]

    assert [("wave 9 " in d, "wave 10 " in d) for d in lines] == [(True, False), (False, True)]


def test_an_archive_pr_retargeted_off_the_default_branch_is_never_merged() -> None:
    """gh#1004: the archive merge reads the PR's base as the export does (p4-r15). A
    PR based anywhere but the default branch is never merged; only the operator can
    retarget it, so the batch is blocked (named every pass), not closing."""
    from dataclasses import replace

    b = _merged("x", 1, events=[_CLOSEOUT])
    pr = _live(5, "h5", head_ref="chore/closeout-feat-batch-x", trusted=True, base="release")
    snap = _snap([b], {"x": "merged"}, archives={REPO: (pr,)}, default_branch={REPO: "main"})
    got = drive_pass(snap)
    assert [(a.kind, a.batch, a.pr) for a in got.actions] == [("blocked", "x", 5)]
    assert "is based on release, not main" in got.actions[0].detail
    assert (got.summary.closing, got.summary.blocked) == (0, 1)
    assert got.summary.waiting_on_operator
    # a default the clone could not give proves nothing: no merge, no blame, it waits
    unknown = drive_pass(replace(snap, default_branch={}))
    assert unknown.actions == () and (unknown.summary.closing, unknown.summary.blocked) == (1, 0)
    on_main = drive_pass(replace(snap, archives={REPO: (replace(pr, base="main"),)}))
    assert [(a.kind, a.pr) for a in on_main.actions] == [("archive", 5)]
