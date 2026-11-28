"""The drive pass passes a walked gate on a merged PR outside a batch (spec
2026-11-28-tester-gate-auto-pass R1-R3, R8): `fr.triage.pr_gates` plans for it, and
`drive_pass` reads `Snapshot.loose_ledgers` beside the batches' ledgers."""

from __future__ import annotations

from pathlib import Path
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


def test_r8_a_closed_out_batchs_gated_pr_is_passed_once_through_the_loose_route() -> None:
    from dataclasses import replace

    f, jd = _with_batch(closeout=True)
    (loose,) = pr_gates.loose_prs(f, jd.batches)
    walked = replace(loose.ledger, rows=(_walked(),))
    (batch,) = jd.batches
    plan = drive_pass(
        _snap(
            [batch],
            {batch.id: "merged"},
            merged_at={batch.id: NOW},
            ledgers={batch.id: walked},  # the batch route sees it too, and skips it
            loose_ledgers=(replace(loose, ledger=walked),),
        )
    )
    passes = [(a.batch, a.repo, a.pr) for a in plan.actions if a.kind == "gate-pass"]
    assert passes == [("", REPO, 10)]


def test_snapshot_has_loose_ledgers_defaulting_empty() -> None:
    assert Snapshot.__dataclass_fields__["loose_ledgers"].default == ()


# ------------------------------------------------- the cursor must name the PR (R5)


def _cursor_pr(
    checkout: Any, *, pr: str | None, extra: str | None = None, archived: bool = False
) -> None:
    """Record *pr* on the run cursor of `_ledger_repo`, and optionally copy that cursor to a
    second run id (a second cursor naming the same branch) or, *archived*, the same run's
    copy under `docs/superpowers/implemented/runs/`."""
    import yaml

    from tests.unit.test_triage_exit_gates_drive import _git

    clone = checkout.path
    path = clone / "docs/superpowers/runs/r1.yaml"
    doc = yaml.safe_load(path.read_text())
    if pr is None:
        doc.pop("pr", None)
    else:
        doc["pr"] = pr
    path.write_text(yaml.safe_dump(doc))
    if extra is not None:
        (clone / f"docs/superpowers/runs/{extra}.yaml").write_text(
            yaml.safe_dump({**doc, "run": extra})
        )
    if archived:
        twin = clone / "docs/superpowers/implemented/runs/r1.yaml"
        twin.parent.mkdir(parents=True, exist_ok=True)
        twin.write_text(yaml.safe_dump(doc))
    _git(clone, "add", "docs/superpowers")
    _git(clone, "commit", "--quiet", "-m", "cursor")
    _git(clone, "push", "--quiet", "origin", "HEAD:main")
    _git(clone, "fetch", "--quiet", "origin")


def _read(tmp_path: Path, number: int | None, **kw: Any) -> Any:
    from fr.triage.ledger import gated_rows_at

    from tests.unit.test_triage_exit_gates_drive import _ledger_repo

    checkout = _ledger_repo(tmp_path, walked=True)
    _cursor_pr(checkout, **kw)
    return gated_rows_at(checkout, "origin/main", "feat/batch-b1", pr=number)


def test_a_cursor_naming_this_pr_gives_its_rows(tmp_path: Path) -> None:
    read = _read(tmp_path, 9, pr=f"https://github.com/{REPO}/pull/9/")
    assert [r.id for r in read.rows] == ["r-live"]


def test_a_cursor_naming_another_pr_gives_no_rows(tmp_path: Path) -> None:
    from fr.triage.ledger import NO_RUN

    assert _read(tmp_path, 9, pr=f"https://github.com/{REPO}/pull/19") == NO_RUN


def test_a_cursor_with_no_pr_gives_its_rows(tmp_path: Path) -> None:
    assert [r.id for r in _read(tmp_path, 9, pr=None).rows] == ["r-live"]


def test_two_cursors_naming_the_branch_are_unreadable_for_a_pr(tmp_path: Path) -> None:
    import pytest
    from fr.triage.errors import TriageError

    with pytest.raises(TriageError, match="feat/batch-b1.*r1.*r2|feat/batch-b1.*r2.*r1"):
        _read(tmp_path, 9, pr=None, extra="r2")


def test_no_cursor_gives_no_rows_and_no_pr_keeps_the_first_match(tmp_path: Path) -> None:
    from fr.triage.ledger import NO_RUN, gated_rows_at

    from tests.unit.test_triage_exit_gates_drive import _ledger_repo

    checkout = _ledger_repo(tmp_path, walked=True)
    assert gated_rows_at(checkout, "origin/main", "fix/none", pr=9) == NO_RUN
    _cursor_pr(checkout, pr=f"https://github.com/{REPO}/pull/19", extra="r2")
    assert [r.id for r in gated_rows_at(checkout, "origin/main", "feat/batch-b1").rows] == [
        "r-live"
    ]  # pr=None: today's first match, however many cursors


def test_a_runs_live_and_archived_cursors_are_one_cursor_for_a_pr(tmp_path: Path) -> None:
    read = _read(tmp_path, 9, pr=f"https://github.com/{REPO}/pull/9", archived=True)
    assert [r.id for r in read.rows] == ["r-live"]
