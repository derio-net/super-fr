"""R8 (spec 2026-10-12-board-truth, #1111): dispatch, cancel, claims_released is terminal.

A cancelled batch whose claims were released reads cancelled, owes no claim or
release, and never renders as Running, whether or not it has a wave.
"""

from __future__ import annotations

from typing import Any

import pytest
from fr.triage.batch import derive_batch_stage
from fr.triage.claims import owed_claims, owed_releases
from fr.triage.kanban import build_board

from tests.unit.triage_board_fixtures import batch, dispatch, facts, issue, j, judgements

KEYS = ["widgets#1", "widgets#2"]


def _events() -> list[dict[str, Any]]:
    return [
        dispatch("gone"),
        {"kind": "cancel", "at": "2026-10-01T12:00:00Z", "reason": "dropped"},
        {"kind": "claims_released", "at": "2026-10-01T12:01:00Z", "keys": KEYS},
    ]


def _world(wave: int | None):  # type: ignore[no-untyped-def]
    f = facts([issue(1), issue(2)])
    kw: dict[str, Any] = {} if wave is None else {"wave": wave}
    jd = judgements(
        {k: j(1, kind="defect") for k in KEYS},
        [batch("gone", [1, 2], events=_events(), **kw)],
        schema=6,
    )
    return f, jd


@pytest.mark.parametrize("wave", [None, 1], ids=["wave-less", "wave"])
def test_a_cancelled_released_batch_is_terminal_and_owes_nothing(wave: int | None) -> None:
    f, jd = _world(wave)
    b = jd.batches[0]
    stage = derive_batch_stage(b, f)
    assert stage == "cancelled"
    stages = {b.id: stage}
    assert not [p for p in owed_claims(jd.batches, stages, set()) if p[1] == "gone"]
    assert not [p for p in owed_releases(jd.batches, stages, set()) if p[1] == "gone"]


@pytest.mark.parametrize("wave", [None, 1], ids=["wave-less", "wave"])
def test_a_cancelled_released_batch_never_renders_as_running(wave: int | None) -> None:
    f, jd = _world(wave)
    # A runner still answering for the dead session must not revive the card.
    board = build_board(f, jd, {"example-org/widgets/run/batch-gone": "working"})
    card = board.card("gone")
    assert card.stage == "cancelled"
    assert card.column != "running"
    assert "gone" not in [c.batch.id for c in board.column("running").cards]
    assert "session running" not in card.hint
