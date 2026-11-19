"""The board page (spec 2026-10-05 §D; R1, R3, R4, R5, R10, R14, R15).

Pure render over `triage_kanban_fixtures.world()`: no browser, no clock, no forge.
"""

from __future__ import annotations

import html
import re
import shlex
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fr.triage import kanban_render
from fr.triage.components import GUTTER_CSS, PAGE_SCRIPT, TOKENS_CSS
from fr.triage.kanban import Board, Card, EventRow, build_board, cutoff_hidden_waves
from fr.triage.kanban_render import CSS, SCRIPT, render_board

from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements
from tests.unit.triage_fixtures import forbidden_imports
from tests.unit.triage_kanban_fixtures import HOSTILE, world

AT = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)
SCOPE = ["--repo", "example-org/widgets"]


def _board(**kw: object) -> tuple[Board, list[str]]:
    f, jd, statuses, notes = world(**kw)  # type: ignore[arg-type]
    return build_board(f, jd, statuses), notes


def _page(*, scope: list[str] | None = None, refresh: int = 30, **kw: object) -> str:
    board, notes = _board(**kw)
    return render_board(
        board, scope_args=scope or SCOPE, rendered_at=AT, refresh=refresh, notes=notes
    )


def _card(page: str, bid: str) -> str:
    m = re.search(rf'<details class="card[^"]*" id="card-{bid}".*?</details>', page, re.S)
    assert m, bid
    return m.group(0)


def _script(page: str) -> str:
    m = re.search(r"<script>(.*?)</script>", page, re.S)
    assert m
    return m.group(1)


def test_a_board_with_no_batches_says_so() -> None:
    f = facts([])
    board = build_board(f, judgements({}), {})
    page = render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=30, notes=[])
    assert "No batches" in page and 'class="board"' not in page
    assert "<!DOCTYPE html>" in page and "<title>" in page


def test_seven_columns_with_their_counts_in_order() -> None:
    page = _page()
    heads = re.findall(
        r'<h2><button[^>]*>(\w[\w ·]*)</button> <span class="count">(\d+)</span></h2>', page
    )
    # The fixture's partial batch is owed its close-out: Partial, not Done (gh#985).
    assert heads == [
        ("Proposed", "2"), ("Waiting", "2"), ("Running", "3"),
        ("Needs you · Developer", "0"), ("PR open", "3"), ("Needs you · Reviewer", "0"),
        ("Needs you · Tester", "0"), ("Needs you · DevOps", "0"),
        ("Closing out", "3"), ("Partial", "1"), ("Done", "3"),
    ]  # fmt: skip


def test_the_wide_grid_has_one_track_per_column() -> None:
    from fr.triage.kanban import COLUMNS
    from fr.triage.kanban_render import CSS

    assert f".board {{ display: grid; grid-template-columns: repeat({len(COLUMNS)}," in CSS


def test_a_column_holds_a_card_element_exactly_when_its_count_is_not_zero() -> None:
    # The wide layout collapses a column by `.col:not(:has(.card))`, so "no .card inside"
    # must mean "count 0" for every column, batch cards and gated cards alike.
    page = _page()
    cols = re.findall(
        r'<section class="col[^"]*" data-column="([^"]+)"><h2><button[^>]*>[^<]*</button> '
        r'<span class="count">(\d+)</span></h2>(.*?)</section>',
        page,
        re.S,
    )
    assert len(cols) == 11
    for key, count, body in cols:
        assert (re.search(r'class="card[ "]', body) is None) == (count == "0"), key
    assert {count == "0" for _, count, _ in cols} == {True, False}


