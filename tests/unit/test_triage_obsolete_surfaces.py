"""Check and the Batches page read the obsolete stage (2026-11-22-triage-hardening R9, R10)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fr.cli import app
from fr.triage.check import classify
from fr.triage.kanban import build_board
from fr.triage.kanban_render import render_board
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements

AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _world(*, closed: tuple[int, ...] = (), n: int = 2):  # type: ignore[no-untyped-def]
    f = facts([issue(k, state="closed" if k in closed else "open") for k in range(1, n + 1)])
    jd = judgements(
        {f"widgets#{k}": j() for k in range(1, n + 1)},
        [batch("old", list(range(1, n + 1)))],
    )
    return f, jd


def _check(tmp_path: Path, f, jd, *extra: str):  # type: ignore[no-untyped-def]
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")
    jd_path = tmp_path / "judgements.yaml"
    import yaml

    jd_path.write_text(yaml.safe_dump(jd.model_dump(mode="json", by_alias=True)), encoding="utf-8")
    return CliRunner().invoke(
        app, ["triage", "check", "--repo", "example-org/widgets", "--dir", str(tmp_path), *extra]
    )


def test_check_lists_the_obsolete_batch_with_its_cancel_command(tmp_path: Path) -> None:
    f, jd = _world(closed=(1, 2))
    assert classify(f, jd).obsolete_batches == ["old"]
    out = _check(tmp_path, f, jd)
    assert out.exit_code == 0, out.output
    flat = " ".join(out.output.split())
    assert "obsolete batches (1)" in flat
    assert "fr triage batch cancel old" in flat and "--yes" in flat
    data = json.loads(_check(tmp_path, f, jd, "--json").output)
    assert data["obsolete_batches"] == ["old"]


def test_check_names_the_closed_members_of_a_proposed_batch(tmp_path: Path) -> None:
    f, jd = _world(closed=(1,))
    result = classify(f, jd)
    assert result.obsolete_batches == []
    assert result.stale_members == {"old": ["widgets#1"]}
    flat = " ".join(_check(tmp_path, f, jd).output.split())
    assert "stale members" in flat and "old" in flat and "widgets#1" in flat
    data = json.loads(_check(tmp_path, f, jd, "--json").output)
    assert data["stale_members"] == {"old": ["widgets#1"]}


def test_a_batch_with_no_closed_member_is_neither() -> None:
    f, jd = _world()
    result = classify(f, jd)
    assert result.obsolete_batches == [] and result.stale_members == {}


def test_the_batches_page_shows_an_obsolete_batch_under_its_own_heading() -> None:
    f, jd = _world(closed=(1, 2))
    board = build_board(f, jd, {})
    assert [c.batch.id for c in board.column("obsolete").cards] == ["old"]
    assert not board.column("proposed").cards and not board.column("waiting").cards
    page = render_board(board, scope_args=[], rendered_at=AT, refresh=0, notes=[])
    section = re.search(
        r'<section class="col[^"]*" data-column="obsolete">.*?</section>', page, re.S
    )
    assert section is not None and 'data-batch="old"' in section.group(0)
    assert ">Obsolete<" in section.group(0)


def test_a_proposed_card_lists_its_closed_members() -> None:
    f, jd = _world(closed=(1,))
    board = build_board(f, jd, {})
    page = render_board(board, scope_args=[], rendered_at=AT, refresh=0, notes=[])
    card = re.search(r'<[^>]*data-batch="old".*?</details>', page, re.S)
    assert card is not None
    assert "already closed" in card.group(0) and "widgets#1" in card.group(0)
