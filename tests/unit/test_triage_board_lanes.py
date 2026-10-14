"""The board's Needs-you lanes and the conflicting predicate (exit-gates R17-R19, §F)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.triage.kanban import COLUMN_TITLES, COLUMNS, build_board, column_of
from fr.triage.merge_stops import MergeStop
from fr.triage.mergeability import CONFLICT_HINT, conflicting
from fr.triage.views import needs_you

from tests.unit.triage_board_fixtures import batch as mk_batch
from tests.unit.triage_board_fixtures import dispatch, facts, issue, j, judgements, pr

LANES = ("needs-developer", "needs-reviewer", "needs-tester", "needs-devops")
CLOSEOUT = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "fake", "handle": "c"}


def _cursor(kind: str, step: str = "implement-phase", unit: str | None = None) -> dict[str, Any]:
    return {"run": "r1", "step": step, "kind": kind, "unit": unit}


def _open(cursor: dict[str, Any] | None, **kw: Any) -> Any:
    p = pr(11, "feat/batch-a", cursor=cursor, **kw)
    f = facts([issue(1, prs=[p])], schema=12)
    return f, judgements({"widgets#1": j(1)}, [mk_batch("a", [1], events=[dispatch("a")])])


def _merged(labels: list[str] | None, events: list[Any] | None = None) -> Any:
    p = pr(10, "feat/batch-a", state="MERGED", merged_at="2026-10-01T09:00:00Z", labels=labels)
    f = facts([issue(1, state="closed", prs=[p])], schema=12)
    ev = [dispatch("a"), *(events or [])]
    return f, judgements({"widgets#1": j(1)}, [mk_batch("a", [1], events=ev)])


def _col(f: Any, jd: Any, **kw: Any) -> str:
    return column_of(jd.batches[0], f, jd.batches, **kw)


# ----------------------------------------------------------------- R19 predicate


@pytest.mark.parametrize(
    ("mergeable", "state", "expected"),
    [
        ("CONFLICTING", None, True),
        ("MERGEABLE", "DIRTY", True),
        (None, "DIRTY", True),
        ("MERGEABLE", "BLOCKED", False),
        ("MERGEABLE", "CLEAN", False),
        ("UNKNOWN", "UNKNOWN", False),
        (None, None, False),
    ],
)
def test_conflicting_is_true_for_conflicting_or_dirty_only(
    mergeable: str | None, state: str | None, expected: bool
) -> None:
    assert conflicting(mergeable, state) is expected


def test_a_conflicting_pr_never_reads_merge_ready() -> None:
    f, jd = _open(_cursor("none"), labels=["approved-fr"], mergeable="CONFLICTING")
    card = build_board(f, jd, {}).card("a")
    assert card.hint == CONFLICT_HINT
    assert CONFLICT_HINT == "conflicting — the driver updates it or hands it back"


def test_a_blocked_pr_still_reads_merge_ready() -> None:
    f, jd = _open(_cursor("none"), labels=["approved-fr"], mergeable="MERGEABLE",
                  merge_state="BLOCKED")  # fmt: skip
    assert build_board(f, jd, {}).card("a").hint == "merge ready"


def test_the_merge_train_still_plans_the_merge_for_a_conflicting_pr() -> None:
    from fr.triage.kanban import first_actions

    f, jd = _open(_cursor("none"), labels=["approved-fr"], mergeable="CONFLICTING")
    assert first_actions(f, jd)["a"].kind == "merge"


# ----------------------------------------------------------------- R17 columns


def test_the_columns_are_r17s_in_order() -> None:
    assert COLUMNS == (
        "proposed", "waiting", "running", "needs-developer", "pr-open", "needs-reviewer",
        "needs-tester", "needs-devops", "closing-out", "partial", "done",
    )  # fmt: skip
    assert COLUMN_TITLES["needs-developer"] == "Needs you · Developer"
    assert COLUMN_TITLES["needs-devops"] == "Needs you · DevOps"


def test_a_cursor_blocked_on_a_step_gate_is_needs_developer() -> None:
    assert _col(*_open(_cursor("gate"))) == "needs-developer"


def test_a_manual_unit_next_is_needs_developer() -> None:
    assert _col(*_open(_cursor("manual", unit="P1.T1"))) == "needs-developer"


def test_deliver_done_and_not_approved_is_needs_reviewer() -> None:
    assert _col(*_open(_cursor("deliver-done", "deliver"))) == "needs-reviewer"


def test_deliver_done_and_approved_stays_pr_open() -> None:
    f, jd = _open(_cursor("deliver-done", "deliver"), labels=["approved-fr"])
    assert _col(f, jd) == "pr-open"


def test_a_cursor_mid_run_is_pr_open_and_an_unknown_cursor_too() -> None:
    assert _col(*_open(_cursor("none"))) == "pr-open"
    assert _col(*_open(None)) == "pr-open"


def test_a_stopped_merge_is_needs_reviewer() -> None:
    f, jd = _open(_cursor("none"), labels=["approved-fr"])
    stop = MergeStop(head="sha-11", reason="conflict", at="2026-10-01T12:00:00Z")
    assert _col(f, jd, stop=stop) == "needs-reviewer"


def test_session_status_alone_never_moves_a_card_into_a_lane_but_still_flags_it() -> None:
    f, jd = _open(_cursor("none"))
    board = build_board(f, jd, {"example-org/widgets/run/batch-a": "blocked"})
    card = board.card("a")
    assert card.column == "pr-open"
    assert card.needs_you


def test_a_landed_tester_gated_batch_is_needs_tester() -> None:
    assert _col(*_merged(["gate:tester"])) == "needs-tester"


def test_a_landed_devops_gated_batch_is_needs_devops() -> None:
    assert _col(*_merged(["gate:devops"])) == "needs-devops"


def test_a_passed_gate_is_not_a_lane() -> None:
    assert _col(*_merged(["gate:tester", "gate:tester-passed"])) == "closing-out"


def test_an_unread_ledger_is_in_a_lane_with_its_reason() -> None:
    f, jd = _merged(None)
    assert _col(f, jd) == "needs-developer"
    card = build_board(f, jd, {}).card("a")
    assert "gate labels" in card.hint and card.needs_you


def test_an_ungated_landed_batch_is_closing_out() -> None:
    assert _col(*_merged([])) == "closing-out"


# --------------------------------------------------------------- needs_you agrees


def test_needs_you_emits_one_need_per_card_in_a_lane() -> None:
    for f, jd, col in (
        (*_open(_cursor("gate")), "needs-developer"),
        (*_open(_cursor("deliver-done", "deliver")), "needs-reviewer"),
        (*_merged(["gate:tester"]), "needs-tester"),
        (*_merged(["gate:devops"]), "needs-devops"),
    ):
        rows = [n for n in needs_you(f, jd) if n.kind == col]
        assert len(rows) == 1, col
        assert build_board(f, jd, {}).card("a").column == col


def test_a_card_in_no_lane_has_no_lane_need() -> None:
    f, jd = _open(_cursor("none"))
    assert not [n for n in needs_you(f, jd) if n.kind in LANES]


def test_the_rendered_board_shows_the_lane_columns() -> None:
    from datetime import UTC, datetime

    from fr.triage.kanban_render import render_board

    f, jd = _open(_cursor("gate"))
    page = render_board(
        build_board(f, jd, {}),
        scope_args=["--repo", "example-org/widgets"],
        rendered_at=datetime(2026, 10, 5, tzinfo=UTC),
        refresh=30,
        notes=[],
    )
    for key in LANES:
        assert f'data-column="{key}"' in page
    for title in ("Needs you · Developer", "Needs you · Reviewer", "Needs you · Tester",
                  "Needs you · DevOps"):  # fmt: skip
        assert title in page