def test_the_wide_layout_collapses_a_collapsed_column_to_a_rotated_strip() -> None:
    m = re.search(r"@media \(min-width: 1101px\) \{(.*?)\n\}", CSS, re.S)
    assert m, "the collapse is scoped to the wide layout"
    wide = m.group(1)
    assert ".board { display: flex; }" in wide
    # The state is the column's own class, not a reading of its cards: a viewer can collapse
    # a column that holds cards and expand one that holds none (R10).
    assert ".col.collapsed { flex: 0 0 " in wide
    assert ":has(" not in wide
    # Reads bottom to top: a -90 degree turn of the title.
    assert "writing-mode: vertical-rl" in wide and "rotate(180deg)" in wide
    # The narrow layouts keep the grid, where a strip would waste a row.
    assert "max-width: 1100px" in CSS and "max-width: 720px" in CSS


def _columns(page: str) -> list[tuple[str, str, str, str]]:
    """(key, classes, h2, body) of every column section."""
    return re.findall(
        r'<section class="col([^"]*)" data-column="([^"]+)">(<h2>.*?</h2>)(.*?)</section>',
        page,
        re.S,
    )  # type: ignore[return-value]


def test_every_column_header_holds_a_toggle_that_says_whether_it_is_expanded() -> None:
    cols = _columns(_page())
    assert len(cols) == 11
    for classes, key, h2, body in cols:
        button = re.search(r"<button([^>]*)>", h2)
        assert button, key
        attrs = button.group(1)
        empty = re.search(r'class="card[ "]', body) is None
        assert 'type="button"' in attrs
        assert f'aria-expanded="{"false" if empty else "true"}"' in attrs, key
        assert ("collapsed" in classes.split()) == empty, key
        # The toggle names the region it controls, and that region holds the cards.
        controls = re.search(r'aria-controls="([^"]+)"', attrs)
        assert controls and f'id="{controls.group(1)}"' in body, key
    assert {"collapsed" in c.split() for c, *_ in cols} == {True, False}


def test_a_gated_only_column_starts_expanded() -> None:
    page = _page()
    for classes, key, h2, body in _columns(page):
        if "data-gated-pr" in body:
            assert "collapsed" not in classes.split(), key


def test_the_body_names_the_scope_the_column_state_is_kept_under() -> None:
    page = _page()
    assert f'data-scope="{html.escape(_board()[0].scope)}"' in page
    assert 'data-scope="x&quot;y&lt;"' in render_board(
        replace(_board()[0], scope='x"y<'), scope_args=SCOPE, rendered_at=AT, refresh=0, notes=[]
    )


def test_the_script_remembers_each_column_under_a_scope_key_and_guards_every_access() -> None:
    assert '"fr-triage:" + ' in SCRIPT and '":col:"' in SCRIPT
    # Every localStorage read or write sits inside a try block.
    for m in re.finditer(r"localStorage\.(getItem|setItem)", SCRIPT):
        before = SCRIPT[: m.start()]
        assert before.rfind("try {") > before.rfind("}"), m.group(0)


# ------------------------------------------------------------- the wave cutoff (R18)


def _cards() -> list[Card]:
    board, _ = _board()
    return [c for col in board.columns for c in col.cards]


def _as(card: Card, wave: int | None, stage: str, *events: str) -> Card:
    return replace(
        card,
        wave=wave,
        stage=stage,  # type: ignore[arg-type]
        events=tuple(EventRow("dispatch", datetime.fromisoformat(e), "") for e in events),
    )


def _page_of(cards: list[Card], *, at: datetime = AT) -> str:
    """A page whose Done column holds *cards* exactly, rendered at the pinned clock *at*."""
    from fr.triage.kanban import ColumnView

    board = Board(
        scope="example-org--widgets",
        collected_at="2026-10-05T00:00:00Z",
        columns=(ColumnView(key="done", title="Done", cards=tuple(cards)),),
    )
    return render_board(board, scope_args=SCOPE, rendered_at=at, refresh=0, notes=[])


def _named(card: Card, bid: str) -> Card:
    return replace(card, batch=card.batch.model_copy(update={"id": bid}))


def _marked(page: str) -> dict[str, bool]:
    """Per batch id, whether its card carries the server's cutoff marker."""
    out = {}
    for m in re.finditer(r'<details class="card[^"]*" id="card-([^"]+)"([^>]*)>', page):
        out[m.group(1)] = "data-cutoff-hidden" in m.group(2)
    return out


