"""The board's pure model: columns, pills, hints, cards (spec 2026-10-05 §C; R2, R3, R4, R6, R7).

Facts and judgements are built from `triage_board_fixtures`; nothing here reads a
clock, a forge or a runner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

import pytest
from fr.triage import kanban
from fr.triage.batch import batch_item_id
from fr.triage.batch_drive import Action, ActionKind, closeout_item_id
from fr.triage.kanban import (
    COLUMNS,
    Board,
    action_phrase,
    build_board,
    column_of,
    first_actions,
    pill_of,
)
from fr.triage.merge_stops import MergeStop
from fr.triage.model import Facts, Judgements

from tests.unit.triage_board_fixtures import (
    REPO,
    batch,
    busy,
    dispatch,
    facts,
    issue,
    j,
    judgements,
    pr,
)
from tests.unit.triage_fixtures import forbidden_imports

HAND = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "hand", "handle": "c"}
SESSION = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "fake", "handle": "c"}
MERGED = pr(10, "feat/batch-m", state="MERGED", merged_at="2026-10-01T09:00:00Z")


def _world(
    batches: list[dict[str, Any]], issues: list[dict[str, Any]], **kw: Any
) -> tuple[Facts, Judgements]:
    f = facts(issues, **kw)
    keys = {f"widgets#{i['number']}" for i in issues} | {k for b in batches for k in b["ids"]}
    judged = {k: j(1) for k in sorted(keys)}
    return f, judgements(judged, batches)


def _col(bid: str, f: Facts, jd: Judgements) -> str:
    return column_of(next(b for b in jd.batches if b.id == bid), f, jd.batches)


def _merged_issues() -> list[dict[str, Any]]:
    return [issue(1, state="closed", prs=[MERGED])]


# ------------------------------------------------------------------ columns (R2)


def test_the_columns_are_seven_in_r2_order() -> None:
    assert COLUMNS == (
        "proposed", "waiting", "running", "pr-open", "closing-out", "partial", "done"
    )  # fmt: skip
    assert set(get_args(kanban.Column)) == set(COLUMNS)


def test_a_batch_never_dispatched_with_no_after_is_proposed() -> None:
    f, jd = _world([batch("a", [1])], [issue(1)])
    assert _col("a", f, jd) == "proposed"


def test_a_batch_waiting_on_an_unmerged_dependency_is_waiting_not_blocked() -> None:
    f, jd = _world([batch("a", [1], wave=1), batch("b", [2], after=["a"])], [issue(1), issue(2)])
    card = build_board(f, jd, {}).card("b")
    assert (card.column, card.blocked) == ("waiting", False)


def test_a_batch_after_a_cancelled_dependency_is_waiting_and_blocked() -> None:
    cancel = {"kind": "cancel", "at": "2026-10-01T12:00:00Z"}
    f, jd = _world(
        [batch("a", [1], events=[dispatch("a"), cancel]), batch("b", [2], after=["a"])],
        [issue(1), issue(2)],
    )
    card = build_board(f, jd, {}).card("b")
    assert (card.column, card.blocked) == ("waiting", True)


def test_a_batch_after_an_unknown_dependency_is_blocked() -> None:
    # Loaded without the cross-batch check, which refuses an unknown `after` on write.
    f, jd = _world([batch("b", [2], after=["ghost"])], [issue(2)])
    card = build_board(f, jd, {}).card("b")
    assert (card.column, card.blocked) == ("waiting", True)


def test_a_dispatched_batch_without_a_pr_is_running() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert _col("a", f, jd) == "running"


def test_a_batch_with_an_open_pr_is_pr_open() -> None:
    open_pr = pr(11, "feat/batch-a")
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[open_pr])])
    assert _col("a", f, jd) == "pr-open"


def test_a_merged_batch_with_no_closeout_event_is_closing_out() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m")])], _merged_issues())
    assert _col("m", f, jd) == "closing-out"


def test_a_merged_batch_with_a_started_closeout_is_closing_out() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m"), SESSION])], _merged_issues())
    assert _col("m", f, jd) == "closing-out"


def test_a_closeout_event_with_archived_is_done() -> None:
    done = {**HAND, "archived": 42}
    f, jd = _world([batch("m", [1], events=[dispatch("m"), done])], _merged_issues())
    assert _col("m", f, jd) == "done"


def test_done_reads_the_closeout_event_never_a_merged_pr_in_the_facts() -> None:
    """gh#882: `facts.prs` holds open PRs only, so a merged close-out PR is never there;
    the driver records the merge on the close-out event, whoever merged it."""
    closeout_pr = pr(12, "chore/closeout-feat-batch-m", state="MERGED")
    f, jd = _world(
        [batch("m", [1], events=[dispatch("m"), SESSION])],
        _merged_issues(),
        prs=[closeout_pr],
    )
    assert _col("m", f, jd) == "closing-out"


@pytest.mark.parametrize("word", ["cancelled", "abandoned"])
def test_cancelled_and_abandoned_are_done_with_the_pill_word(word: str) -> None:
    events: list[dict[str, Any]] = [dispatch("a")]
    issues = [issue(1)]
    if word == "cancelled":
        events.append({"kind": "cancel", "at": "2026-10-01T12:00:00Z"})
    elif word == "abandoned":
        issues = [issue(1, prs=[pr(11, "feat/batch-a", state="CLOSED")])]
        # a closed PR is only linked through the batch_prs list
        f = facts(issues, batch_prs=[pr(11, "feat/batch-a", state="CLOSED")])
        jd = judgements({"widgets#1": j(1)}, [batch("a", [1], events=events)])
        assert (_col("a", f, jd), pill_of(jd.batches[0], f)) == ("done", "abandoned")
        return
    f, jd = _world([batch("a", [1], events=events)], issues)
    assert _col("a", f, jd) == "done"
    assert pill_of(jd.batches[0], f) == word


def _partial(*closeout: dict[str, Any]) -> tuple[Facts, Judgements]:
    """Batch `a`'s PR merged while its member stayed open: stage `partial`."""
    issues = [issue(1, prs=[pr(11, "feat/batch-a", state="MERGED")])]
    return _world([batch("a", [1], events=[dispatch("a"), *closeout])], issues)


