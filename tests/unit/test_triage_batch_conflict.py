"""Conflict hand-back (spec 2026-10-06-verification-strategies §G; R19-R22).

The structured conflict `batch_merge._update` raises, the `conflict` event and the
judgements schema that carries it, and the pure decision the driver takes on it.
Nothing here reaches a forge, a runner or a clone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.batch_drive import ConflictDecision, conflict_decision
from fr.triage.batch_merge import MergeConflictError, MergeContext, MergeStopError, Slot, _update
from fr.triage.model import (
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    CancelEvent,
    ConflictEvent,
    DispatchEvent,
    Judgements,
)
from pydantic import ValidationError

AT = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


# ------------------------------------------------------- MergeConflictError (R19)


class _Wt:
    def __init__(self, path: Path, conflicted: list[str]) -> None:
        self.path, self.conflicted, self.log = path, conflicted, []

    def merge(self, ref: str) -> list[str]:
        self.log.append(f"merge {ref}")
        return list(self.conflicted)

    def abort_merge(self) -> None:
        self.log.append("abort")


class _Checkout:
    path = Path("/clone")

    def __init__(self, conflicted: list[str]) -> None:
        self.conflicted = conflicted
        self.worktrees: list[_Wt] = []

    def default_branch(self) -> str:
        return "main"

    def add_worktree(self, where: Path, ref: str) -> _Wt:
        wt = _Wt(where, self.conflicted)
        self.worktrees.append(wt)
        return wt


def _slot(batch_id: str = "b1", number: int = 101) -> Slot:
    from types import SimpleNamespace

    pr = SimpleNamespace(number=number, head_ref=f"feat/batch-{batch_id}")
    step = SimpleNamespace(pr=pr, batch=SimpleNamespace(id=batch_id))
    return Slot(step=step, head="sha-101", slot=None)  # type: ignore[arg-type]


def test_an_unresolvable_conflict_is_a_structured_merge_stop(tmp_path: Path) -> None:
    checkout = _Checkout(["src/a.py", "docs/b.md"])
    ctx = MergeContext(
        client=None,  # type: ignore[arg-type]
        checkout=checkout,  # type: ignore[arg-type]
        repo="derio-net/super-fr",
        version=None,
        scratch_root=tmp_path,
        method="squash",
        say=lambda line: None,
    )
    with pytest.raises(MergeConflictError) as raised:
        _update(ctx, _slot(), "sha-101", True, None)
    exc = raised.value
    assert isinstance(exc, MergeStopError)
    assert (exc.batch, exc.head, exc.paths) == ("b1", "sha-101", ("src/a.py", "docs/b.md"))
    where = tmp_path / "feat/batch-b1"
    assert str(exc) == (
        "PR #101 (batch b1) conflicts with origin/main in a change merge will not resolve: "
        "src/a.py, docs/b.md (only a version file whose PR change is the version alone is "
        f"resolved). The scratch worktree is kept for inspection at {where}"
    )
    assert checkout.worktrees[0].log == ["merge origin/main", "abort"]


# ------------------------------------------------------- ConflictEvent, schema 5


CONFLICT = {
    "kind": "conflict",
    "at": "2026-10-06T12:00:00Z",
    "head": "sha-101",
    "paths": ["src/a.py"],
    "delivered": "session",
    "handle": "derio-net/super-fr/run/batch-b1",
}


def _judgements(schema: int, *events: dict[str, Any]) -> dict[str, Any]:
    dispatch = {"kind": "dispatch", "at": "2026-10-06T10:00:00Z", "runner": "fake",
                "handle": "h", "branch": "feat/batch-b1"}  # fmt: skip
    return {
        "schema": schema,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"super-fr#1": {"tier": 1}},
        "batches": [
            {"id": "b1", "title": "b1", "ids": ["super-fr#1"], "events": [dispatch, *events]}
        ],
    }


def test_the_writer_writes_schema_5_and_the_reader_reads_1_to_5() -> None:
    assert JUDGEMENTS_SCHEMA == 6
    assert JUDGEMENTS_READS == (1, 2, 3, 4, 5, 6)
    assert Judgements.model_validate({"schema": 5}).schema_ == 5


@pytest.mark.parametrize("delivered", ["session", "fresh", "held"])
def test_a_conflict_event_round_trips_on_schema_5(delivered: str) -> None:
    got = Judgements.model_validate(_judgements(5, {**CONFLICT, "delivered": delivered}))
    event = got.batches[0].events[-1]
    assert isinstance(event, ConflictEvent)
    assert (event.head, event.paths, event.delivered) == ("sha-101", ["src/a.py"], delivered)
    again = Judgements.model_validate(got.model_dump(mode="json", by_alias=True))
    assert again == got


@pytest.mark.parametrize("schema", [2, 3, 4])
def test_a_conflict_event_needs_schema_5(schema: int) -> None:
    with pytest.raises(ValidationError, match="`conflict` events need schema 5"):
        Judgements.model_validate(_judgements(schema, CONFLICT))


def test_a_conflict_event_needs_a_refused_path_and_a_known_delivery() -> None:
    with pytest.raises(ValidationError):
        ConflictEvent.model_validate({**CONFLICT, "paths": []})
    with pytest.raises(ValidationError):
        ConflictEvent.model_validate({**CONFLICT, "delivered": "mail"})


# ------------------------------------------------------- conflict_decision (R21, R22)


def _dispatch(at: datetime = AT) -> DispatchEvent:
    return DispatchEvent(kind="dispatch", at=at, runner="fake", handle="h", branch="feat/batch-b1")


def _conflict(head: str, delivered: str, at: datetime) -> ConflictEvent:
    return ConflictEvent(
        kind="conflict", at=at, head=head, paths=["src/a.py"],
        delivered=delivered, handle=None,  # type: ignore[arg-type]
    )  # fmt: skip


def _t(minutes: int) -> datetime:
    return AT + timedelta(minutes=minutes)


def test_a_first_conflict_is_handed_back() -> None:
    got = conflict_decision([_dispatch()], "sha-1", ("src/a.py",), ())
    assert got == ConflictDecision("handback")


@pytest.mark.parametrize("delivered", ["session", "fresh", "held"])
def test_a_head_already_handed_back_or_held_is_skipped(delivered: str) -> None:
    events = [_dispatch(), _conflict("sha-1", delivered, _t(1))]
    assert conflict_decision(events, "sha-1", ("src/a.py",), ()) == ConflictDecision("skip")


def test_a_conflict_sharing_a_path_with_an_earlier_one_this_pass_waits_behind_it() -> None:
    earlier = (("b0", ("README.md",)), ("b2", ("src/a.py", "x.py")), ("b3", ("src/a.py",)))
    got = conflict_decision([_dispatch()], "sha-1", ("src/a.py",), earlier)
    assert got == ConflictDecision("wait-behind", behind="b2")
    unrelated = (("b0", ("README.md",)),)
    assert conflict_decision([_dispatch()], "sha-1", ("src/a.py",), unrelated).kind == "handback"


def test_the_same_head_is_skipped_even_when_it_would_wait_behind() -> None:
    events = [_dispatch(), _conflict("sha-1", "session", _t(1))]
    got = conflict_decision(events, "sha-1", ("src/a.py",), (("b2", ("src/a.py",)),))
    assert got.kind == "skip"


def test_two_hand_backs_since_the_dispatch_hold_the_third() -> None:
    events = [_dispatch(), _conflict("sha-1", "session", _t(1)), _conflict("sha-2", "fresh", _t(2))]
    assert conflict_decision(events, "sha-3", ("src/a.py",), ()) == ConflictDecision("held")


def test_held_events_never_count_toward_the_bound() -> None:
    events = [_dispatch(), _conflict("sha-1", "session", _t(1)), _conflict("sha-2", "held", _t(2))]
    assert conflict_decision(events, "sha-3", ("src/a.py",), ()).kind == "handback"


def test_a_new_dispatch_resets_the_count() -> None:
    events = [
        _dispatch(),
        _conflict("sha-1", "session", _t(1)),
        _conflict("sha-2", "fresh", _t(2)),
        CancelEvent(kind="cancel", at=_t(3)),
        _dispatch(_t(4)),
    ]
    assert conflict_decision(events, "sha-3", ("src/a.py",), ()).kind == "handback"