def test_the_server_marks_the_cards_of_the_waves_the_cutoff_hides() -> None:
    base = _cards()
    cards = [
        _named(_as(base[0], 1, "merged", "2026-08-01T09:00:00+00:00"), "old-a"),
        _named(_as(base[1], 1, "merged"), "old-b"),
        _named(_as(base[2], 2, "merged", "2026-11-01T09:00:00+00:00"), "recent"),
        _named(_as(base[3], 3, "dispatched"), "live"),
        _named(_as(base[4], None, "merged"), "nowave"),
    ]
    assert _marked(_page_of(cards)) == {
        "old-a": True,
        "old-b": True,  # a quiet, finished wave: every card of it
        "recent": False,
        "live": False,
        "nowave": False,
    }
    # the markers are that helper's answer, not a second rule
    assert cutoff_hidden_waves(cards, AT) == {"1"}


def test_the_marker_follows_the_thirty_day_boundary_to_the_second() -> None:
    base = _cards()

    def marker(event_at: str) -> bool:
        card = _named(_as(base[0], 1, "merged", event_at), "b")
        return _marked(_page_of([card]))["b"]

    assert marker("2026-09-05T21:30:00+00:00") is False  # exactly 30 days: still active
    assert marker("2026-09-05T21:29:59+00:00") is True  # one second older: quiet
    assert marker("2026-09-05T21:30:01+00:00") is False


def test_cards_carry_their_wave_and_no_date_inputs_for_the_script() -> None:
    page = _page_of([_as(_cards()[0], 4, "merged", "2026-08-01T09:00:00+00:00")])
    assert 'data-wave="4"' in page
    # the browser applies the server's marker; it is given no dates to decide from
    assert "data-active" not in page and "data-terminal" not in page
    assert "data-rendered" not in page


def test_the_script_only_applies_the_marker_and_parses_no_dates() -> None:
    assert "data-cutoff-hidden" in SCRIPT
    assert "Date.parse" not in SCRIPT and "new Date" not in SCRIPT


def test_every_selector_the_script_queries_matches_the_markup_it_acts_on() -> None:
    page = _page()
    selectors = re.findall(r'querySelector(?:All)?\("([^"]+)"\)', SCRIPT)
    assert selectors
    for sel in selectors:
        simple = re.sub(r":not\([^)]*\)", "", sel).split(" ")[-1]
        m = re.fullmatch(r"([a-z0-9]*)(?:\.([\w-]+))?(?:#([\w-]+))?", simple)
        if m is None:
            continue  # an attribute selector: pinned by its own test
        tag, cls, ident = m.groups()
        if ident:
            assert f'id="{ident}"' in page, sel
        elif cls:
            assert re.search(rf'<{tag or "[a-z]+"} [^>]*class="[^"]*\b{cls}\b', page), sel
        else:
            assert f"<{tag}" in page, sel


def test_the_script_reads_the_column_key_and_toggle_the_markup_carries() -> None:
    page = _page()
    for key in ("proposed", "running", "done"):
        assert re.search(
            rf'<section class="col[^"]*" data-column="{key}"><h2><button[^>]*class="coltoggle"',
            page,
        ), key
    assert "dataset.column" in SCRIPT and "button.coltoggle" in SCRIPT


def test_the_cutoff_toggle_is_a_pressed_toolbar_button_by_default() -> None:
    page = _page()
    bar = re.search(r'<div class="toolbar" role="toolbar"[^>]*>(.*?)</div>', page, re.S)
    assert bar
    button = re.search(r"<button([^>]*)>([^<]*)</button>", bar.group(1))
    assert button
    assert 'aria-pressed="true"' in button.group(1) and 'id="cutoff"' in button.group(1)
    assert button.group(2) == "last 30 days"
    # A board with nothing on it has nothing to cut off.
    board = build_board(facts([]), judgements({}), {})
    empty = render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=[])
    assert 'id="cutoff"' not in empty