@pytest.mark.parametrize("closeout", [(), (SESSION,)], ids=["not-recorded", "started"])
def test_a_partial_batch_owed_its_closeout_is_in_partial_not_done(closeout: tuple) -> None:
    """gh#985: the driver still owes a partial batch its close-out, so it is not Done."""
    f, jd = _partial(*closeout)
    assert _col("a", f, jd) == "partial"
    assert pill_of(jd.batches[0], f) == "partial"


def test_a_partial_batch_moves_to_done_once_its_closeout_is_archived() -> None:
    f, jd = _partial({**HAND, "archived": 42})
    assert (_col("a", f, jd), pill_of(jd.batches[0], f)) == ("done", "partial")
    assert _hint("a", f, jd) == "partial"


def test_a_partial_batch_with_a_started_closeout_reads_archive_pr_pending() -> None:
    f, jd = _partial(SESSION)
    assert _hint("a", f, jd) == "archive PR pending"


def test_a_plain_merged_or_running_batch_has_no_pill() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert pill_of(jd.batches[0], f) is None


# ------------------------------------------------------------------ hints (R6)


def test_every_action_kind_has_a_phrase() -> None:
    for kind in get_args(ActionKind):
        phrase = action_phrase(Action(kind, "b", "detail"))
        assert phrase and "\n" not in phrase


@pytest.mark.parametrize(
    ("kind", "phrase"),
    [
        ("dispatch", "dispatch next"),
        ("merge", "merge ready"),
        ("warn", "CI failing"),
        ("closeout", "close-out due"),
        ("archive", "archive PR ready to merge"),
        ("held", "held by the in-flight cap"),
        ("adopt", "close-out found; the drive records it"),
        ("foreign", "foreign PR on its branch"),
        ("close", "finished; session to close"),
    ],
)
def test_action_phrases(kind: ActionKind, phrase: str) -> None:
    assert action_phrase(Action(kind, "b", "x")) == phrase


