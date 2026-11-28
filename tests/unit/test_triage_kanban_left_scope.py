"""The board and `batch list` for a `left-scope` batch (2026-11-27-closeout-state R6)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.triage import kanban_render, render
from fr.triage.batch import left_scope
from fr.triage.kanban import PILL_STAGES, build_board, column_of, fallback_hint, pill_of
from fr.triage.lanes import lane_of
from fr.triage.model import Facts, Judgements
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import batch, dispatch, facts, issue, j, judgements

AT = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)
TEXT = "repo left this scope"


def _world(*, dispatched: bool) -> tuple[Facts, Judgements]:
    """A batch of `other#1`: the facts' only repo is `example-org/widgets`."""
    events = [dispatch("a")] if dispatched else []
    gone = {**batch("a", [1], events=events), "ids": ["other#1"]}
    jd = judgements({"other#1": j(1)}, [gone])
    return facts([issue(1)]), jd


@pytest.mark.parametrize("dispatched", [True, False])
def test_a_left_scope_batch_is_in_done_with_no_lane(dispatched: bool) -> None:
    f, jd = _world(dispatched=dispatched)
    b = jd.batches[0]
    assert left_scope(b, f)
    assert column_of(b, f, jd.batches) == "done"
    assert lane_of(b, f) is None


def test_the_pill_and_the_done_hint_read_repo_left_this_scope() -> None:
    f, jd = _world(dispatched=True)
    b = jd.batches[0]
    assert pill_of(b, f) == TEXT
    assert fallback_hint(b, "done", f, jd.batches, selected=False) == TEXT
    assert "left-scope" in PILL_STAGES


@pytest.mark.parametrize("dispatched", [True, False])
def test_the_card_is_terminal_with_no_jump(dispatched: bool) -> None:
    f, jd = _world(dispatched=dispatched)
    card = build_board(f, jd, {"example-org/other/run/batch-a": "working"}).card("a")
    assert card.terminal and card.show_jump is False
    assert card.column == "done" and card.pill == TEXT
    page = kanban_render.render_board(
        build_board(f, jd, {}),
        scope_args=["--org", "example-org"],
        rendered_at=AT,
        refresh=30,
        notes=[],
    )
    section = re.search(r'<details class="card[^"]*" id="card-a".*?</details>', page, re.S)
    assert section
    assert "bstage-left-scope" in section.group(0) and TEXT in section.group(0)
    assert 'class="jump"' not in section.group(0)


def test_the_rendered_pages_carry_the_left_scope_pill_rule() -> None:
    from fr.triage.fragments import Entry, Resolved
    from fr.triage.history import GENERATED, render_history

    f, jd = _world(dispatched=True)
    rule = ".pill.bstage-left-scope"
    assert rule in render.render_backlog(f, jd)
    resolved = Resolved(order=[Entry(g) for g in GENERATED], fragments={})
    assert rule in render_history(f, jd, snapshots=[], resolved=resolved)


def _list(tmp_path: Path, f: Facts | None) -> str:
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers: [{n: 1, title: Now}]\nissues:\n  'other#1': {tier: 1}\n"
        "batches:\n  - {id: a, title: A, ids: ['other#1']}\n",
        "utf-8",
    )
    if f is not None:
        import json

        (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    result = CliRunner().invoke(
        app, ["triage", "batch", "list", "--repo", "example-org/widgets", "--dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


def test_batch_list_marks_a_left_scope_batch_only_with_facts(tmp_path: Path) -> None:
    f = facts([issue(1)]).model_copy(update={"scope": "example-org--widgets"})
    assert TEXT in _list(tmp_path, f)
    other: Any = tmp_path / "x"
    other.mkdir()
    assert TEXT not in _list(other, None)


def test_batch_list_does_not_mark_a_batch_when_the_repo_list_was_truncated(
    tmp_path: Path,
) -> None:
    from fr.triage.model import Truncation

    warn = Truncation(source="repos", target="example-org", limit=100)
    f = facts([issue(1)]).model_copy(update={"scope": "example-org--widgets", "warnings": [warn]})
    assert TEXT not in _list(tmp_path, f)