def _card_named(bid: str) -> Card:
    board, _ = _board()
    return board.card(bid)


def test_a_merged_batch_never_archived_and_still_closing_out_is_terminal() -> None:
    card = _card_named("c-none")  # PR merged, no close-out event: the Closing out column
    assert card.column == "closing-out" and card.stage == "merged"
    assert card.terminal is True


def test_each_terminal_kind_is_terminal() -> None:
    assert _card_named("c-session").terminal  # merged, close-out started but not archived
    assert _card_named("d-done").terminal  # merged and archived
    assert _card_named("x-cancelled").stage == "cancelled" and _card_named("x-cancelled").terminal
    assert replace(_card_named("r-run"), stage="abandoned").terminal  # abandoned
    # a partial batch is terminal once its close-out archived, not before
    partial = _card_named("d-partial")
    assert partial.stage == "partial" and not partial.terminal


def test_a_batch_still_in_flight_or_waiting_is_not_terminal() -> None:
    for bid in ("p-queued", "w-wait", "r-run", "o-draft", "o-ready"):
        assert not _card_named(bid).terminal, bid


def test_a_wave_of_only_terminal_batches_with_no_recent_event_is_hidden() -> None:
    base = _cards()
    old = "2026-08-01T09:00:00+00:00"
    cards = [_as(base[0], 1, "merged", old), _as(base[1], 1, "merged")]
    assert cutoff_hidden_waves(cards, AT) == frozenset({"1"})


def test_a_recent_event_in_any_card_keeps_the_wave_shown() -> None:
    base = _cards()
    cards = [
        _as(base[0], 1, "merged", "2026-08-01T09:00:00+00:00"),
        _as(base[1], 1, "merged", "2026-09-20T09:00:00+00:00"),  # 15 days before AT
    ]
    assert cutoff_hidden_waves(cards, AT) == frozenset()


def test_the_cutoff_is_thirty_days_before_the_render_and_days_is_a_parameter() -> None:
    base = _cards()
    cards = [_as(base[0], 1, "merged", "2026-09-05T21:30:00+00:00")]  # exactly 30 days
    assert cutoff_hidden_waves(cards, AT) == frozenset()
    assert cutoff_hidden_waves(cards, AT, days=29) == frozenset({"1"})
    assert cutoff_hidden_waves([_as(base[0], 1, "merged", "2026-09-05T21:29:59+00:00")], AT) == {
        "1"
    }


def test_a_wave_with_a_batch_that_is_not_terminal_always_shows() -> None:
    base = _cards()
    cards = [_as(base[0], 2, "merged"), _as(base[1], 2, "proposed")]  # proposed, eventless
    assert cutoff_hidden_waves(cards, AT) == frozenset()


def test_cards_with_no_wave_are_never_hidden() -> None:
    base = _cards()
    assert cutoff_hidden_waves([_as(base[0], None, "merged")], AT) == frozenset()


def test_each_wave_is_judged_on_its_own_cards() -> None:
    base = _cards()
    cards = [
        _as(base[0], 1, "merged"),
        _as(base[1], 2, "dispatched", "2026-08-01T09:00:00+00:00"),
        _as(base[2], 3, "merged", "2026-10-01T09:00:00+00:00"),
    ]
    assert cutoff_hidden_waves(cards, AT) == frozenset({"1"})


def test_the_script_keeps_the_cutoff_choice_like_the_column_state() -> None:
    assert re.search(r'"fr-triage:" \+ scope \+ ":cutoff"', SCRIPT)


def test_every_card_is_a_details_element_with_its_id() -> None:
    board, _ = _board()
    page = _page()
    for col in board.columns:
        for card in col.cards:
            assert '<details class="card' in page
            assert f'id="card-{card.batch.id}"' in page
    assert page.count("<details ") == board.batch_count


