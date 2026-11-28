"""The drive pass passes a walked gate on a merged PR outside a batch (spec
2026-11-28-tester-gate-auto-pass R1-R3, R8): `fr.triage.pr_gates` plans for it, and
`drive_pass` reads `Snapshot.loose_ledgers` beside the batches' ledgers."""

from __future__ import annotations

from typing import Any

from fr.triage import pr_gates
from fr.triage.batch_drive import Snapshot, drive_pass
from fr.triage.batch_drive_types import GatedRow, GateLedger, LooseLedger

from tests.unit.test_triage_batch_drive import NOW, _dispatched, _snap
from tests.unit.triage_board_fixtures import REPO, dispatch, facts, issue, j, judgements, pr
from tests.unit.triage_board_fixtures import batch as mk_batch

CLOSEOUT = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "fake", "handle": "c"}
ISSUE = f"{REPO}#7"
OTHER = f"{REPO}#8"


def _ledger(*labels: str, rows: tuple[GatedRow, ...] | None, **kw: Any) -> GateLedger:
    return GateLedger(pr=50, labels=frozenset(labels), rows=rows, **kw)


def _walked(*issues: str, gate: str = "tester", rid: str = "row-a") -> GatedRow:
    return GatedRow(rid, gate, True, tuple(issues))


# ------------------------------------------------------------------ gate_actions


def test_walked_rows_of_a_loose_pr_plan_one_gate_pass_naming_its_repo() -> None:
    ledger = _ledger("gate:tester", rows=(_walked(),))
    (action,) = pr_gates.gate_actions("", REPO, ledger, frozenset(), set())
    assert (action.kind, action.batch, action.repo, action.pr, action.gate) == (
        "gate-pass", "", REPO, 50, "tester",
    )  # fmt: skip


def test_a_row_not_walked_plans_no_pass() -> None:
    rows = (_walked(), GatedRow("row-b", "tester", False))
    ledger = _ledger("gate:tester", rows=rows)
    assert pr_gates.gate_actions("", REPO, ledger, frozenset(), set()) == []


def test_r2_the_batch_guards_hold_for_a_loose_pr() -> None:
    def plan(ledger: GateLedger) -> list[Any]:
        return pr_gates.gate_actions("", REPO, ledger, frozenset(), set())

    run_gate = _ledger("gate:tester", rows=(_walked(),), run_gate="tester")
    assert plan(run_gate) == []  # a run gate no row inherits
    inherited = _ledger(
        "gate:tester", rows=(_walked(),), run_gate="tester", run_gate_inherited=True
    )
    assert [a.kind for a in plan(inherited)] == ["gate-pass"]
    ops = _ledger("gate:devops", rows=(_walked(gate="devops"),), ops_promoted=True)
    assert plan(ops) == []  # an ops-promoted devops gate
    assert plan(_ledger("gate:devops", rows=())) == []  # a held gate with no rows


def test_unread_rows_plan_nothing() -> None:
    ledger = _ledger("gate:tester", rows=None)
    assert pr_gates.gate_actions("", REPO, ledger, frozenset({ISSUE}), set()) == []


def test_an_open_issue_a_row_cites_is_labelled_once_across_calls() -> None:
    ledger = _ledger("gate:tester", rows=(_walked(ISSUE),))
    labelled: set[str] = set()
    first = pr_gates.gate_actions("", REPO, ledger, frozenset({ISSUE}), labelled)
    again = pr_gates.gate_actions("", REPO, ledger, frozenset({ISSUE}), labelled)
    assert [a.kind for a in first] == ["awaiting-live", "gate-pass"]
    assert first[0].key == ISSUE and first[0].repo == REPO
    assert [a.kind for a in again] == ["gate-pass"]


# --------------------------------------------------------------------- loose_prs


def _facts_with(*gated: dict[str, Any], batch_prs: list[dict[str, Any]] | None = None) -> Any:
    f = facts([])
    doc = f.model_dump(by_alias=True)
    doc.update(schema=13, gated_prs=list(gated), gated_unread=[], batch_prs=batch_prs or [])
    return type(f).model_validate(doc)