def test_a_blocked_action_names_what_it_waits_on() -> None:
    action = Action("blocked", "b", "waits on a is cancelled")
    assert action_phrase(action) == "blocked: waits on a is cancelled"


def _hint(bid: str, f: Facts, jd: Judgements, statuses: dict[str, str] | None = None) -> str:
    return build_board(f, jd, statuses or {}).card(bid).hint


def test_a_blocked_session_overrides_every_other_hint() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    item = f"{REPO}/run/batch-a"
    assert _hint("a", f, jd, {item: "blocked"}) == "needs you: session blocked"


def test_a_blocked_closeout_session_also_needs_you() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m"), SESSION])], _merged_issues())
    assert _hint("m", f, jd, {f"{REPO}/run/closeout-m": "blocked"}) == "needs you: session blocked"


def test_the_driver_would_dispatch_a_proposed_batch() -> None:
    f, jd = _world([batch("a", [1], wave=1)], [issue(1)])
    assert _hint("a", f, jd) == "dispatch next"


def test_the_driver_would_merge_a_green_open_pr() -> None:
    f, jd = _world(
        [batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[pr(11, "feat/batch-a")])]
    )
    assert _hint("a", f, jd) == "merge ready"


def test_a_failing_pr_reads_ci_failing() -> None:
    red = pr(11, "feat/batch-a", checks={"pass": 1, "fail": 2, "pending": 0})
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[red])])
    assert _hint("a", f, jd) == "CI failing"


def test_a_merged_batch_past_the_fallback_reads_closeout_due() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m")])], _merged_issues())
    assert _hint("m", f, jd) == "close-out due"


def test_a_batch_waiting_on_a_dead_dependency_reads_blocked() -> None:
    f, jd = busy()
    assert _hint("d-blocked", f, jd).startswith("blocked: waits on z-cancelled")


def test_the_full_in_flight_cap_holds_a_proposed_batch() -> None:
    running = [batch(f"r{n}", [n], wave=1, events=[dispatch(f"r{n}")]) for n in range(1, 5)]
    f, jd = _world([*running, batch("late", [5], wave=1)], [issue(n) for n in range(1, 6)])
    assert _hint("late", f, jd) == "held by the in-flight cap"


def test_a_foreign_pr_on_a_batch_branch_is_reported() -> None:
    stranger = pr(11, "feat/batch-a", author="stranger")
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[stranger])])
    assert _hint("a", f, jd) == "foreign PR on its branch"


def test_a_proposed_batch_outside_the_drives_selection_reads_not_driven() -> None:
    f, jd = _world([batch("a", [1], wave=1), batch("b", [2], wave=None)], [issue(1), issue(2)])
    assert _hint("b", f, jd) == "not driven"


def test_a_proposed_batch_with_no_action_reads_queued() -> None:
    # All four slots are NOT full here, but the batch has no wave and nothing is waved:
    # the drive selects everything, dispatches it, so use a cap-free fallback instead.
    f, jd = _world([batch("a", [1], wave=1)], [issue(1)])
    cards = build_board(f, jd, {})
    assert cards.card("a").hint == "dispatch next"
    assert (
        kanban.fallback_hint(cards.card("a").batch, "proposed", f, jd.batches, selected=True)
        == "queued"
    )


def test_a_waiting_batch_names_the_batches_not_yet_merged() -> None:
    f, jd = _world(
        [
            batch("a", [1], wave=1, events=[dispatch("a")]),
            batch("c", [3], wave=1, events=[dispatch("c")]),
            batch("b", [2], wave=2, after=["a", "c"]),
        ],
        [issue(1), issue(2), issue(3)],
    )
    assert _hint("b", f, jd) == "waits on a, c"