def test_a_collapsed_card_shows_id_title_wave_members_status_hint_and_jump() -> None:
    card = _card(_page(), "r-run")
    summary = re.search(r"<summary>.*?</summary>", card, re.S)
    assert summary
    head = summary.group(0)
    for needle in (
        "r-run",
        "batch r-run",
        "wave 1",
        "2 issues",
        "working",
        "session running",
        "jump",
    ):
        assert needle in head, needle


def test_the_jump_button_follows_the_session_status() -> None:
    page = _page()
    assert 'class="jump"' in _card(page, "r-blocked")
    assert 'class="jump"' in _card(page, "o-ready")  # unknown keeps it
    assert 'class="jump"' not in _card(page, "r-absent")  # no session hides it
    assert "no session" in _card(page, "r-absent")
    assert 'class="jump"' not in _card(page, "p-queued")  # never dispatched


def test_every_r4_section_is_on_a_full_card() -> None:
    card = _card(_page(), "c-session")
    for heading in ("Issues", "Pull request", "Lifecycle", "Timeline", "Close-out session"):
        assert f"<h4>{heading}</h4>" in card, heading
    assert "merged" in card and "https://github.com/example-org/widgets/pull/10" in card
    assert "post_merge" in card and "closeout" in card
    timeline = card.split("<h4>Timeline</h4>", 1)[1]  # the front's own --closeout precedes it
    assert timeline.index("dispatch") < timeline.index("post_merge") < timeline.index("closeout")


def test_a_card_without_a_pr_has_no_pull_request_section() -> None:
    card = _card(_page(), "r-run")
    assert "<h4>Pull request</h4>" not in card
    assert "<h4>Close-out session</h4>" not in card


def test_pr_details_show_draft_checks_mergeable_and_review() -> None:
    page = _page()
    assert "draft" in _card(page, "o-draft")
    ready = _card(page, "o-ready")
    for needle in ("ready", "3 pass", "MERGEABLE", "APPROVED"):
        assert needle in ready, needle
    assert "2 fail" in _card(page, "o-red")


def test_lifecycle_shows_launch_with_default_marking_and_a_dash_when_unset() -> None:
    ready = _card(_page(), "o-ready")
    assert "claude" in ready and "claude-opus-5-5" in ready and "5.6.0" in ready
    assert "(default)" not in ready
    queued = _card(_page(), "p-queued")
    assert "codex (default)" in queued and "gpt-5 (default)" in queued
    f, jd, st, _ = world()
    bare = build_board(f.model_copy(update={"config": {}}), jd, st)  # no config: no default
    assert "<dd>—</dd>" in render_board(bare, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=[])


def test_lifecycle_lists_each_dependency_with_its_state() -> None:
    card = _card(_page(), "w-blocked")
    assert "x-cancelled" in card and "unsatisfiable" in card
    assert "blocked" in card


def test_a_hand_closeout_has_no_closeout_button() -> None:
    page = _page()
    hand = _card(page, "c-hand")
    assert hand.count('class="jump"') == 2  # the batch's own session: front and body
    assert "closeout" not in "".join(re.findall(r'data-command="([^"]*)"', hand))
    sess = _card(page, "c-session")
    assert sess.count('class="jump"') == 3  # front (close-out), body batch, body close-out


def test_a_cancelled_card_carries_its_pill_and_a_blocked_session_highlights() -> None:
    page = _page()
    assert 'class="pill stage-cancelled"' in _card(page, "x-cancelled")
    assert "needs-you" in _card(page, "r-blocked").split(">", 1)[0]
    assert "needs-you" not in _card(page, "r-run").split(">", 1)[0]


def test_the_jump_command_is_the_quoted_focus_command() -> None:
    page = _page()
    card = _card(page, "c-session")
    commands = [html.unescape(c) for c in re.findall(r'data-command="([^"]*)"', card)]
    expected = shlex.join(["fr", "triage", "batch", "focus", "c-session", *SCOPE])
    assert commands == [expected + " --closeout", expected, expected + " --closeout"]
    visible = [html.unescape(c) for c in re.findall(r'<code class="cmd"[^>]*>(.*?)</code>', card)]
    assert visible == [expected, expected + " --closeout"]