def _merged_pr(number: int, head_ref: str, labels: list[str] | None = None) -> dict[str, Any]:
    return pr(number, head_ref, state="MERGED", merged_at="2026-10-01T09:00:00Z",
              labels=labels if labels is not None else ["gate:tester"])  # fmt: skip


def test_a_gated_pr_no_batch_delivered_is_loose() -> None:
    f = _facts_with(_merged_pr(10, "feat/solo"))
    (loose,) = pr_gates.loose_prs(f, [])
    assert (loose.repo, loose.number, loose.head_ref) == (REPO, 10, "feat/solo")
    assert loose.ledger.pr == 10 and loose.ledger.rows is None
    assert loose.ledger.labels == frozenset({"gate:tester"})


def _with_batch(closeout: bool) -> tuple[Any, Any]:
    merged = _merged_pr(10, "feat/batch-a")
    f = _facts_with(merged)
    events = [dispatch("a"), *([CLOSEOUT] if closeout else [])]
    jd = judgements({"widgets#1": j(1)}, [mk_batch("a", [1], events=events)])
    doc = f.model_dump(by_alias=True)
    doc["issues"] = [issue(1, state="closed", prs=[merged])]
    return type(f).model_validate(doc), jd


def test_a_batch_pr_without_a_closeout_is_not_loose_but_a_closed_out_one_is() -> None:
    f, jd = _with_batch(closeout=False)
    assert pr_gates.loose_prs(f, jd.batches) == []
    f, jd = _with_batch(closeout=True)
    assert [p.number for p in pr_gates.loose_prs(f, jd.batches)] == [10]


# -------------------------------------------------------------------- drive_pass


def _loose(number: int, rows: tuple[GatedRow, ...] | None, *labels: str) -> LooseLedger:
    ledger = GateLedger(pr=number, labels=frozenset(labels or ("gate:tester",)), rows=rows)
    return LooseLedger(REPO, number, f"feat/x{number}", ledger)


def _pass(**kw: Any) -> Any:
    return drive_pass(_snap([], {}, **kw))


def test_a_loose_ledger_with_walked_rows_plans_a_gate_pass() -> None:
    plan = _pass(loose_ledgers=(_loose(10, (_walked(),)),))
    (action,) = [a for a in plan.actions if a.kind == "gate-pass"]
    assert (action.batch, action.repo, action.pr) == ("", REPO, 10)


def test_r3_a_loose_pr_and_a_gated_batch_citing_one_issue_label_it_once() -> None:
    b1 = _dispatched("b1", 7)
    batch_ledger = GateLedger(pr=101, labels=frozenset({"gate:tester"}), rows=(_walked(ISSUE),))
    plan = drive_pass(
        _snap(
            [b1],
            {"b1": "merged"},
            merged_at={"b1": NOW},
            ledgers={"b1": batch_ledger},
            awaiting_unlabelled=frozenset({ISSUE}),
            loose_ledgers=(_loose(10, (_walked(ISSUE),)),),
        )  # fmt: skip
    )
    assert [a.key for a in plan.actions if a.kind == "awaiting-live"] == [ISSUE]


def test_a_loose_ledger_with_unread_rows_plans_nothing() -> None:
    plan = _pass(loose_ledgers=(_loose(10, None),), awaiting_unlabelled=frozenset({ISSUE}))
    assert [a for a in plan.actions if a.kind in ("awaiting-live", "gate-pass")] == []


def test_a_closed_out_batchs_pr_given_as_a_loose_ledger_is_passed() -> None:
    plan = _pass(loose_ledgers=(_loose(10, (_walked(),)),))
    assert [a.kind for a in plan.actions if a.kind == "gate-pass"] == ["gate-pass"]


def test_snapshot_has_loose_ledgers_defaulting_empty() -> None:
    assert Snapshot.__dataclass_fields__["loose_ledgers"].default == ()
