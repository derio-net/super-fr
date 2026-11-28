"""`fr.triage.readiness` (spec 2026-11-24-batch-merge-readiness R1-R6, R12).

`batch_readiness` is a function of a `QueueSnapshot` alone. Every case below builds one by
hand, one fixture per R5 verdict in R5's order (first match wins), and reads the verdict,
its facts (R6) and `admits`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fr.triage.approval import Approved, First, Held, Unlabelled, Void
from fr.triage.batch_drive import LivePr
from fr.triage.model import Batch, CursorPosition, QueueRecord
from fr.triage.readiness import (
    NO_CURSOR_ACTION,
    Readiness,
    batch_readiness,
    in_queue_order,
)
from fr.triage.wave_queue import (
    BuildConflict,
    Hold,
    QueueConfig,
    QueueSnapshot,
    _ready,
)

REPO = "derio-net/super-fr"
ME, OTHER = "s-11111111", "s-22222222"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
HEAD = "h" * 40
URL = f"https://github.com/{REPO}/pull/101"
BRANCH = "feat/batch-b1"
DONE = CursorPosition(run="r1", step="deliver", kind="deliver-done")
RUNNING = CursorPosition(run="r1", step="deliver", kind="none")


def _batch(*events: dict[str, Any]) -> Batch:
    return Batch.model_validate({
        "id": "b1", "title": "b1", "ids": ["super-fr#1"], "wave": 1,
        "events": [{"kind": "dispatch", "at": "2026-11-24T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": BRANCH}, *events],
    })  # fmt: skip


def _live(**kw: Any) -> LivePr:
    base: dict[str, Any] = {"number": 101, "state": "OPEN", "draft": True, "head": HEAD,
                            "checks": "green", "head_ref": BRANCH, "url": URL,
                            "mergeable": "MERGEABLE", "base": "main"}  # fmt: skip
    return LivePr(**{**base, **kw})


def _qs(batch: Batch, *, pr: LivePr | None = None, approved: Any = "yes",
        cursor: Any = (HEAD, DONE, "read"), **kw: Any) -> QueueSnapshot:  # fmt: skip
    """B1's snapshot: by default open, approved, green, delivered, mergeable."""
    pr = pr or _live()
    verdict = Approved(HEAD) if approved == "yes" else approved
    return QueueSnapshot(
        repo=REPO, scope=ME, config=kw.pop("config", QueueConfig()), now=NOW,
        batches=(batch,), stages={batch.id: "pr-open"}, live={batch.id: pr},
        approvals={} if verdict is None else {batch.id: verdict},
        cursors={} if cursor is None else {batch.id: cursor}, default="main",
        scope_args=("--repo", REPO), **kw,
    )  # fmt: skip


def _record(*events: dict[str, Any]) -> QueueRecord:
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": 1, "scope": ME, "base": "m" * 40, "events": list(events)}
    )


HALT = {"kind": "queue_halt", "at": "2026-11-24T10:00:00Z", "state": "held",
        "detail": "the remote refused the push", "land": "push"}  # fmt: skip
VOIDED = {"kind": "approval", "at": "2026-11-24T10:00:00Z", "pr": 101, "head": "a" * 40,
          "voided_at": "v" * 40}  # fmt: skip
CONFLICT = {"kind": "conflict", "at": "2026-11-24T10:00:00Z", "head": HEAD,
            "paths": ["a.py", "b.py"], "delivered": "session"}  # fmt: skip
OPENED = {"kind": "queue_open", "at": "2026-11-24T09:30:00Z"}