def test_the_command_carries_dir_only_as_given_and_hostile_dirs_are_quoted_then_escaped() -> None:
    hostile = "/tmp/a b;rm -rf ~"
    page = _page(scope=[*SCOPE, "--dir", hostile])
    card = _card(page, "r-run")
    raw = re.search(r'data-command="([^"]*)"', card)
    assert raw
    cmd = html.unescape(raw.group(1))
    assert cmd == shlex.join(["fr", "triage", "batch", "focus", "r-run", *SCOPE, "--dir", hostile])
    assert "'/tmp/a b;rm -rf ~'" in cmd
    assert "&#x27;/tmp/a b;rm -rf ~&#x27;" in raw.group(1)
    assert "--dir" not in html.unescape(
        re.search(r'data-command="([^"]*)"', _card(_page(), "r-run")).group(1)
    )  # type: ignore[union-attr]


def test_hostile_titles_are_escaped_and_never_reach_the_script() -> None:
    page = _page(hostile=True)
    assert HOSTILE not in page
    assert html.escape(HOSTILE, quote=True) in page
    assert page.count("<script") == 1
    assert "alert" not in _script(page)
    assert "<img" not in page


def test_non_https_urls_are_not_linked() -> None:
    board, _ = _board()
    card = next(c for col in board.columns for c in col.cards if c.batch.id == "r-run")
    evil = card.members[0].__class__("k#1", "t", "javascript:alert(1)", "backlog")
    assert kanban_render._member(evil).count("href") == 0  # type: ignore[attr-defined]


def test_the_script_element_is_the_module_constant() -> None:
    assert _script(_page()) == SCRIPT + PAGE_SCRIPT
    assert _script(_page(hostile=True)) == SCRIPT + PAGE_SCRIPT


def test_refresh_reaches_the_script_as_a_body_attribute() -> None:
    assert re.search(r'<body data-refresh="30"[ >]', _page())
    assert re.search(r'<body data-refresh="0"[ >]', _page(refresh=0))
    assert "dataset.refresh" in SCRIPT


def test_rendered_and_collected_times_and_page_notes_are_shown() -> None:
    page = _page()
    assert "2026-10-05 21:30 UTC" in page
    assert "2026-10-02 12:00 UTC" in page
    assert "runner `ghost` could not be loaded" in page


def test_the_page_notes_are_escaped() -> None:
    board, _ = _board()
    page = render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=["<b>x</b>"])
    assert "<b>x</b>" not in page and "&lt;b&gt;x&lt;/b&gt;" in page


def test_the_same_inputs_give_the_same_bytes() -> None:
    assert _page() == _page()


def test_the_look_is_shared_and_stacks_at_phone_width() -> None:
    assert TOKENS_CSS in CSS and GUTTER_CSS in CSS
    assert "max-width: 720px" in CSS
    assert "overflow-wrap" in CSS


def test_the_script_keeps_expanded_cards_and_scroll_in_guarded_local_storage() -> None:
    assert "localStorage" in SCRIPT and "location.pathname" in SCRIPT
    assert SCRIPT.count("try {") >= 3
    assert "location.reload" in SCRIPT and "clipboard" in SCRIPT and '"copied"' in SCRIPT


def test_the_renderer_reads_no_clock_and_no_fr_dispatch() -> None:
    path = Path(kanban_render.__file__)
    assert forbidden_imports(path, "fr.triage", ("fr_dispatch", "time")) == []
    assert "datetime.now" not in path.read_text(encoding="utf-8")


# ------------------------------------------- claims: held elsewhere, card expiry (R13)


