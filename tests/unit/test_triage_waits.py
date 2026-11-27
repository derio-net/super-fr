"""Who each Batches card waits for (spec 2026-11-27-board-session-state §A, R1, R2).

Facts and judgements come from `triage_board_fixtures`; nothing here reads a clock, a
forge or a runner.
"""

from __future__ import annotations

from typing import Any

from fr.triage.kanban import build_board
from fr.triage.model import Facts, Judgements

from tests.unit.triage_board_fixtures import batch, dispatch, facts, issue, j, judgements


def _world(
    batches: list[dict[str, Any]], issues: list[dict[str, Any]], **kw: Any
) -> tuple[Facts, Judgements]:
    f = facts(issues, **kw)
    keys = {f"widgets#{i['number']}" for i in issues} | {k for b in batches for k in b["ids"]}
    return f, judgements({k: j(1) for k in sorted(keys)}, batches)


def test_the_harness_renders_a_dispatched_card_in_running() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert build_board(f, jd, {}).card("a").column == "running"


# ------------------------------------------------------- the table, row by row (§A)

from fr.triage.lanes import LaneVerdict  # noqa: E402
from fr.triage.waits import Wait, wait_of  # noqa: E402


def _w(**kw: Any) -> Wait | None:
    """`wait_of` on a card that is quiet everywhere, so a test names only what it moves."""
    args: dict[str, Any] = {
        "column": "running", "stage": "dispatched", "lane": None, "needs_you": False,
        "front_status": "working", "front_background": False, "checks": None,
        "has_action": False, "queued": False, "ready": False, "awaiting": False,
        "selected": False, "deps": (),
    }  # fmt: skip
    return wait_of(**{**args, **kw})


def test_row_1_a_done_card_waits_for_no_one() -> None:
    assert _w(column="done", needs_you=True, front_status="working") is None


def test_row_2_a_needs_you_card_waits_for_you_with_the_lanes_role() -> None:
    lane = LaneVerdict("needs-reviewer", "approve it")
    assert _w(column="needs-reviewer", lane=lane, needs_you=True) == Wait("you", "reviewer")
    for name, role in (
        ("needs-developer", "developer"), ("needs-tester", "tester"), ("needs-devops", "devops")
    ):
        assert _w(column=name, lane=LaneVerdict(name, "x"), needs_you=True) == Wait("you", role)


def test_row_2_a_needs_you_card_with_no_lane_has_no_role() -> None:
    assert _w(needs_you=True) == Wait("you", None)


def test_row_2_beats_every_later_row() -> None:
    w = _w(
        needs_you=True, stage="obsolete", awaiting=True, deps=("unsatisfiable",),
        front_status="working", checks={"pending": 2},
    )
    assert w == Wait("you", None)


def test_blocked_always_reaches_row_2() -> None:
    assert _w(front_status="blocked", needs_you=True) == Wait("you", None)
    assert _w(front_status="blocked", needs_you=False) == Wait("you", None)


def test_row_3_an_obsolete_card_waits_for_the_operators_cancel() -> None:
    assert _w(column="obsolete", stage="obsolete", front_status=None) == Wait("you")


def test_row_4_a_green_pr_held_for_approval_waits_for_the_reviewer() -> None:
    w = _w(column="pr-open", stage="pr-open", awaiting=True, front_status=None)
    assert w == Wait("you", "reviewer")


def test_row_5_a_dead_dependency_waits_for_you() -> None:
    for dead in ("unsatisfiable", "unknown"):
        w = _w(column="waiting", stage="proposed", deps=(dead,), front_status=None)
        assert w == Wait("you")


def test_row_6_an_unsatisfied_dependency_is_a_dependency_wait() -> None:
    w = _w(column="waiting", stage="proposed", deps=("pending",), front_status=None)
    assert w == Wait("dependency")


def test_row_6_a_dependency_satisfied_by_an_obsolete_batch_is_no_wait() -> None:
    w = _w(column="waiting", stage="proposed", deps=("satisfied",), front_status=None)
    assert w == Wait("queue")  # falls to row 11: `waiting` is the driver's to move


def test_row_7_an_unselected_proposal_waits_for_you() -> None:
    w = _w(column="proposed", stage="proposed", front_status=None, selected=False)
    assert w == Wait("you")


def test_row_8_a_working_front_session_is_the_agent() -> None:
    assert _w(front_status="working") == Wait("agent")


def test_row_8_beats_background_and_ci() -> None:
    assert _w(front_status="working", front_background=True, checks={"pending": 1}) == Wait(
        "agent"
    )


def test_row_9_an_idle_session_with_background_work_is_background() -> None:
    for status in ("idle", "done"):
        assert _w(front_status=status, front_background=True) == Wait("background")


def test_row_9_beats_a_pending_pr() -> None:
    w = _w(column="pr-open", front_status="idle", front_background=True, checks={"pending": 1})
    assert w == Wait("background")


def test_row_10_pending_checks_wait_for_ci() -> None:
    assert _w(column="pr-open", front_status="idle", checks={"pending": 2}) == Wait("ci")


def test_row_10_checks_none_is_not_pending() -> None:
    assert _w(column="pr-open", front_status="idle", checks=None) == Wait("agent")
    assert _w(column="pr-open", front_status="idle", checks={"pending": 0}) == Wait("agent")


def test_row_11_a_driver_action_queued_or_ready_card_waits_for_the_queue() -> None:
    for key in ("has_action", "queued", "ready"):
        assert _w(front_status="idle", **{key: True}) == Wait("queue")


def test_row_11_a_selected_proposal_and_a_waiting_card_wait_for_the_queue() -> None:
    sel = _w(column="proposed", stage="proposed", front_status=None, selected=True)
    assert sel == Wait("queue")
    waiting = _w(column="waiting", stage="proposed", front_status=None)
    assert waiting == Wait("queue")


def test_row_12_an_idle_or_done_session_below_the_threshold_is_the_agent() -> None:
    for status in ("idle", "done"):
        assert _w(front_status=status) == Wait("agent")


def test_row_13_a_lost_session_waits_for_the_queue() -> None:
    for status in ("absent", "unknown", None):
        assert _w(front_status=status) == Wait("queue")


# ------------------------------------------------ the close-out front (rows 8, 9, 12)


def _closeout_card(status: str | None, background: bool) -> Wait | None:
    """What the board hands `wait_of` for a card whose close-out session is its front."""
    return _w(column="closing-out", stage="merged", front_status=status, front_background=background)


def test_the_closeout_front_decides_rows_8_9_and_12() -> None:
    assert _closeout_card("working", False) == Wait("agent")
    assert _closeout_card("idle", True) == Wait("background")
    assert _closeout_card("idle", False) == Wait("agent")
