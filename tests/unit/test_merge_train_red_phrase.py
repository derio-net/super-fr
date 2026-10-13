"""`kanban._red_phrase`: a red PR's card line (merge-train-safety §C, R11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fr.triage.batch_drive import Action
from fr.triage.kanban import _red_phrase
from fr.triage.model import Batch, RedHandbackEvent

AT = datetime(2026, 10, 11, tzinfo=UTC)


def _batch(*events: RedHandbackEvent) -> Batch:
    return Batch(id="b", title="T", ids=["super-fr#1"], events=list(events))


def _event(head: str, delivered: str) -> RedHandbackEvent:
    return RedHandbackEvent(
        kind="red_handback",
        at=AT,
        pr=7,
        head=head,
        checks=["t"],
        delivered=delivered,  # type: ignore[arg-type]
    )


def _red(head: str = "h") -> Action:
    return Action("warn", "b", "d", pr=7, head=head, red=True)


@pytest.mark.parametrize(
    ("events", "want"),
    [
        ((_event("h", "session"),), "red: handed back to its session"),
        ((_event("h", "none"),), "needs you: red PR, no session can take it"),
        ((_event("other", "session"),), ""),  # a hand-back at another head covers nothing
        ((), ""),
    ],
)
def test_the_card_line_follows_the_hand_back_at_the_current_head(
    events: tuple[RedHandbackEvent, ...], want: str
) -> None:
    assert _red_phrase(_batch(*events), _red()) == want


def test_only_a_red_warn_has_a_phrase() -> None:
    assert (
        _red_phrase(_batch(_event("h", "session")), Action("warn", "b", "d", pr=7, head="h")) == ""
    )
    assert (
        _red_phrase(
            _batch(_event("h", "session")), Action("merge", "b", "d", pr=7, head="h", red=True)
        )
        == ""
    )