def _claim_board(
    *,
    held_expired: bool = False,
    own: bool = True,
    held: bool = True,
    own_expires: str = "2026-10-07T09:30:00Z",
) -> str:
    claim = {
        "batch": "theirs",
        "claimed": "2026-10-05T12:00:00Z",
        "heartbeat": "2026-10-05T12:00:00Z",
        "comment_id": 1,
        "created_at": "2026-10-05T12:00:00Z",
    }
    issues = [issue(1, claims=[{**claim, "signer": "s-aaaaaaaa", "batch": "a",
                                "expires": own_expires}] if own else [])]  # fmt: skip
    if held:
        gone = "2026-10-05T08:00:00Z" if held_expired else "2026-10-07T12:00:00Z"
        issues.append(
            issue(2, title=HOSTILE, claims=[{**claim, "signer": "s-bbbbbbbb", "expires": gone}])
        )
    f = facts(issues)
    jd = judgements({"widgets#1": j(1), "widgets#2": j(1)}, [batch("a", [1], wave=1)])
    board = build_board(f, jd, {}, me="s-aaaaaaaa", now=AT)
    return render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=[])


def test_the_held_elsewhere_group_names_issue_holder_batch_and_expiry() -> None:
    page = _claim_board()
    m = re.search(r'<section class="held".*?</section>', page, re.S)
    assert m
    group = m.group(0)
    assert "Held elsewhere" in group and "s-bbbbbbbb" in group and "theirs" in group
    assert (
        "2026-10-07T12:00:00" in group
        and 'href="https://github.com/example-org/widgets/issues/2"' in group
    )
    assert "expired" not in group.replace("expires", "")


def test_the_held_group_is_absent_when_nothing_is_held() -> None:
    assert "Held elsewhere" not in _claim_board(held=False)


def test_an_expired_held_claim_is_marked() -> None:
    group = re.search(r'<section class="held".*?</section>', _claim_board(held_expired=True), re.S)
    assert group and 'class="pill flag">expired<' in group.group(0)
    assert "fr triage claim take widgets#2" in group.group(0)


def test_forge_text_in_the_held_group_is_escaped() -> None:
    page = _claim_board()
    assert HOSTILE not in page and html.escape(HOSTILE) in page


def test_an_own_card_shows_when_its_claims_expire() -> None:
    card = _card(_claim_board(), "a")
    assert "claims expire 2026-10-07 09:30 UTC" in card


def test_an_own_expired_claim_is_marked_on_the_card() -> None:
    card = _card(_claim_board(own_expires="2026-10-05T09:30:00Z"), "a")
    assert "claims expired 2026-10-05 09:30 UTC" in card


def test_a_card_with_no_claims_shows_no_claim_line() -> None:
    assert "claims expire" not in _card(_claim_board(own=False), "a")


def test_the_page_keeps_its_tokens_and_gutter_with_the_held_group() -> None:
    page = _claim_board()
    assert TOKENS_CSS in page and GUTTER_CSS in page


# ------------------------------------------------ the quota footer (quota-pacing R14)


def test_the_footer_names_the_last_budget_and_when_the_facts_were_collected() -> None:
    from fr.triage.quota import Budget

    board, notes = _board()
    budget = Budget("graphql", 812, 5000, datetime(2026, 10, 12, 16, 43, tzinfo=UTC))
    page = render_board(
        board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes, budget=budget
    )
    footer = page[page.index("<footer") : page.index("</footer>")]
    stamp = kanban_render._stamp(board.collected_at)
    assert f"forge quota: graphql 812/5000, resets 16:43Z · facts collected {stamp}" in footer


def test_the_footer_names_the_reset_in_utc_whatever_offset_the_record_carried() -> None:
    from fr.triage.quota import budget_from_json

    board, notes = _board()
    for reset, shown in (
        ("2026-10-12T18:43:00+02:00", "16:43Z"),
        ("2026-10-12T16:43:00", "16:43Z"),
    ):
        budget = budget_from_json(
            {"resource": "graphql", "remaining": 1, "limit": 5, "reset": reset}
        )
        page = render_board(
            board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes, budget=budget
        )
        assert f"resets {shown}" in page[page.index("<footer") : page.index("</footer>")]