def test_a_running_batch_with_no_pr_reads_session_running() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert _hint("a", f, jd) == "session running, no PR yet"


def test_a_draft_pr_reads_pr_draft() -> None:
    f, jd = busy()
    assert _hint("b-draft", f, jd) == "PR draft"


def test_a_pending_pr_reads_ci_pending() -> None:
    pending = pr(11, "feat/batch-a", checks={"pass": 1, "fail": 0, "pending": 2})
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[pending])])
    assert _hint("a", f, jd) == "CI pending"


def test_a_ready_green_pr_the_driver_will_not_merge_reads_awaiting_review() -> None:
    f, jd = _world(
        [batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[pr(11, "feat/batch-a")])]
    )
    got = kanban.fallback_hint(jd.batches[0], "pr-open", f, jd.batches, selected=True)
    assert got == "awaiting review"


def test_a_started_closeout_reads_archive_pr_pending() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m"), SESSION])], _merged_issues())
    assert _hint("m", f, jd) == "archive PR pending"


def test_a_merged_batch_that_the_drive_does_not_select_reads_closeout_not_recorded() -> None:
    f, jd = _world(
        [batch("m", [1], wave=None, events=[dispatch("m")]), batch("w", [2], wave=1)],
        [*_merged_issues(), issue(2)],
    )
    assert _hint("m", f, jd) == "close-out not recorded"


def test_a_finished_batch_reads_finished_or_its_pill() -> None:
    done = {**HAND, "archived": 42}
    f, jd = _world([batch("m", [1], events=[dispatch("m"), done])], _merged_issues())
    assert _hint("m", f, jd) == "finished"
    f, jd = busy()
    assert _hint("z-cancelled", f, jd) == "cancelled"


# ------------------------------------------------------------ merge stops (gh#987)

CONFLICT = "PR #11 conflicts with origin/main in a change merge will not resolve: a.py, b.py"


def _stopped(head: str) -> dict[str, MergeStop]:
    return {"a": MergeStop(head=head, reason=CONFLICT, at="2026-10-01T12:00:00Z")}


def test_a_merge_the_driver_stopped_on_needs_you_not_merge_ready() -> None:
    """gh#987: the stop is an execution-time fact the pure pass cannot see, so the board
    reads the driver's record of it, and the card says the opposite of "merge ready"."""
    f, jd = _world(
        [batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[pr(11, "feat/batch-a")])]
    )
    card = build_board(f, jd, {}, stops=_stopped("sha-11")).card("a")
    assert card.hint == f"needs you: merge stopped: {CONFLICT}"
    assert card.needs_you


def test_a_merge_stop_at_a_head_since_moved_no_longer_counts() -> None:
    f, jd = _world(
        [batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[pr(11, "feat/batch-a")])]
    )
    card = build_board(f, jd, {}, stops=_stopped("sha-older")).card("a")
    assert (card.hint, card.needs_you) == ("merge ready", False)


def test_a_merge_stop_on_a_pr_no_longer_open_no_longer_counts() -> None:
    merged = pr(11, "feat/batch-a", state="MERGED")
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1, prs=[merged])])
    assert not build_board(f, jd, {}, stops=_stopped("sha-11")).card("a").needs_you


def test_a_batch_waiting_on_a_stopped_merge_says_so() -> None:
    f, jd = _world(
        [
            batch("a", [1], wave=1, events=[dispatch("a")]),
            batch("b", [2], wave=2, after=["a"]),
        ],
        [issue(1, prs=[pr(11, "feat/batch-a")]), issue(2)],
    )
    assert build_board(f, jd, {}, stops=_stopped("sha-11")).card("b").hint == (
        "waits on a (merge stopped)"
    )


def test_first_actions_keeps_the_first_action_per_batch() -> None:
    f, jd = busy()
    got = first_actions(f, jd)
    assert got["e-next"].kind == "dispatch"
    assert got["c-red"].kind == "warn"
    assert got["a-merged"].kind == "closeout"
    assert "b-draft" not in got


