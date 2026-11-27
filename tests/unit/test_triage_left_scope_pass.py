"""A `left-scope` batch is left alone by claims, waves and the pass (closeout-state R5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fr.triage import claim_sync as cs
from fr.triage.batch_drive import finished_waves, wave_landings_done
from fr.triage.claims import owed_claims, owed_releases, releasing
from fr.triage.model import Facts, load_judgements
from fr.triage.views import cancelled_waves, preselected_wave
from fr.triage.wave_queue import is_terminal

from tests.unit.test_triage_batch_drive import _batch, _dispatched, _snap
from tests.unit.test_triage_claim_sync import _env
from tests.unit.test_triage_claims import _batch as _cbatch
from tests.unit.test_triage_claims import _dispatch

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_a_left_scope_batch_owes_no_claim_and_no_release() -> None:
    waved = _cbatch("w", ["x#1"], wave=1)
    sent = _cbatch("d", ["x#2"], events=[_dispatch()])
    stages = {"w": "left-scope", "d": "left-scope"}
    assert owed_claims([waved, sent], stages, set()) == []  # type: ignore[arg-type]
    assert owed_releases([waved, sent], stages, set()) == []  # type: ignore[arg-type]
    assert releasing(waved, "left-scope", False) is False


def test_claim_sync_plans_nothing_for_a_left_scope_batch(tmp_path: Path) -> None:
    (tmp_path / "judgements.yaml").write_text(
        "schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  'super-fr#11': {tier: 1}\n"
        "batches:\n  - {id: mine, title: mine, ids: ['super-fr#11'], wave: 1}\n",
        "utf-8",
    )
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    facts = Facts(
        viewer="operator",
        scope="derio-net--other",
        kind="repo",
        collected_at="2026-10-14T11:00:00+00:00",
        repos=["derio-net/other"],
        issues=[],
    )
    me = "s-11111111"
    plan = cs.plan_sync(_env(me, facts), batches, NOW)
    assert plan.ops == [] and plan.held == []


def test_a_left_scope_batch_is_terminal_and_finishes_its_wave() -> None:
    b = _batch("a", 1, wave=1)
    assert is_terminal(b, "left-scope")
    done = _dispatched("m", 2, wave=1)
    stages = {"a": "left-scope", "m": "merged"}
    assert finished_waves([b], {"a": "left-scope"}) == frozenset({"1"})
    assert finished_waves([b, done], stages) == frozenset()  # merged and not archived
    assert cancelled_waves([b], {"a": "left-scope"}) == frozenset()  # counts as delivered


def test_a_wave_of_left_scope_batches_is_done_for_the_landings() -> None:
    a = _batch("a", 1, wave=1)
    snap = _snap([a], {"a": "left-scope"})
    assert wave_landings_done(snap, "derio-net/super-fr", 1) is True


def test_the_pass_plans_no_action_for_a_left_scope_batch() -> None:
    from fr.triage.batch_drive import drive_pass

    from tests.unit.test_triage_batch_drive import _claim

    a = _dispatched("a", 1)
    snap = _snap([a], {"a": "left-scope"}, me="s-me", held={"super-fr#1": _claim()})
    assert not drive_pass(snap).actions


def test_preselected_wave_skips_a_left_scope_batch() -> None:
    from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements

    f = facts([issue(1)])
    judged = {"widgets#1": j(), "other#1": j()}
    gone = batch("a", [1], wave=2)
    gone["ids"] = ["other#1"]  # its repo is not among the facts' repos
    jj = judgements(judged, [gone, batch("b", [1], wave=1)])
    assert preselected_wave(f, jj) == 1


def test_an_orphan_cancelled_batch_plans_no_release(tmp_path: Path) -> None:
    """p2-r1: once cancelled, a dispatched batch whose repo left the scope owes no release:
    its repo is unreachable, so the release would fail every pass."""
    (tmp_path / "judgements.yaml").write_text(
        "schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  'super-fr#11': {tier: 1}\n"
        "batches:\n  - {id: mine, title: mine, ids: ['super-fr#11'], wave: 1, events: ["
        "{kind: dispatch, at: '2026-10-14T10:00:00+00:00', runner: herdr, handle: h, "
        "branch: feat/batch-mine}, {kind: cancel, at: '2026-10-14T10:30:00+00:00'}]}\n",
        "utf-8",
    )
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    facts = Facts(
        viewer="operator",
        scope="derio-net--other",
        kind="repo",
        collected_at="2026-10-14T11:00:00+00:00",
        repos=["derio-net/other"],
        issues=[],
    )
    plan = cs.plan_sync(_env("s-11111111", facts), batches, NOW)
    assert plan.ops == [] and plan.held == []
