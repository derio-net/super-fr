"""Who each Batches card waits for (spec 2026-11-27-board-session-state §A, R1, R2).

Facts and judgements come from `triage_board_fixtures`; nothing here reads a clock, a
forge or a runner.
"""

from __future__ import annotations

from typing import Any

from fr.triage.kanban import build_board
from fr.triage.model import Facts, Judgements

from tests.unit.triage_board_fixtures import batch, dispatch, facts, issue, j, judgements


def _world(
    batches: list[dict[str, Any]], issues: list[dict[str, Any]], **kw: Any
) -> tuple[Facts, Judgements]:
    f = facts(issues, **kw)
    keys = {f"widgets#{i['number']}" for i in issues} | {k for b in batches for k in b["ids"]}
    return f, judgements({k: j(1) for k in sorted(keys)}, batches)


def test_the_harness_renders_a_dispatched_card_in_running() -> None:
    f, jd = _world([batch("a", [1], events=[dispatch("a")])], [issue(1)])
    assert build_board(f, jd, {}).card("a").column == "running"
