"""The wave merge queue's pure planner (spec 2026-11-19-wave-merge-queue §A, §B, §C, §M;
R2, R3, R8, R9, R13, R14, R30, R31, R36).

`fr.triage.wave_queue.plan_queue` is a function of a `QueueSnapshot` alone: no git, no
forge, no clock. Every test builds a snapshot by hand and reads the plan it returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fr.triage.approval import Approved, First, Void
from fr.triage.batch_drive import LivePr
from fr.triage.model import Batch, QueueRecord
from fr.triage.wave_queue import (
    Hold,
    QueueAction,
    QueueConfig,
    QueuePlan,
    QueueSnapshot,
    SlotCheck,
    plan_queue,
    queue_phase,
)

REPO = "derio-net/super-fr"
ME = "s-11111111"
OTHER = "s-22222222"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
AT = "2026-11-20T10:00:00Z"
MAIN = "m0" * 20


def _batch(bid: str, n: int, *, wave: int | None = 1, events: Sequence[dict[str, Any]] = (),
           **kw: Any) -> Batch:  # fmt: skip
    doc: dict[str, Any] = {
        "id": bid, "title": bid, "ids": [f"super-fr#{n}"], "wave": wave,
        "events": [
            {"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake", "handle": "h",
             "branch": f"feat/batch-{bid}"},
            *events,
        ],
        **kw,
    }  # fmt: skip
    return Batch.model_validate(doc)


def _live(n: int, head: str = "", **kw: Any) -> LivePr:
    return LivePr(number=n, state=kw.pop("state", "OPEN"), draft=kw.pop("draft", False),
                  head=head or f"head-{n}", checks=kw.pop("checks", "green"), **kw)  # fmt: skip


def _record(*events: dict[str, Any], wave: int | None = 1, base: str = MAIN,
            scope: str = ME) -> QueueRecord:  # fmt: skip
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": wave, "scope": scope, "base": base, "events": list(events)}
    )


def _open(at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_open", "at": at}


def _built(slot: int, sha: str, bid: str, *, head: str = "", parent: str = MAIN,
           base: str = MAIN, at: str = AT) -> dict[str, Any]:  # fmt: skip
    return {"kind": "queue_built", "at": at, "slot": slot, "sha": sha, "entry": {"batch": bid},
            "head": head or f"head-{bid}", "patch_id": f"pid-{bid}", "base": base,
            "parent": parent}  # fmt: skip


def _land(main: str, *bids: str, at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_land", "at": at, "main": main,
            "entries": [{"batch": b} for b in bids]}  # fmt: skip


def _eject(bid: str, reason: str = "red", at: str = AT) -> dict[str, Any]:
    return {"kind": "queue_eject", "at": at, "entry": {"batch": bid}, "reason": reason}


def _qs(
    batches: Sequence[Batch],
    stages: dict[str, str],
    *,
    live: dict[str, LivePr] | None = None,
    numbers: dict[str, int] | None = None,
    **kw: Any,
) -> QueueSnapshot:
    """A snapshot of REPO: every `pr-open` batch is approved and green unless told."""
    numbers = numbers or {b.id: 100 + i for i, b in enumerate(batches)}
    if live is None:
        live = {
            b.id: _live(numbers[b.id], f"head-{b.id}")
            for b in batches if stages.get(b.id) == "pr-open"
        }  # fmt: skip
    kw.setdefault("approvals", {bid: First(pr.head) for bid, pr in live.items()})
    kw.setdefault("base", MAIN)
    return QueueSnapshot(
        repo=REPO,
        scope=ME,
        config=kw.pop("config", QueueConfig()),
        now=kw.pop("now", NOW),
        batches=tuple(batches),
        stages=stages,  # type: ignore[arg-type]
        live=live,
        **kw,
    )


def _kinds(plan: QueuePlan) -> list[str]:
    return [a.kind for a in plan.actions]


def _one(plan: QueuePlan, kind: str) -> QueueAction:
    (got,) = [a for a in plan.actions if a.kind == kind]
    return got


def _green(*shas: str) -> dict[str, SlotCheck]:
    return {s: SlotCheck("green") for s in shas}


# ------------------------------------------------ phases and wave choice (R2, R3, R31)


def test_an_idle_repo_opens_the_lowest_unfinished_wave_even_with_nothing_of_it_ready() -> None:
    batches = [
        _batch("w3", 1, wave=3),  # dispatched, no PR yet: not ready, not terminal
        _batch("w4", 2, wave=4),
        _batch("w2", 3, wave=2),  # landed: terminal
    ]
    stages = {"w3": "dispatched", "w4": "pr-open", "w2": "merged"}
    plan = plan_queue(_qs(batches, stages))
    assert plan.phase == "idle"
    assert _kinds(plan) == ["queue-open"]
    assert _one(plan, "queue-open").wave == 3 and plan.wave == 3
    assert plan.waiting == ("w4",)


def test_terminal_means_landed_cancelled_abandoned_or_deferred() -> None:
    deferred = [{"kind": "deferred", "at": AT, "wave": 3}]
    batches = [
        _batch("a", 1, wave=3, events=deferred),
        _batch("b", 2, wave=3),
        _batch("c", 3, wave=3),
        _batch("d", 4, wave=3),
        _batch("e", 5, wave=5),
    ]
    stages = {"a": "pr-open", "b": "cancelled", "c": "abandoned", "d": "partial", "e": "proposed"}
    plan = plan_queue(_qs(batches, stages))
    assert _one(plan, "queue-open").wave == 5


def test_a_requeued_batch_belongs_to_the_wave_it_names() -> None:
    moved = [{"kind": "deferred", "at": AT, "wave": 3},
             {"kind": "requeued", "at": "2026-11-20T10:05:00Z", "wave": 6}]  # fmt: skip
    batches = [_batch("a", 1, wave=3, events=moved), _batch("b", 2, wave=7)]
    plan = plan_queue(_qs(batches, {"a": "pr-open", "b": "proposed"}))
    assert _one(plan, "queue-open").wave == 6


def test_another_scopes_hold_is_held_naming_it_and_nothing_else() -> None:
    batches = [_batch("a", 1, wave=3)]
    for state in ("open", "drained"):
        hold = Hold(state=state, scope=OTHER, wave=2, parent=MAIN)  # type: ignore[arg-type]
        plan = plan_queue(_qs(batches, {"a": "pr-open"}, hold=hold))
        assert _kinds(plan) == ["queue-held"], state
        held = plan.actions[0]
        assert held.scope == OTHER and OTHER in held.detail and "wave 2" in held.detail


def test_another_scopes_hold_holds_an_open_queue_too() -> None:
    batches = [_batch("a", 1, wave=3)]
    hold = Hold(state="open", scope=OTHER, wave=3, parent=MAIN)
    plan = plan_queue(_qs(batches, {"a": "pr-open"}, records=(_record(_open(), wave=3),),
                          hold=hold))  # fmt: skip
    assert _kinds(plan) == ["queue-held"]


def test_a_drained_hold_opens_nothing_and_a_cleared_or_absent_one_opens() -> None:
    batches = [_batch("a", 1, wave=3)]
    stages = {"a": "pr-open"}
    drained = Hold(state="drained", scope=ME, wave=2, parent=MAIN)
    drain_rec = _record(_open(), {"kind": "queue_drain", "at": AT, "main": MAIN}, wave=2)
    plan = plan_queue(_qs(batches, stages, hold=drained, records=(drain_rec,)))
    assert plan.phase == "releasing" and plan.actions == ()
    plan = plan_queue(_qs(batches, stages, hold=drained))  # no record: still releasing
    assert plan.phase == "releasing" and plan.actions == ()
    for hold in (None, Hold(state="cleared", scope=OTHER, wave=2, parent=MAIN)):
        plan = plan_queue(_qs(batches, stages, hold=hold, records=(drain_rec,)))
        assert plan.phase == "idle" and _kinds(plan) == ["queue-open"], hold


def test_the_phase_reads_records_and_the_hold() -> None:
    hold_open = Hold(state="open", scope=ME, wave=1, parent=MAIN)
    assert queue_phase((), None) == "idle"
    assert queue_phase((_record(_open()),), hold_open) == "open"
    drained = _record(_open(), {"kind": "queue_drain", "at": AT})
    assert queue_phase((drained,), Hold(state="drained", scope=ME, wave=1, parent=MAIN)) == (
        "releasing"
    )
    assert queue_phase((drained,), Hold(state="cleared", scope=ME, wave=1, parent=MAIN)) == "idle"
    assert queue_phase((drained,), None) == "idle"


def test_between_waves_entries_wait_while_a_waved_batch_is_unfinished() -> None:
    batches = [_batch("loose", 1, wave=None), _batch("w2", 2, wave=2)]
    plan = plan_queue(_qs(batches, {"loose": "pr-open", "w2": "dispatched"}))
    assert _one(plan, "queue-open").wave == 2 and plan.waiting == ("loose",)


def test_between_waves_entries_open_a_one_entry_queue_once_every_wave_is_done() -> None:
    approved = {"kind": "approval", "at": "2026-11-20T10:30:00Z", "pr": 101, "head": "head-new"}
    older = {"kind": "approval", "at": "2026-11-20T10:10:00Z", "pr": 100, "head": "head-old"}
    batches = [
        _batch("new", 1, wave=None, events=[approved]),
        _batch("old", 2, wave=None, events=[older]),
        _batch("w2", 3, wave=2),
    ]
    stages = {"new": "pr-open", "old": "pr-open", "w2": "merged"}
    live = {"new": _live(101, "head-new"), "old": _live(100, "head-old")}
    approvals = {"new": Approved("head-new"), "old": Approved("head-old")}
    plan = plan_queue(_qs(batches, stages, live=live, approvals=approvals))
    opened = _one(plan, "queue-open")
    assert opened.wave is None and opened.entries == ("old",)
    assert plan.waiting == ("new",)


def test_an_idle_repo_with_nothing_unfinished_and_nothing_ready_opens_nothing() -> None:
    batches = [_batch("w2", 1, wave=2), _batch("loose", 2, wave=None)]
    live = {"loose": _live(101, checks="pending")}
    plan = plan_queue(_qs(batches, {"w2": "merged", "loose": "pr-open"}, live=live))
    assert plan.actions == () and plan.phase == "idle"


def test_an_entry_needs_an_open_pr_a_valid_approval_and_green_checks() -> None:
    batches = [_batch(b, i, wave=None) for i, b in enumerate(("red", "void", "closed", "ok"))]
    stages = dict.fromkeys(("red", "void", "closed", "ok"), "pr-open")
    live = {
        "red": _live(1, checks="failing"),
        "void": _live(2),
        "closed": _live(3, state="CLOSED"),
        "ok": _live(4),
    }
    approvals = {"red": First("head-1"), "void": Void("h"), "closed": First("head-3"),
                 "ok": First("head-4")}  # fmt: skip
    plan = plan_queue(_qs(batches, stages, live=live, approvals=approvals))
    assert _one(plan, "queue-open").entries == ("ok",) and plan.waiting == ()


# ------------------------------------------------------------- purity


def test_the_planner_reaches_no_git_forge_process_or_clock() -> None:
    import ast

    from tests.unit.triage_fixtures import forbidden_imports

    path = Path(__file__).resolve().parents[2] / "packages/fr/src/fr/triage/wave_queue.py"
    banned = ("fr_dispatch", "subprocess", "fr.triage.gitseam", "fr.ghclient", "fr.gh", "os",
              "time", "shutil", "fr.commands", "fr.triage.queue_exec")  # fmt: skip
    assert forbidden_imports(path, "fr.triage", banned) == []
    calls = {
        n.func.attr
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert not calls & {"now", "utcnow", "today"}


_ = timedelta  # used by later sections