# ------------------------------------------------------------------ cards and board


def test_the_board_has_seven_columns_with_counts_in_order() -> None:
    f, jd = busy()
    board = build_board(f, jd, {})
    assert [c.key for c in board.columns] == list(COLUMNS)
    counts = {c.key: len(c.cards) for c in board.columns}
    assert counts == {
        "proposed": 1,
        "waiting": 1,
        "running": 0,
        "pr-open": 2,
        "closing-out": 1,
        "partial": 0,
        "done": 1,
    }
    assert isinstance(board, Board)


def test_a_card_exists_for_every_batch_exactly_once() -> None:
    f, jd = busy()
    board = build_board(f, jd, {})
    ids = [card.batch.id for col in board.columns for card in col.cards]
    assert sorted(ids) == sorted(b.id for b in jd.batches)


def test_cards_sort_by_wave_with_no_wave_last_then_id() -> None:
    f, jd = _world(
        [
            batch("z", [1], wave=1),
            batch("b", [2], wave=2),
            batch("a", [3], wave=2),
            batch("n", [4], wave=None),
            batch("m", [5], wave=None),
        ],
        [issue(n) for n in range(1, 6)],
    )
    col = build_board(f, jd, {}).column("proposed")
    assert [c.batch.id for c in col.cards] == ["z", "a", "b", "m", "n"]


def test_a_card_carries_its_members_with_issue_stage_and_url() -> None:
    f, jd = busy()
    card = build_board(f, jd, {}).card("b-draft")
    assert [(m.key, m.title, m.stage) for m in card.members] == [
        ("widgets#3", "issue 3", "pr-draft"),
        ("widgets#4", "issue 4", "pr-draft"),
    ]
    assert card.members[0].url == "https://github.com/example-org/widgets/issues/3"


def test_a_member_missing_from_the_facts_is_listed_with_an_unknown_stage() -> None:
    f, jd = _world([batch("a", [1, 2])], [issue(1)])
    card = build_board(f, jd, {}).card("a")
    assert [(m.key, m.stage, m.url) for m in card.members] == [
        ("widgets#1", "backlog", "https://github.com/example-org/widgets/issues/1"),
        ("widgets#2", "unknown", None),
    ]


def test_a_card_carries_its_batch_pr() -> None:
    f, jd = busy()
    card = build_board(f, jd, {}).card("c-red")
    assert card.pr is not None
    assert (card.pr.number, card.pr.draft, card.pr.checks) == (
        12,
        False,
        {"pass": 1, "fail": 2, "pending": 0},
    )
    assert card.pr.url.endswith("/pull/12")
    assert build_board(f, jd, {}).card("e-next").pr is None


def test_the_lifecycle_carries_wave_after_branch_version_skill_and_rationale() -> None:
    cancel = {"kind": "cancel", "at": "2026-10-01T12:00:00Z"}
    d = {**dispatch("a"), "reserved_version": "5.6.0"}
    f, jd = _world(
        [
            batch("a", [1], events=[d, cancel]),
            batch("b", [2], wave=3, after=["a"], skill="debug", rationale="because"),
        ],
        [issue(1), issue(2)],
    )
    board = build_board(f, jd, {})
    a, b = board.card("a"), board.card("b")
    assert (a.branch, a.reserved_version, a.runner) == ("feat/batch-a", "5.6.0", "fake")
    assert (b.wave, b.skill, b.rationale) == (3, "debug", "because")
    assert [(d.batch_id, d.state) for d in b.after] == [("a", "unsatisfiable")]


def test_harness_and_model_come_from_the_batch_launch() -> None:
    f, jd = _world(
        [batch("a", [1], launch={"harness": "claude", "model": "opus"})],
        [issue(1)],
        config={REPO: {"defaults": {"launch": {"harness": "codex", "model": "gpt"}}}},
    )
    card = build_board(f, jd, {}).card("a")
    assert (card.harness.value, card.harness.is_default) == ("claude", False)
    assert (card.model.value, card.model.is_default) == ("opus", False)