B = _batch()
CASES: list[tuple[str, QueueSnapshot, str, str, bool]] = [
    # (case, snapshot, kind, verdict line, admits)
    ("other scope's hold",
     _qs(B, hold=Hold(state="open", scope=OTHER, wave=1, parent=""), hold_read=True),
     "queue-held", "Not ready: queue held: held by scope s-22222222 (hold open)", True),
    ("halted queue", _qs(B, records=(_record(OPENED, HALT),)),
     "queue-held", "Not ready: queue held: held: the remote refused the push", True),
    ("approved, deliver running", _qs(B, cursor=(HEAD, RUNNING, "read")),
     "approved-not-delivered", "Approved, not delivered", False),
    ("unapproved, at another step",
     _qs(B, approved=None, cursor=(HEAD, CursorPosition(run="r1", step="review", kind="none"),
                                   "read")),
     "not-delivered", "Not ready: not delivered: run r1 is at review", False),
    ("unapproved, no cursor", _qs(B, approved=None, cursor=(HEAD, None, "read")),
     "not-delivered", f"Not ready: not delivered: no run cursor names {BRANCH}", False),
    ("unapproved, unread", _qs(B, approved=None, cursor=(HEAD, None, "unread")),
     "not-delivered", f"Not ready: not delivered: the run cursor at {HEAD[:12]} could not be read",
     False),
    ("unapproved, never asked", _qs(B, approved=None, cursor=None),
     "not-delivered", "Not ready: not delivered: the run cursor was not read", False),
    ("unapproved, no clone", _qs(B, approved=None, cursor=(HEAD, None, "no-clone")),
     "not-delivered", f"Not ready: not delivered: no clone of {REPO} to read the run cursor from",
     False),
    ("unapproved, another head", _qs(B, approved=None, cursor=("o" * 40, DONE, "read")),
     "not-delivered", f"Not ready: not delivered: the run cursor was read at {'o' * 12}, the PR "
     f"is at {HEAD[:12]}", False),
    ("CI red", _qs(B, pr=_live(checks="failing", failing=("lint", "test (1)"))),
     "ci-red", "Not ready: CI red: lint, test (1)", False),
    ("CI running", _qs(B, pr=_live(checks="pending")),
     "ci-running", "Not ready: CI running", False),
    ("pre-merge gate", _qs(B, pr=_live(labels=("gate:devops",))),
     "gate-held", "Not ready: held by a pre-merge gate", False),
    ("based on another branch", _qs(B, pr=_live(base="develop")),
     "other-base", "Not ready: based on develop, not main", False),
    ("voided before settlement", _qs(B, approved=Void("a" * 40)),
     "approval-voided", f"Approval voided by a push at {HEAD[:12]}: re-label once Ready for "
     "approval", False),
    ("voided after settlement", _qs(_batch(VOIDED), approved=Unlabelled()),
     "approval-voided", f"Approval voided by a push at {'v' * 12}: re-label once Ready for "
     "approval", False),
    ("conflicting, unapproved", _qs(_batch(CONFLICT), approved=None,
                                    pr=_live(mergeable="CONFLICTING")),
     "conflicting", "Not ready: conflicting: a.py, b.py", False),
    ("conflicting, approved", _qs(_batch(CONFLICT), pr=_live(mergeable="CONFLICTING")),
     "merges-next", "Approved, merges next", True),
    ("ready for approval", _qs(B, approved=None), "ready-for-approval", "Ready for approval",
     False),
    ("held approval reads unapproved", _qs(B, approved=Held("a" * 40, "git failed")),
     "ready-for-approval", "Ready for approval", False),
    ("approved, delivered, green", _qs(B), "merges-next", "Approved, merges next", True),
]  # fmt: skip
IDS = [c[0] for c in CASES]


@pytest.mark.parametrize(("case", "qs", "kind", "line", "admits"), CASES, ids=IDS)
def test_each_verdict_in_r5_order(
    case: str, qs: QueueSnapshot, kind: str, line: str, admits: bool
) -> None:
    got = batch_readiness(qs.batches[0], qs)
    assert (got.kind, got.verdict, got.admits) == (kind, line, admits)


@pytest.mark.parametrize(("case", "qs", "admits"), [(c[0], c[1], c[4]) for c in CASES], ids=IDS)
def test_the_queue_admits_exactly_the_hand_written_cases(
    case: str, qs: QueueSnapshot, admits: bool
) -> None:
    """R4 (l-tests-r6): the queue's own `_ready` admits each fixture exactly as the case
    table says by hand, never by comparing it with the function it calls."""
    assert _ready(qs.batches[0], qs) is admits


