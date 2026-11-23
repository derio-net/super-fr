"""The `obsolete` batch stage and what reads it (2026-11-22-triage-hardening R8, spec §E).

A batch with no lifecycle event whose members are all in the facts and all closed (or
awaiting their live walk) has nothing left to dispatch: it derives `obsolete`.
"""

from __future__ import annotations

from typing import Any

from fr.triage.batch import (
    CLOSED_OUT,
    dependency_state,
    derive_batch_stage,
    is_open,
    meets_dependency,
)
from fr.triage.batch_drive import drive_pass, finished_waves
from fr.triage.model import Batch, Facts, Issue, Judgements
from fr.triage.views import cancelled_waves, drive_snapshot, next_up, preselected_wave

REPO = "derio-net/example-repo"
DISPATCH = {
    "kind": "dispatch",
    "at": "2026-09-25T10:00:00Z",
    "runner": "herdr",
    "handle": "w1:p0",
    "branch": "feat/batch-a",
}


def _issue(n: int, *, state: str = "open", labels: tuple[str, ...] = ()) -> Issue:
    return Issue(
        repo=REPO,
        number=n,
        title=f"issue {n}",
        state=state,  # type: ignore[arg-type]
        labels=list(labels),
        url=f"https://github.com/{REPO}/issues/{n}",
        author_association="OWNER",
    )


def _facts(*issues: Issue) -> Facts:
    return Facts(
        viewer="operator",
        schema=3,
        scope="derio-net--example-repo",
        kind="repo",
        collected_at="2026-09-26T12:00:00+00:00",
        repos=[REPO],
        issues=list(issues),
        config={},
    )


def _batch(bid: str, ids: list[int], **kw: Any) -> Batch:
    doc = {"id": bid, "title": bid, "ids": [f"example-repo#{n}" for n in ids], **kw}
    return Batch.model_validate(doc)


def _judgements(*batches: Batch) -> Judgements:
    return Judgements.model_validate(
        {
            "schema": 3,
            "tiers": [{"n": 1, "title": "Now"}],
            "issues": {k: {"tier": 1} for b in batches for k in b.ids},
            "batches": [b.model_dump(mode="json") for b in batches],
        }
    )


def _closed(*ns: int) -> list[Issue]:
    return [_issue(n, state="closed") for n in ns]


# ------------------------------------------------------------------ the stage


def test_a_never_dispatched_batch_of_closed_members_is_obsolete() -> None:
    assert derive_batch_stage(_batch("a", [1, 2]), _facts(*_closed(1, 2))) == "obsolete"


def test_closed_members_and_one_awaiting_live_is_obsolete() -> None:
    facts = _facts(*_closed(1), _issue(2, labels=("fr:awaiting-live",)))
    assert derive_batch_stage(_batch("a", [1, 2]), facts) == "obsolete"


def test_a_member_missing_from_the_facts_keeps_it_proposed() -> None:
    assert derive_batch_stage(_batch("a", [1, 2]), _facts(*_closed(1))) == "proposed"


def test_an_open_member_keeps_it_proposed() -> None:
    assert derive_batch_stage(_batch("a", [1, 2]), _facts(*_closed(1), _issue(2))) == "proposed"


def test_a_dispatched_batch_keeps_the_existing_table() -> None:
    facts = _facts(*_closed(1, 2))
    assert derive_batch_stage(_batch("a", [1, 2], events=[DISPATCH]), facts) == "dispatched"


def test_obsolete_is_closed_out_and_not_open() -> None:
    facts = _facts(*_closed(1))
    assert "obsolete" in CLOSED_OUT
    assert not is_open(_batch("a", [1]), facts)


# --------------------------------------------------------------- dependencies


def test_obsolete_and_merged_meet_a_dependency() -> None:
    assert meets_dependency("obsolete") and meets_dependency("merged")
    assert not meets_dependency("proposed") and not meets_dependency("cancelled")


def test_a_batch_after_an_obsolete_one_is_satisfied() -> None:
    batches = [_batch("a", [1]), _batch("b", [2], after=["a"])]
    assert dependency_state("a", batches, _facts(*_closed(1), _issue(2))) == "satisfied"


def test_the_drive_dispatches_a_batch_after_an_obsolete_one_and_never_the_obsolete_one() -> None:
    batches = [_batch("a", [1], wave=1), _batch("b", [2], wave=1, after=["a"])]
    facts = _facts(*_closed(1), _issue(2))
    plan = drive_pass(drive_snapshot(facts, _judgements(*batches)))
    assert [a.batch for a in plan.actions if a.kind == "dispatch"] == ["b"]


# ---------------------------------------------------------------------- waves


def test_a_wave_of_obsolete_and_cancelled_batches_is_finished() -> None:
    batches = [_batch("a", [1], wave=1), _batch("b", [2], wave=1)]
    stages = {"a": "obsolete", "b": "cancelled"}
    assert finished_waves(batches, stages) == frozenset({"1"})