def test_harness_and_model_fall_back_to_the_repo_default_flagged() -> None:
    f, jd = _world(
        [batch("a", [1])],
        [issue(1)],
        config={REPO: {"defaults": {"launch": {"harness": "codex", "model": "gpt"}}}},
    )
    card = build_board(f, jd, {}).card("a")
    assert (card.harness.value, card.harness.is_default) == ("codex", True)
    assert (card.model.value, card.model.is_default) == ("gpt", True)


def test_harness_and_model_are_none_with_no_launch_and_no_default() -> None:
    f, jd = _world([batch("a", [1])], [issue(1)])
    card = build_board(f, jd, {}).card("a")
    assert card.harness.value is None and card.model.value is None


def test_events_are_listed_oldest_first() -> None:
    post = {"kind": "post_merge", "at": "2026-10-01T14:00:00Z"}
    f, jd = _world([batch("m", [1], events=[dispatch("m"), SESSION, post])], _merged_issues())
    card = build_board(f, jd, {}).card("m")
    assert [e.kind for e in card.events] == ["dispatch", "closeout", "post_merge"]
    assert card.events[0].at < card.events[1].at < card.events[2].at


def test_status_is_looked_up_by_item_id_and_unknown_when_missing() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert build_board(f, jd, {f"{REPO}/run/batch-a": "working"}).card("a").status == "working"
    assert build_board(f, jd, {}).card("a").status == "unknown"


def test_a_batch_never_dispatched_has_no_status_and_no_jump() -> None:
    f, jd = _world([batch("a", [1])], [issue(1)])
    card = build_board(f, jd, {f"{REPO}/run/batch-a": "working"}).card("a")
    assert (card.status, card.show_jump) == (None, False)


@pytest.mark.parametrize(
    ("status", "shown"), [("absent", False), ("unknown", True), ("idle", True)]
)
def test_the_jump_button_shows_unless_there_is_no_session(status: str, shown: bool) -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    card = build_board(f, jd, {f"{REPO}/run/batch-a": status}).card("a")  # type: ignore[dict-item]
    assert card.show_jump is shown


def test_a_runner_closeout_has_a_status_and_a_jump_a_hand_closeout_has_neither() -> None:
    f, jd = _world([batch("m", [1], events=[dispatch("m"), SESSION])], _merged_issues())
    card = build_board(f, jd, {f"{REPO}/run/closeout-m": "idle"}).card("m")
    assert (card.closeout_status, card.show_closeout_jump) == ("idle", True)
    f, jd = _world([batch("m", [1], events=[dispatch("m"), HAND])], _merged_issues())
    card = build_board(f, jd, {}).card("m")
    assert (card.closeout_status, card.show_closeout_jump, card.hand_closeout) == (
        None,
        False,
        True,
    )


def test_the_board_pins_its_status_vocabulary() -> None:
    assert "unknown" in get_args(kanban.BoardStatus)


def test_the_board_module_imports_no_fr_dispatch() -> None:
    path = Path(kanban.__file__)
    assert forbidden_imports(path, "fr.triage", ("fr_dispatch",)) == []


# ------------------------------------------- claims: held elsewhere, card expiry (R13)

ME = "s-aaaaaaaa"
OTHER = "s-bbbbbbbb"
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _claim(signer: str, batch_id: str, expires: str, cid: int = 1) -> dict[str, Any]:
    return {
        "signer": signer,
        "batch": batch_id,
        "claimed": "2026-10-05T12:00:00Z",
        "heartbeat": "2026-10-05T12:00:00Z",
        "expires": expires,
        "comment_id": cid,
        "created_at": "2026-10-05T12:00:00Z",
    }


