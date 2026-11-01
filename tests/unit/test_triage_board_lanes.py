"""The board's Needs-you lanes and the conflicting predicate (exit-gates R17-R19, §F)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.triage.kanban import COLUMN_TITLES, COLUMNS, build_board, column_of
from fr.triage.lanes import lane_of
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


def test_an_unread_ledger_stays_closing_out_with_the_drivers_hint_and_a_need() -> None:
    f, jd = _merged(None)
    assert _col(f, jd) == "closing-out"
    card = build_board(f, jd, {}).card("a")
    assert "gate labels unread" in card.hint
    rows = [n for n in needs_you(f, jd) if n.ref == "a"]
    assert [n.kind for n in rows] == ["ledger-unread"]  # p5-r2


def test_an_ungated_landed_batch_is_closing_out() -> None:
    assert _col(*_merged([])) == "closing-out"


# --------------------------------------------------------------- needs_you agrees


def test_needs_you_emits_one_need_per_card_in_a_lane() -> None:
    for f, jd, col in (
        (*_open(_cursor("gate"), checks={"pass": 0, "fail": 0, "pending": 1}), "needs-developer"),
        (*_open(_cursor("deliver-done", "deliver")), "needs-reviewer"),
        (*_merged(["gate:tester"]), "needs-tester"),
        (*_merged(["gate:devops"]), "needs-devops"),
    ):
        rows = [n for n in needs_you(f, jd) if n.ref == "a"]
        assert len(rows) == 1, col
        assert rows[0].kind in (col, "approve-pr")
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


# ------------------------------------------------------------ review findings (phase 5)


def test_p5_r1_a_recorded_merge_stop_reaches_the_rendered_needs_you_now() -> None:
    from fr.triage.render import render

    f, jd = _open(_cursor("none"), labels=["approved-fr"])
    stop = MergeStop(head="sha-11", reason="conflict", at="2026-10-01T12:00:00Z")
    assert 'data-need="needs-reviewer"' not in render(f, jd)
    assert 'data-need="needs-reviewer"' in render(f, jd, stops={"a": stop})


def test_p5_r3_a_green_unapproved_delivered_pr_has_one_row() -> None:
    f, jd = _open(_cursor("deliver-done", "deliver"))
    rows = [n for n in needs_you(f, jd) if n.ref == "a"]
    assert [n.kind for n in rows] == ["approve-pr"]


def test_p5_r4_a_red_delivered_pr_hint_is_the_red_one_not_approve_it() -> None:
    f, jd = _open(_cursor("deliver-done", "deliver"), checks={"pass": 1, "fail": 2, "pending": 0})
    card = build_board(f, jd, {}).card("a")
    assert card.column == "needs-reviewer"
    assert "approve" not in card.hint
    assert [n.kind for n in needs_you(f, jd) if n.ref == "a"] == ["failing-ci"]


def test_p5_r5_hint_and_column_agree_when_a_stop_meets_a_gate() -> None:
    f, jd = _open(_cursor("gate"))
    stop = MergeStop(head="sha-11", reason="conflict", at="2026-10-01T12:00:00Z")
    card = build_board(f, jd, {}, stops={"a": stop}).card("a")
    assert card.column == "needs-developer"
    assert "blocked on" in card.hint


def test_p5_r6_the_reason_names_every_held_gate_and_what_is_owed() -> None:
    f, jd = _merged(["gate:tester", "gate:devops"])
    reason = lane_of(jd.batches[0], f).reason  # type: ignore[union-attr]
    assert "tester" in reason and "devops" in reason
    assert "fr gate pass --pr 10 --gate tester" in reason
    assert "fr gate pass --pr 10 --gate devops" in reason
    assert "walk" in reason


@pytest.mark.parametrize("kind", ["merge", "enqueue"])
def test_p5_r7_the_conflicting_hint_replaces_merge_and_enqueue(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage import kanban
    from fr.triage.batch_drive import Action

    f, jd = _open(_cursor("none"), mergeable="CONFLICTING")
    monkeypatch.setattr(
        kanban,
        "_first_actions",
        lambda plan: {"a": Action(kind, "a", "", pr=11)},  # type: ignore[arg-type]
    )
    assert build_board(f, jd, {}).card("a").hint == CONFLICT_HINT


# ------------------------------------------- fr-ops R14 (p3-r9): the devops pre-merge hold


def test_p3_r9_a_pr_held_by_gate_devops_is_awaiting_devops_on_the_board() -> None:
    from fr.triage.kanban import first_actions

    f, jd = _open(_cursor("none"), labels=["approved-fr", "gate:devops"])
    assert _col(f, jd) == "needs-devops"
    (need,) = [n for n in needs_you(f, jd) if n.ref == "a"]
    assert need.kind == "needs-devops" and "awaiting DevOps" in need.text
    assert first_actions(f, jd)["a"].kind == "held"


def test_p3_r9_a_passed_devops_gate_merges_as_before() -> None:
    from fr.triage.kanban import first_actions

    f, jd = _open(_cursor("none"), labels=["approved-fr", "gate:devops", "gate:devops-passed"])
    assert _col(f, jd) == "pr-open" and first_actions(f, jd)["a"].kind == "merge"


# ------------------------------- gate-labelled merged PRs outside batches (gate-backfill R13)


def _gated(number: int, labels: list[str] | None) -> dict[str, Any]:
    return pr(number, f"feat/x{number}", state="MERGED", merged_at="2026-10-01T09:00:00Z",
              labels=labels)  # fmt: skip


def _with_gated(f: Any, *prs: dict[str, Any], unread: list[dict[str, str]] | None = None) -> Any:
    doc = f.model_dump(by_alias=True)
    doc.update(schema=13, gated_prs=list(prs), gated_unread=unread or [])
    return type(f).model_validate(doc)


def _only_gated(*prs: dict[str, Any], unread: list[dict[str, str]] | None = None) -> Any:
    return _with_gated(facts([]), *prs, unread=unread), judgements({})


def _gated_pr_of(number: int, labels: list[str] | None) -> Any:
    return _with_gated(facts([]), _gated(number, labels)).gated_prs[0]


def test_gated_pr_lane_is_tester_first_then_devops_then_none() -> None:
    from fr.triage.lanes import gated_pr_lane

    both = gated_pr_lane(_gated_pr_of(1, ["gate:tester", "gate:devops"]))
    assert both is not None and both.lane == "needs-tester"
    assert "gate:tester" in both.reason and "gate:devops" in both.reason
    dev = gated_pr_lane(_gated_pr_of(2, ["gate:devops"]))
    assert dev is not None and dev.lane == "needs-devops"
    assert gated_pr_lane(_gated_pr_of(3, ["gate:tester", "gate:tester-passed"])) is None
    assert gated_pr_lane(_gated_pr_of(4, [])) is None
    assert gated_pr_lane(_gated_pr_of(5, None)) is None


def test_a_gate_labelled_pr_outside_every_batch_is_one_need_with_the_pass_command() -> None:
    f, jd = _only_gated(_gated(30, ["gate:devops"]))
    (need,) = needs_you(f, jd)
    assert (need.kind, need.ref) == ("needs-devops", "PR #30")
    assert need.href == "https://github.com/example-org/widgets/pull/30"
    assert "merged, held by gate:devops" in need.text
    assert 'fr gate pass --pr 30 --gate devops --notes "' in need.text
    assert "--no-run-evidence" in need.text


def test_the_board_lists_the_gated_pr_in_its_lane_column() -> None:
    f, jd = _only_gated(_gated(30, ["gate:tester"]), _gated(31, ["gate:devops"]))
    board = build_board(f, jd, {})
    assert [g.number for g in board.column("needs-tester").gated] == [30]
    assert [g.number for g in board.column("needs-devops").gated] == [31]
    assert "gate:tester" in board.column("needs-tester").gated[0].reason


def test_a_pr_whose_batch_is_in_a_lane_is_listed_only_through_its_batch() -> None:
    f, jd = _merged(["gate:tester"])
    f = _with_gated(f, _gated(10, ["gate:tester"]))
    rows = [n for n in needs_you(f, jd) if n.kind in LANES]
    assert [(n.kind, n.ref) for n in rows] == [("needs-tester", "a")]
    board = build_board(f, jd, {})
    assert board.column("needs-tester").gated == ()
    assert [c.batch.id for c in board.column("needs-tester").cards] == ["a"]


def test_a_closed_out_batchs_pr_is_listed_through_gated_prs() -> None:
    f, jd = _merged(["gate:tester"], [CLOSEOUT])
    assert not [n for n in needs_you(f, jd) if n.ref == "a" and n.kind in LANES]
    f = _with_gated(f, _gated(10, ["gate:tester"]))
    (need,) = [n for n in needs_you(f, jd) if n.kind in LANES]
    assert (need.kind, need.ref) == ("needs-tester", "PR #10")
    assert [g.number for g in build_board(f, jd, {}).column("needs-tester").gated] == [10]


def test_a_batch_with_an_unread_ledger_does_not_list_its_pr_through_gated_prs() -> None:
    f, jd = _merged(None)
    f = _with_gated(f, _gated(10, ["gate:tester"]))
    kinds = [n.kind for n in needs_you(f, jd)]
    assert kinds.count("ledger-unread") == 1 and "needs-tester" not in kinds
    assert build_board(f, jd, {}).column("needs-tester").gated == ()


def test_an_unread_gate_listing_is_a_need() -> None:
    from fr.triage.views import NEED_LABELS

    f, jd = _only_gated(unread=[{"repo": "example-org/widgets", "why": "HTTP 502"}])
    (need,) = needs_you(f, jd)
    assert need.kind == "gated-unread"
    assert need.ref == "example-org/widgets"
    assert need.text == "gate-labelled PRs of example-org/widgets not read: HTTP 502"
    assert NEED_LABELS["gated-unread"] == "Gate labels unread"


def test_the_rendered_board_shows_a_gated_pr_card() -> None:
    from datetime import UTC, datetime

    from fr.triage.kanban_render import render_board

    f, jd = _only_gated(_gated(30, ["gate:tester"]))
    page = render_board(
        build_board(f, jd, {}),
        scope_args=["--repo", "example-org/widgets"],
        rendered_at=datetime(2026, 10, 5, tzinfo=UTC),
        refresh=30,
        notes=[],
    )
    assert "PR #30" in page and "merged, held by gate:tester" in page