def test_the_footer_escapes_the_resource_name() -> None:
    from fr.triage.quota import Budget

    board, notes = _board()
    budget = Budget("<b>x&y</b>", 1, 5, datetime(2026, 10, 12, 16, 43, tzinfo=UTC))
    page = render_board(
        board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes, budget=budget
    )
    footer = page[page.index("<footer") : page.index("</footer>")]
    assert "&lt;b&gt;x&amp;y&lt;/b&gt;" in footer and "<b>x" not in footer


def test_no_recorded_budget_renders_the_footer_as_it_always_did() -> None:
    board, notes = _board()
    plain = render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes)
    none = render_board(
        board, scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes, budget=None
    )
    assert plain == none and "forge quota" not in plain


def _summary(card: str) -> str:
    return card.split("</summary>", 1)[0]


def _body_of(card: str) -> str:
    return card.split("</summary>", 1)[1]


def test_a_live_closeout_takes_the_card_front_and_the_body_jumps_to_the_batch() -> None:
    card = _card(_page(), "c-session")
    front = _summary(card)
    cmds = [html.unescape(c) for c in re.findall(r'data-command="([^"]*)"', front)]
    assert len(cmds) == 1 and cmds[0].endswith(" --closeout")
    assert "status-idle" in front and "status-done" not in front
    body = _body_of(card)
    body_cmds = [html.unescape(c) for c in re.findall(r'data-command="([^"]*)"', body)]
    assert [c.endswith(" --closeout") for c in body_cmds] == [False, True]  # each pair


def test_without_a_live_closeout_the_front_is_the_batch_session() -> None:
    page = _page()
    for bid in ("c-hand", "r-run"):
        front = _summary(_card(page, bid))
        cmds = [html.unescape(c) for c in re.findall(r'data-command="([^"]*)"', front)]
        assert len(cmds) == 1 and not cmds[0].endswith(" --closeout"), bid
        body_cmds = re.findall(r'data-command="([^"]*)"', _body_of(_card(page, bid)))
        assert len(body_cmds) == 1 and "closeout" not in body_cmds[0], bid


def test_card_front_is_derived_from_the_closeout_status() -> None:
    board, _ = _board()
    assert board.card("c-session").front == "closeout"
    assert board.card("c-hand").front == "batch"
    assert board.card("r-run").front == "batch"
    for status in (None, "absent", "unknown"):
        from dataclasses import replace

        assert replace(board.card("c-session"), closeout_status=status).front == "batch"


def _closeout_variant(status: str) -> str:
    f, jd, st, notes = world()
    st = {**st, "example-org/widgets/run/closeout-c-session": status}
    page = render_board(
        build_board(f, jd, st), scope_args=SCOPE, rendered_at=AT, refresh=0, notes=notes
    )
    return _card(page, "c-session")


def _cmds(fragment: str) -> list[str]:
    return [html.unescape(c) for c in re.findall(r'data-command="([^"]*)"', fragment)]


def test_an_unknown_closeout_status_leaves_the_front_to_the_batch_session() -> None:
    card = _closeout_variant("unknown")
    front = _summary(card)
    assert len(_cmds(front)) == 1 and "--closeout" not in _cmds(front)[0]
    assert "status-done" in front and "status-unknown" not in front
    assert [c.endswith("--closeout") for c in _cmds(_body_of(card))] == [False, True]


def test_an_absent_closeout_has_a_batch_front_and_no_closeout_jump_or_code() -> None:
    card = _closeout_variant("absent")
    front = _summary(card)
    assert len(_cmds(front)) == 1 and "--closeout" not in _cmds(front)[0]
    assert "status-done" in front
    body = _body_of(card)
    assert [c.endswith("--closeout") for c in _cmds(body)] == [False]
    section = body.split("<h4>Close-out session</h4>", 1)[1]
    assert 'class="jump"' not in section and 'class="cmd"' not in section