# R5's order (l-tests-r1): two conditions hold at once, for each adjacent pair, and the
# earlier one wins. (case, snapshot, the kind that must win)
FAILING = {"checks": "failing", "failing": ("lint",)}
PAIRS: list[tuple[str, QueueSnapshot, str]] = [
    ("queue held over not delivered",
     _qs(B, records=(_record(OPENED, HALT),), cursor=(HEAD, RUNNING, "read")), "queue-held"),
    ("not delivered over CI red",
     _qs(B, cursor=(HEAD, RUNNING, "read"), pr=_live(**FAILING)), "approved-not-delivered"),
    ("not delivered (unapproved) over CI running",
     _qs(B, approved=None, cursor=(HEAD, RUNNING, "read"), pr=_live(checks="pending")),
     "not-delivered"),
    ("CI red over a pre-merge gate",
     _qs(B, pr=_live(labels=("gate:devops",), **FAILING)), "ci-red"),
    ("CI running over a pre-merge gate",
     _qs(B, pr=_live(labels=("gate:devops",), checks="pending")), "ci-running"),
    ("gate over another base",
     _qs(B, pr=_live(labels=("gate:devops",), base="develop")), "gate-held"),
    ("another base over a voided approval",
     _qs(B, approved=Void("a" * 40), pr=_live(base="develop")), "other-base"),
    ("voided approval over conflicting",
     _qs(_batch(CONFLICT), approved=Void("a" * 40), pr=_live(mergeable="CONFLICTING")),
     "approval-voided"),
    ("conflicting over ready for approval",
     _qs(_batch(CONFLICT), approved=None, pr=_live(mergeable="CONFLICTING")), "conflicting"),
    ("an approved conflict is the queue's: merges next",
     _qs(_batch(CONFLICT), pr=_live(mergeable="CONFLICTING")), "merges-next"),
]  # fmt: skip


@pytest.mark.parametrize(("case", "qs", "kind"), PAIRS, ids=[p[0] for p in PAIRS])
def test_r5_the_earlier_of_two_holding_conditions_wins(
    case: str, qs: QueueSnapshot, kind: str
) -> None:
    assert batch_readiness(qs.batches[0], qs).kind == kind


def test_an_unread_cursor_carries_its_cause_and_is_the_operators() -> None:
    """l-errors-r2 / l-errors-r3: a read that failed names why, and a known cause is the
    operator's to fix (the driver re-reads it each pass, and it failed with that cause)."""
    why = "fetch of feat/batch-b1 failed: network down"
    got = _facts(_qs(B, approved=None, cursor=(HEAD, None, "unread"), cursor_details={"b1": why}))
    assert got.verdict == (
        f"Not ready: not delivered: the run cursor at {HEAD[:12]} could not be read: {why}"
    )
    assert got.delivered.cause == why
    assert got.facts.whose_move == "the operator"
    assert got.facts.next_action == f"fix what stops the run cursor being read: {why}"


def test_an_unread_cursor_with_no_cause_is_the_drivers_to_read_again() -> None:
    got = _facts(_qs(B, approved=None, cursor=(HEAD, None, "unread")))
    assert got.facts.whose_move == "the driver"


def test_no_clone_is_the_operators_and_names_the_clone() -> None:
    got = _facts(_qs(B, approved=None, cursor=(HEAD, None, "no-clone")))
    assert got.facts.whose_move == "the operator"
    assert got.facts.next_action == f"clone {REPO} on the driver host"


@pytest.mark.parametrize(
    "qs",
    [
        _qs(B, pr=_live(**FAILING), sessions={"b1": "working"}),
        _qs(_batch(CONFLICT), approved=None, pr=_live(mergeable="CONFLICTING"),
            sessions={"b1": "working"}),
    ],
    ids=["ci-red", "conflicting"],
)  # fmt: skip
def test_whose_move_is_the_sessions_for_red_ci_and_a_conflict(qs: QueueSnapshot) -> None:
    """l-tests-r4: a red head and an unapproved conflict are the session's to fix."""
    got = _facts(qs)
    assert got.kind in ("ci-red", "conflicting")
    assert got.facts.whose_move == "the session, working"