def test_held_elsewhere_lists_issues_another_scope_claims_with_holder_batch_and_expiry() -> None:
    f, jd = _world(
        [batch("a", [1])],
        [issue(1), issue(2, claims=[_claim(OTHER, "theirs", "2026-10-07T12:00:00Z")]), issue(3)],
    )
    board = build_board(f, jd, {}, me=ME, now=NOW)
    (held,) = board.held
    assert (held.key, held.title, held.holder, held.batch) == (
        "widgets#2", "issue 2", OTHER, "theirs"
    )  # fmt: skip
    assert held.expires == datetime(2026, 10, 7, 12, 0, tzinfo=UTC) and held.expired is False
    assert held.url and held.line.startswith("widgets#2 is claimed by triage scope")


def test_an_expired_claim_is_marked_and_still_listed() -> None:
    f, jd = _world([], [issue(2, claims=[_claim(OTHER, "theirs", "2026-10-06T08:00:00Z")])])
    (held,) = build_board(f, jd, {}, me=ME, now=NOW).held
    assert held.expired is True and "expired" in held.line


def test_own_claims_and_closed_issues_are_not_held_elsewhere() -> None:
    f, jd = _world(
        [],
        [
            issue(1, claims=[_claim(ME, "mine", "2026-10-07T12:00:00Z")]),
            issue(2, state="closed", claims=[_claim(OTHER, "t", "2026-10-07T12:00:00Z")]),
        ],
    )
    assert build_board(f, jd, {}, me=ME, now=NOW).held == ()


def test_without_a_scope_id_there_is_no_held_group_and_no_card_expiry() -> None:
    f, jd = _world(
        [batch("a", [1])], [issue(1, claims=[_claim(OTHER, "t", "2026-10-07T12:00:00Z")])]
    )
    board = build_board(f, jd, {})
    assert board.held == () and board.card("a").claim_expiry is None


def test_an_own_batch_card_carries_the_earliest_expiry_of_its_claims() -> None:
    f, jd = _world(
        [batch("a", [1, 2], wave=1)],
        [
            issue(1, claims=[_claim(ME, "a", "2026-10-07T12:00:00Z")]),
            issue(2, claims=[_claim(ME, "a", "2026-10-06T18:00:00Z")]),
        ],
    )
    expiry = build_board(f, jd, {}, me=ME, now=NOW).card("a").claim_expiry
    assert expiry is not None
    assert expiry.at == datetime(2026, 10, 6, 18, 0, tzinfo=UTC) and expiry.expired is False


def test_an_own_expired_claim_marks_the_card_expiry_expired() -> None:
    f, jd = _world([batch("a", [1])], [issue(1, claims=[_claim(ME, "a", "2026-10-06T09:00:00Z")])])
    expiry = build_board(f, jd, {}, me=ME, now=NOW).card("a").claim_expiry
    assert expiry is not None and expiry.expired is True


def test_a_batch_with_no_own_claims_has_no_card_expiry() -> None:
    f, jd = _world(
        [batch("a", [1])], [issue(1, claims=[_claim(ME, "other-batch", "2026-10-07T12:00:00Z")])]
    )
    assert build_board(f, jd, {}, me=ME, now=NOW).card("a").claim_expiry is None


# ------------------------------ idle sessions (driver-sessions §D, R8)

IDLE_NOW = datetime(2026, 10, 1, 12, 5, tzinfo=UTC)  # 125 minutes after `dispatch`
ARCHIVE = {"kind": "closeout", "at": "2026-10-01T10:00:00Z", "runner": "fake", "handle": "c"}


def _idle_card(
    batches: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    statuses: dict[str, Any],
    bid: str = "a",
    **kw: Any,
) -> Any:
    f, jd = _world(batches, issues, **kw)
    return build_board(f, jd, statuses, now=IDLE_NOW).card(bid)


def test_a_batch_card_idle_with_no_pr_needs_you_and_says_why() -> None:
    card = _idle_card(
        [batch("a", [1], events=[dispatch("a")])], [issue(1)], {batch_item_id(REPO, "a"): "idle"}
    )
    assert card.needs_you
    assert card.hint == "idle, dispatched 125 min ago, no PR as of 2026-10-02 12:00 UTC"


