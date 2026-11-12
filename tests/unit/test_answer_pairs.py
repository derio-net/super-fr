"""Structural (question, answer) pairs from both harness readers (review p4-r3).

`git.push: ask` / `git.pr: ask` approve only on the answer to the question naming
the request, so the readers pair each answer with its question from the harness's
own answers record, never from a flat list of strings.
"""

from __future__ import annotations

import datetime as _dt

from fr.run.observed import _answer_pairs
from fr.run.opencode_store import ToolItem
from fr.run.telemetry import answered_rounds_in

from tests.unit.transcript_sessions import QUESTION

EPOCH = _dt.datetime(2000, 1, 1, tzinfo=_dt.UTC)


def test_claude_code_pairs_each_answer_with_its_question_from_the_capture() -> None:
    rounds = answered_rounds_in(QUESTION, EPOCH)
    assert rounds
    pairs = dict(p for r in rounds for p in (r.answer_pairs or ()))
    assert pairs["C1 — how should the operator gate on Claude Code be made honest?"] == "Both"
    assert all(r.answer_pairs is not None for r in rounds)


def _item(questions: list[str], answers: object) -> ToolItem:
    return ToolItem(
        session="s", message="m", tool="question", call_id="c", status="completed",
        input={"questions": [{"question": q, "header": "h"} for q in questions]},
        metadata={"answers": answers}, output=None, began=None, ended=None,
    )  # fmt: skip


def test_opencode_pairs_answers_by_position() -> None:
    item = _item(["May fr push? push-x-1", "Colour?"], [["Approve push-x-1"], ["Red"]])
    assert _answer_pairs(item) == [
        ("May fr push? push-x-1", "Approve push-x-1"),
        ("Colour?", "Red"),
    ]


def test_opencode_several_or_no_options_never_read_as_one_label() -> None:
    item = _item(["q1", "q2"], [["Approve a", "Decline"], []])
    assert _answer_pairs(item) == [("q1", '["Approve a", "Decline"]'), ("q2", "[]")]


def test_opencode_a_count_mismatch_pairs_nothing() -> None:
    assert _answer_pairs(_item(["q1", "q2"], [["Approve a"]])) == []