def test_merge_state_never_changes_admits() -> None:
    for state in ({"mergeable": "CONFLICTING"}, {"merge_state": "BEHIND"}, {"mergeable": ""}):
        assert batch_readiness(B, _qs(B, pr=_live(**state))).admits


def test_admission_keeps_the_queues_own_conditions() -> None:
    assert not batch_readiness(B, dataclasses.replace(_qs(B), stages={})).admits
    assert not batch_readiness(B, _qs(B, eligible=frozenset())).admits
    assert batch_readiness(B, _qs(B, approved=First(HEAD))).admits
    released = _qs(B, pr=_live(labels=("gate:devops",)), released=frozenset({"b1"}))
    assert batch_readiness(B, released).admits


def test_a_batch_with_no_open_pr_is_never_admitted() -> None:
    got = batch_readiness(B, _qs(B, pr=_live(state="MERGED")))
    assert (got.kind, got.admits) == ("not-open", False)


# ------------------------------------------------------------------ R6 facts


def _facts(qs: QueueSnapshot) -> Readiness:
    return batch_readiness(qs.batches[0], qs)


def test_the_facts_of_a_ready_pr() -> None:
    f = _facts(_qs(B)).facts
    assert f.delivered == "yes"
    assert f.ci == f"green at {HEAD[:12]}"
    assert f.merge == "clean"
    assert f.approval == f"recorded at {HEAD[:12]}"
    assert f.whose_move == "the driver"
    assert f.link == URL


def test_the_facts_name_red_checks_and_link_the_checks_tab() -> None:
    f = _facts(_qs(B, pr=_live(checks="failing", failing=("lint",)))).facts
    assert f.ci == f"red: lint at {HEAD[:12]}"
    assert f.link == f"{URL}/checks"


def test_the_merge_fact_reads_behind_conflicting_or_unknown() -> None:
    assert _facts(_qs(B, pr=_live(merge_state="BEHIND", mergeable=""))).facts.merge == "behind"
    assert _facts(_qs(_batch(CONFLICT), pr=_live(mergeable="CONFLICTING"))).facts.merge == (
        "conflicting: a.py, b.py"
    )
    executor = {"b1": BuildConflict(HEAD, ("c.py",))}
    assert _facts(_qs(B, pr=_live(merge_state="DIRTY"), conflicts=executor)).facts.merge == (
        "conflicting: c.py"
    )
    assert _facts(_qs(B, pr=_live(mergeable=""))).facts.merge == "unknown"


def test_the_approval_fact() -> None:
    assert _facts(_qs(B, approved=None)).facts.approval == "none"
    assert _facts(_qs(B, approved=Void("a" * 40))).facts.approval == (
        f"voided by a push at {HEAD[:12]}"
    )
    assert _facts(_qs(B, approved=Held("a" * 40, "git failed"))).facts.approval.startswith(
        "held unreadable"
    )


def test_whose_move_is_the_sessions_while_its_run_works() -> None:
    running = (HEAD, RUNNING, "read")
    got = _facts(_qs(B, cursor=running, sessions={"b1": "working"}))
    assert got.facts.whose_move == "the session, working"
    assert got.facts.command == "fr triage batch focus b1 --repo derio-net/super-fr"
    assert got.facts.link == URL
    idle = _qs(B, cursor=running, sessions={"b1": "idle"},
               head_changed={"b1": NOW - timedelta(minutes=42)})  # fmt: skip
    assert _facts(idle).facts.whose_move == "the session, idle for 42 minutes"


def test_whose_move_is_the_operators_for_approval() -> None:
    got = _facts(_qs(B, approved=None))
    assert got.facts.whose_move == "the operator"
    assert got.facts.link == URL


