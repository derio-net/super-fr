"""The queue and the driver merge by readiness (spec 2026-11-24-batch-merge-readiness §B,
R1, R2, R4).

An approved, green draft whose run cursor still reads `deliver: running` is never admitted,
never readied and never merged; once its run delivered it is. The planner, the driver's
member classification and both `Snapshot` builders read one input path.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fr.triage.batch_drive import drive_pass
from fr.triage.model import CursorPosition, load_judgements
from fr.triage.views import drive_snapshot
from fr.triage.wave_queue import QueueConfig, plan_queue

from tests.unit.test_triage_batch_drive import REPO as DRIVE_REPO
from tests.unit.test_triage_batch_drive import _batch as drive_batch
from tests.unit.test_triage_batch_drive import _snap
from tests.unit.test_triage_batch_drive_cmd import (
    NOW,
    DriveCheckout,
    World,
    _drive,
    _lines,
    _pr_open,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    runner_fixture,  # noqa: F401 - registered as `runner`
    triage_batch_cmd,
    world_fixture,  # noqa: F401 - registered as `world`
)
from tests.unit.test_wave_queue_planner import _abc, _batch, _kinds, _live, _qs

RUNNING = CursorPosition(run="r1", step="deliver", kind="none")
DONE = CursorPosition(run="r1", step="deliver", kind="deliver-done")


def _draft(cursor: CursorPosition) -> Any:
    b = _batch("a", 1)
    live = {"a": _live(100, "head-a", draft=True)}
    return _qs([b], {"a": "pr-open"}, live=live, cursors={"a": ("head-a", cursor, "read")})


def test_an_approved_green_draft_still_delivering_is_no_entry() -> None:
    plan = plan_queue(_draft(RUNNING))
    assert _kinds(plan) == [] and plan.entries == () and plan.waiting == ()
    assert plan.readiness["a"].verdict == "Approved, not delivered"
    assert not plan.readiness["a"].admits


def test_the_same_draft_delivered_opens_the_queue() -> None:
    plan = plan_queue(_draft(DONE))
    assert _kinds(plan) == ["queue-open"]
    assert plan.readiness["a"].admits
    # l-tests-r3: the pass that opens the queue places it first in the order it will take
    assert plan.entries == ()
    assert (plan.readiness["a"].kind, plan.readiness["a"].verdict) == (
        "merges-next",
        "Approved, merges next",
    )


def test_the_plan_holds_a_verdict_for_every_open_batch_in_its_entry_order() -> None:
    plan = plan_queue(_abc())
    assert set(plan.readiness) == {"a", "b", "c"}
    assert [plan.readiness[k].verdict for k in plan.entries] == [
        "Approved, merges next",
        f"Approved, queued behind {plan.entries[0]}",
        f"Approved, queued behind {plan.entries[1]}",
    ]


def test_the_driver_holds_an_approved_pr_not_delivered_as_awaiting() -> None:
    b = drive_batch("a", 1)
    snap = _snap([b], {"a": "pr-open"})
    pr = snap.live["a"]
    held = drive_pass(replace(snap, cursors={"a": (pr.head, RUNNING, "read")}))
    assert "a" in held.awaiting and "a" not in held.ready
    (action,) = [a for a in held.actions if a.kind == "held" and a.batch == "a"]
    assert action.detail == "approved, not delivered: run r1 is at deliver"
    done = drive_pass(replace(snap, cursors={"a": (pr.head, DONE, "read")}))
    assert "a" in done.ready and "a" not in done.awaiting


# ------------------------------------------------------------ both builders


def test_both_snapshot_builders_fill_the_cursors_from_facts(
    tmp_path: Path, world: World, checkout: DriveCheckout
) -> None:
    _pr_open(world, tmp_path)
    facts = world.facts()
    jd = load_judgements(tmp_path / "judgements.yaml")
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd._scope(DRIVE_REPO, None), tmp_path, named=None, checkouts={},
        max_inflight=4, yes=False,
    )  # fmt: skip
    live = driver.snapshot(facts, jd, NOW).cursors
    board = drive_snapshot(facts, jd).cursors
    assert live == board
    assert board["b1"][0] == "sha-101" and board["b1"][2] == "read"
    assert board["b1"][1] is not None and board["b1"][1].kind == "deliver-done"


# ------------------------------------------------------------------ the drive


@pytest.mark.parametrize("delivered", [False, True])
def test_the_drive_never_readies_or_merges_an_approved_draft_until_it_delivered(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch,
    delivered: bool,
) -> None:  # fmt: skip
    from fr.triage import batch_drive

    real = batch_drive.drive_pass
    monkeypatch.setattr(
        triage_batch_cmd, "drive_pass",
        lambda snap: real(replace(snap, wave_queues={DRIVE_REPO: QueueConfig()})),
    )  # fmt: skip
    _pr_open(world, tmp_path, draft=True, delivered=delivered)
    code, out = _drive(tmp_path, "--once")
    assert code in (0, 3), out
    assert world.merged == []
    assert not any(c.startswith("pr_ready") for c in world.calls)
    assert bool(_lines(out, "queue-open")) is delivered
    assert ("approved, not delivered" in out) is not delivered


def test_the_driver_holds_a_gated_approved_pr_for_devops_whatever_its_ci() -> None:
    """p1-r2: a `gate:devops` PR, approved and delivered, is held for DevOps with CI still
    running, as it is when green: the gate is tested directly, not through the verdict."""
    from fr.labels import awaiting_devops

    from tests.unit.test_triage_batch_drive import _live as drive_live

    b = drive_batch("a", 1)
    snap = _snap([b], {"a": "pr-open"})
    pr = snap.live["a"]
    for checks in ("pending", "green"):
        live = {"a": drive_live(pr.number, pr.head, checks=checks, labels=("gate:devops",))}
        got = drive_pass(replace(snap, live=live))
        assert "a" in got.awaiting and "a" not in got.ready, checks
        (action,) = [a for a in got.actions if a.kind == "held" and a.batch == "a"]
        assert action.detail == awaiting_devops(pr.number)