def test_a_closeout_card_idle_with_no_archive_pr_needs_you_and_says_why() -> None:
    card = _idle_card(
        [batch("m", [1], events=[dispatch("m"), ARCHIVE])],
        [issue(1, state="closed", prs=[pr(10, "feat/batch-m", state="MERGED")])],
        {closeout_item_id(REPO, "m"): "idle"},
        bid="m",
    )
    assert card.needs_you
    assert (
        card.hint == "idle, close-out started 125 min ago, no archive PR as of 2026-10-02 12:00 UTC"
    )


def test_a_card_with_a_pr_is_not_flagged() -> None:
    card = _idle_card(
        [batch("a", [1], events=[dispatch("a")])],
        [issue(1, prs=[pr(11, "feat/batch-a")])],
        {batch_item_id(REPO, "a"): "idle"},
    )
    assert not card.needs_you and "idle" not in card.hint


def test_a_closeout_with_an_attributed_archive_pr_is_not_flagged() -> None:
    merged = pr(10, "feat/batch-m", state="MERGED")
    closeout = {**ARCHIVE, "archived": 3}
    card = _idle_card(
        [batch("m", [1], events=[dispatch("m"), closeout])],
        [issue(1, state="closed", prs=[merged])],
        {closeout_item_id(REPO, "m"): "idle"},
        bid="m",
    )
    assert not card.needs_you


@pytest.mark.parametrize("status", ["working", "blocked", "absent", "unknown"])
def test_a_session_that_is_not_idle_adds_no_idle_line(status: str) -> None:
    card = _idle_card(
        [batch("a", [1], events=[dispatch("a")])], [issue(1)], {batch_item_id(REPO, "a"): status}
    )
    assert "idle" not in card.hint


def test_the_threshold_is_the_repos_idle_session_minutes() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    from fr.triage.model import TriageConfig

    f = f.model_copy(update={"config": {REPO: TriageConfig(idle_session_minutes=200)}})
    statuses = {batch_item_id(REPO, "a"): "idle"}
    assert not build_board(f, jd, statuses, now=IDLE_NOW).card("a").needs_you


def test_without_a_clock_the_board_judges_no_idleness() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert not build_board(f, jd, {batch_item_id(REPO, "a"): "idle"}).card("a").needs_you


def test_a_cancelled_batch_with_a_leftover_idle_session_is_not_flagged() -> None:
    cancel = {"kind": "cancel", "at": "2026-10-01T11:00:00Z", "reason": "no longer wanted"}
    card = _idle_card(
        [batch("a", [1], events=[dispatch("a"), cancel])],
        [issue(1)],
        {batch_item_id(REPO, "a"): "idle"},
    )
    assert not card.needs_you and "idle" not in card.hint


def test_a_finished_closeout_is_never_flagged() -> None:
    # The archive PR merged by hand, not yet recorded: the facts carry it merged.
    archive = pr(20, "chore/closeout-feat-batch-m", state="MERGED")
    card = _idle_card(
        [batch("m", [1], events=[dispatch("m"), ARCHIVE])],
        [issue(1, state="closed", prs=[pr(10, "feat/batch-m", state="MERGED")])],
        {closeout_item_id(REPO, "m"): "idle"},
        bid="m",
        prs=[archive],
    )
    assert not card.needs_you and "idle" not in card.hint


def test_an_idle_session_is_never_a_failing_ci_need() -> None:
    from fr.triage.batch_drive import idle_session
    from fr.triage.views import drive_snapshot, needs_you

    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    # The inputs that WOULD make the driver report: an idle, aged, PR-less dispatch.
    assert (
        idle_session(
            jd.batches[0], repo=REPO, closeout=False, status="idle", stage="dispatched",
            archives=(), now=IDLE_NOW, threshold=60,
        )
        is not None
    )  # fmt: skip
    assert drive_snapshot(f, jd).idle == ()
    assert [n for n in needs_you(f, jd) if n.kind == "failing-ci"] == []