def test_r12_a_pr_with_no_cursor_says_how_to_merge_it() -> None:
    got = _facts(_qs(B, cursor=(HEAD, None, "read")))
    assert got.kind == "approved-not-delivered" and not got.admits
    assert got.facts.next_action == NO_CURSOR_ACTION
    assert got.facts.whose_move == "the operator"


# ------------------------------------------------------------- queue order


def test_an_approved_verdict_reads_its_place_in_the_queue() -> None:
    ready = _facts(_qs(B))
    order: Sequence[str] = ("b0", "b1")
    assert in_queue_order(ready, "b1", order).verdict == "Approved, queued behind b0"
    assert in_queue_order(ready, "b1", ("b1", "b2")).verdict == "Approved, merges next"
    held = _facts(_qs(B, approved=None))
    assert in_queue_order(held, "b1", order) is held


def test_the_module_names_its_spec() -> None:
    import fr.triage.readiness as readiness

    assert "2026-11-24-batch-merge-readiness" in (readiness.__doc__ or "")


def test_an_admitted_batch_outside_the_plans_order_is_not_merges_next() -> None:
    """p1-r3: a batch the queue admits but this pass did not place reads as not queued,
    never "merges next"."""
    ready = _facts(_qs(B))
    got = in_queue_order(ready, "b1", ("b0",))
    assert got.kind == "not-queued"
    assert got.verdict == "Approved, not in the queue this pass"
    assert got.admits


def test_an_ejected_batch_outside_the_order_reads_its_eject_reason() -> None:
    """p1-r3: ejected at its live head, it waits for the head to move, and says so."""
    eject = {"kind": "queue_eject", "at": "2026-11-24T10:30:00Z", "entry": {"batch": "b1"},
             "reason": "conflict", "detail": "a.py", "head": HEAD}  # fmt: skip
    qs = _qs(B, records=(_record(OPENED, eject),))
    got = in_queue_order(_facts(qs), "b1", (), qs)
    assert got.kind == "not-queued"
    assert got.verdict == (
        f"Approved, ejected at {HEAD[:12]} (conflict: a.py): re-enters once its head moves"
    )
    moved = dataclasses.replace(qs, live={"b1": _live(head="n" * 40)},
                                approvals={"b1": Approved("n" * 40)},
                                cursors={"b1": ("n" * 40, DONE, "read")})  # fmt: skip
    got = in_queue_order(_facts(moved), "b1", (), moved)
    assert got.verdict == "Approved, not in the queue this pass"


def test_a_held_approval_never_reads_an_older_void() -> None:
    """p1-r4: a re-labelled PR whose patch-id is unreadable reads "held unreadable", not the
    void an earlier push recorded."""
    got = _facts(_qs(_batch(VOIDED), approved=Held("a" * 40, "git failed")))
    assert got.kind == "ready-for-approval"
    assert got.facts.approval == "held unreadable: git failed"


# ------------------------------------- the approval lifecycle (queue-followups R1, R2)


def test_a_waiting_approval_reads_as_waiting_for_a_conflict_free_head() -> None:
    from fr.triage.approval import WAITS_WHY, Waiting

    got = _facts(_qs(_batch(CONFLICT), pr=_live(mergeable="CONFLICTING"),
                     approved=Waiting(HEAD, WAITS_WHY)))  # fmt: skip
    assert got.facts.approval == "approved, waits for a conflict-free head"
    assert not got.approved and got.kind != "approval-voided"


def test_an_ended_approval_is_not_a_push_void() -> None:
    approved = {"kind": "approval", "at": "2026-11-24T10:00:00Z", "pr": 101, "head": HEAD}
    ended = {**approved, "at": "2026-11-24T11:00:00Z", "voided_at": HEAD}
    got = _facts(_qs(_batch(approved, ended), approved=Unlabelled()))
    assert got.facts.approval == "ended: label removed"
    assert got.kind != "approval-voided" and "voided by a push" not in got.verdict
