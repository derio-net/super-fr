"""The Batches page leads every batch PR card with its verdict and lists the facts beneath it
(spec 2026-11-24-batch-merge-readiness R4-R8)."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime

from fr.triage.kanban import Board, Card, build_board
from fr.triage.kanban_render import CSS, render_board
from fr.triage.readiness import Readiness, ReadinessFacts

from tests.unit.test_triage_board_readiness import _closing, _world
from tests.unit.triage_kanban_fixtures import HOSTILE

AT = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)
SCOPE = ["--repo", "example-org/widgets"]


def _page(board: Board) -> str:
    return render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=[])


def _card_html(page: str, bid: str) -> str:
    m = re.search(rf'<details class="card[^"]*" id="card-{bid}".*?</details>', page, re.S)
    assert m, bid
    return m.group(0)


def _swap(board: Board, bid: str, **changes: object) -> Board:
    from fr.triage.kanban import ColumnView

    cols = tuple(
        ColumnView(c.key, c.title, tuple(replace(k, **changes) if k.batch.id == bid else k
                                         for k in c.cards), c.gated)
        for c in board.columns
    )  # fmt: skip
    return replace(board, columns=cols)


def test_a_batch_pr_card_leads_with_its_verdict() -> None:
    f, jd = _world()
    card = _card_html(_page(build_board(f, jd, {})), "a")
    assert re.search(r'<summary><span class="verdict [a-z-]+">Approved, merges next</span>', card)
    assert card.index("Approved, merges next") < card.index('<span class="mono">a</span>')


def test_the_facts_sit_beneath_the_verdict_in_the_body() -> None:
    f, jd = _world()
    card = _card_html(_page(build_board(f, jd, {})), "a")
    body = card[card.index('<div class="body">') :]
    assert body.startswith('<div class="body"><div class="readiness">')
    for label in ("Delivered", "CI", "Merge", "Approval", "Whose move", "Next action"):
        assert f"<dt>{label}</dt>" in body
    assert "<dd>yes</dd>" in body
    assert '<a href="https://github.com/example-org/widgets/pull/11"' in body


def test_the_page_says_when_the_facts_were_collected_where_they_may_lag() -> None:
    f, jd = _world()
    board = build_board(f, jd, {})
    body = _card_html(_page(board), "a")
    assert "as of facts collected" in body


def test_every_verdict_string_is_escaped() -> None:
    f, jd = _world()
    board = build_board(f, jd, {})
    r = board.card("a").readiness
    assert r is not None
    facts = ReadinessFacts(HOSTILE, HOSTILE, HOSTILE, HOSTILE, HOSTILE, HOSTILE, "javascript:x")
    hostile = replace(r, verdict=HOSTILE, facts=facts)
    page = _page(_swap(board, "a", readiness=hostile))
    assert HOSTILE not in page and "<img src=x" not in _card_html(page, "a")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in _card_html(page, "a")
    assert 'href="javascript:' not in page


def test_a_card_with_no_verdict_renders_none() -> None:
    f, jd = _world()
    page = _page(_swap(build_board(f, jd, {}), "a", readiness=None))
    assert 'class="verdict' not in page and 'class="readiness"' not in page


def test_a_close_out_archive_pr_line_renders_on_its_card() -> None:
    from tests.unit.triage_board_fixtures import pr

    f, jd = _closing(pr(30, "chore/archive-m", files=["docs/superpowers/runs/r-m.yaml"]))
    board = build_board(f, jd, {})
    (other,) = board.card("m").others
    card = _card_html(_page(board), "m")
    assert f'<li class="other-pr"><span class="mono">archive#30</span>: {other.verdict}' in card
    assert "<dt>Trust rule</dt>" in card


def test_an_export_pr_line_renders_in_the_queue_section() -> None:
    f, jd = _world()
    board = build_board(f, jd, {})
    facts = ReadinessFacts("admitted", "green at h7", "clean", "none", "the driver",
                           "none: the queue merges it", "https://example.com/pull/7")  # fmt: skip
    from fr.triage.wave_queue import OtherEntry

    export = Readiness("merges-next", "Admitted, merges next", "", facts, True,
                       __import__("fr.triage.readiness", fromlist=["Delivered"]).Delivered(
                           "delivered"), entry=OtherEntry("export#7", "export", 7))  # fmt: skip
    page = _page(replace(board, others=(export,)))
    queue = page[page.index('<section class="queue">') :]
    assert "export#7" in queue and "Admitted, merges next" in queue


def test_the_verdict_styles_use_tokens_never_literal_colours() -> None:
    rules = [ln for ln in CSS.splitlines() if ".verdict" in ln or ".readiness" in ln]
    assert rules
    for ln in rules:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(", ln), ln
    assert any("var(--" in ln for ln in rules)


def test_the_card_type_has_the_two_fields() -> None:
    assert {"readiness", "others"} <= set(Card.__dataclass_fields__)


def test_a_session_owned_verdicts_focus_command_shows_on_the_page_escaped() -> None:
    f, jd = _world()
    board = build_board(f, jd, {})
    r = board.card("a").readiness
    assert r is not None
    cmd = "fr triage batch focus a --repo example-org/widgets"
    facts = replace(r.facts, command=cmd, next_action="let the session finish, or focus it")
    page = _page(_swap(board, "a", readiness=replace(r, facts=facts)))
    assert f'<code class="mono">{cmd}</code>' in _card_html(page, "a")
    hostile = replace(r.facts, command=HOSTILE)
    page = _page(_swap(board, "a", readiness=replace(r, facts=hostile)))
    assert HOSTILE not in page