def test_an_all_obsolete_wave_delivered_nothing() -> None:
    batches = [_batch("a", [1], wave=1)]
    assert cancelled_waves(batches, {"a": "obsolete"}) == frozenset({"1"})


def test_preselected_wave_skips_an_obsolete_batch() -> None:
    batches = [_batch("a", [1], wave=2), _batch("b", [2], wave=1)]
    facts = _facts(*_closed(1), _issue(2))
    assert preselected_wave(facts, _judgements(*batches)) == 1


def test_the_waiting_view_does_not_list_a_batch_waiting_on_an_obsolete_one() -> None:
    batches = [_batch("a", [1]), _batch("b", [2], after=["a"])]
    facts = _facts(*_closed(1), _issue(2))
    rows = next_up(facts, _judgements(*batches))
    assert not [r for r in rows if r.waiting and r.ref == "b"]
    assert not [r for r in rows if r.ref == "a"]


# ------------------------------------------------- one awaiting-live rule, claims


def test_all_closed_agrees_with_the_set_apart_awaiting_live_predicate() -> None:
    from fr.labels import FR_AWAITING_LIVE
    from fr.triage.batch import _all_closed
    from fr.triage.sets import is_awaiting_live

    shapes = [
        _issue(1),
        _issue(1, state="closed"),
        _issue(1, labels=(FR_AWAITING_LIVE.name,)),
        _issue(1, state="closed", labels=(FR_AWAITING_LIVE.name,)),
        _issue(1, labels=("bug",)),
    ]
    b = _batch("a", [1])
    for shape in shapes:
        expected = shape.state == "closed" or is_awaiting_live(shape)
        assert _all_closed(b, _facts(shape)) is expected, shape


def test_an_obsolete_wave_batch_releases_its_claims() -> None:
    from fr.triage.claims import owed_claims, releasing

    b = _batch("a", [1, 2], wave=1)
    assert releasing(b, "obsolete", archived=False)
    assert owed_claims([b], {"a": "obsolete"}, ()) == []
    assert owed_claims([b], {"a": "proposed"}, ()) != []


# --------------------------------------------------------- the drive (lens finding T2)


def _held_awaiting(n: int, *, awaiting: bool) -> Issue:
    """Issue *n*, open, claimed by another scope; with *awaiting*, set apart for its walk."""
    from tests.unit.triage_claim_fixtures import FAR, OTHER, facts_claim, marker

    labels = ["fr:claimed", *(["fr:awaiting-live"] if awaiting else [])]
    return _issue(n, labels=tuple(labels)).model_copy(
        update={"claims": [facts_claim(marker(OTHER, "theirs", expires=FAR), 9)]}
    )


def _held_pass(*, awaiting: bool) -> Any:
    from dataclasses import replace

    from fr.triage.claims import held_map

    batches = [_batch("a", [1, 2], wave=1)]
    facts = _facts(*_closed(1), _held_awaiting(2, awaiting=awaiting))
    snap = drive_snapshot(facts, _judgements(*batches))
    snap = replace(snap, me="s-11111111", held=held_map(facts, "s-11111111"))
    return snap, drive_pass(snap)


def test_a_foreign_held_obsolete_batch_emits_no_held_action() -> None:
    snap, plan = _held_pass(awaiting=True)
    assert snap.stages["a"] == "obsolete" and snap.held  # held, and obsolete
    assert not [a for a in plan.actions if a.kind == "held"]
    assert plan.held_by == ()


def test_a_foreign_held_proposed_batch_still_emits_held() -> None:
    """The control for the test above: the same hold on a live batch is reported."""
    snap, plan = _held_pass(awaiting=False)
    assert snap.stages["a"] == "proposed"
    assert [a.batch for a in plan.actions if a.kind == "held"] == ["a"]


def test_a_wave_of_an_obsolete_and_a_cancelled_batch_reports_its_duplicates_once_finished() -> None:
    from dataclasses import replace

    cancel = {"kind": "cancel", "at": "2026-09-25T10:00:00Z", "reason": "split"}
    batches = [_batch("a", [1], wave=1), _batch("b", [2], wave=1, events=[cancel])]
    facts = _facts(*_closed(1), _issue(2))
    snap = drive_snapshot(facts, _judgements(*batches))
    assert snap.stages == {"a": "obsolete", "b": "cancelled"}
    snap = replace(
        snap,
        finished=finished_waves(snap.batches, snap.stages),
        unfinished_waves=frozenset({"1"}),
        duplicate_groups=2,
        dedupe_command="fr triage dedupe",
    )
    plan = drive_pass(snap)
    (dedupe,) = [a for a in plan.actions if a.kind == "dedupe"]
    assert "after wave 1 finished" in dedupe.detail
