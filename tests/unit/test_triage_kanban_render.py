"""The board page (spec 2026-10-05 §D; R1, R3, R4, R5, R10, R14, R15).

Pure render over `triage_kanban_fixtures.world()`: no browser, no clock, no forge.
"""

from __future__ import annotations

import html
import re
import shlex
from datetime import UTC, datetime
from pathlib import Path

from fr.triage import kanban_render
from fr.triage.components import GUTTER_CSS, TOKENS_CSS
from fr.triage.kanban import Board, RunSignal, build_board
from fr.triage.kanban_render import CSS, SCRIPT, render_board

from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements
from tests.unit.triage_fixtures import forbidden_imports
from tests.unit.triage_kanban_fixtures import HOSTILE, world

AT = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)
SCOPE = ["--repo", "example-org/widgets"]


def _board(**kw: object) -> tuple[Board, list[str]]:
    run_signals = kw.pop("run_signals", {})
    f, jd, statuses, notes = world(**kw)  # type: ignore[arg-type]
    return build_board(f, jd, statuses, run_signals=run_signals), notes  # type: ignore[arg-type]


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


def test_nine_columns_with_their_counts_in_order() -> None:
    page = _page()
    heads = re.findall(r'<h2>([^<]+) <span class="count">(\d+)</span></h2>', page)
    # The fixture's partial batch is owed its close-out: Partial, not Done (gh#985).
    assert heads == [
        ("Proposed", "2"), ("Waiting", "2"), ("Running", "2"),
        ("Needs you · start", "1"), ("PR open", "3"), ("Needs you · review", "1"),
        ("Closing out", "2"), ("Partial", "1"), ("Done", "3"),
    ]  # fmt: skip


def test_both_human_columns_render_counts_classes_reasons_and_existing_controls() -> None:
    page = _page(
        run_signals={
            "r-run": RunSignal("start", "needs you: operator gate"),
            "o-draft": RunSignal("review", "needs you: completed draft awaiting review"),
        }
    )
    assert 'class="col attention start" data-column="needs-you-start"' in page
    assert 'class="col attention review" data-column="needs-you-review"' in page
    early = _card(page, "r-run")
    review = _card(page, "o-draft")
    assert "operator gate" in early and "completed draft" in review
    assert "<details" in early and 'class="jump"' in early and "data-command=" in early
    assert "&lt;" not in _script(page)


def test_the_wide_grid_has_one_track_per_column() -> None:
    from fr.triage.kanban import COLUMNS
    from fr.triage.kanban_render import CSS

    assert f".board {{ display: grid; grid-template-columns: repeat({len(COLUMNS)}," in CSS


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
    assert card.index("dispatch") < card.index("post_merge") < card.index("closeout")


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
    assert hand.count('class="jump"') == 1  # the batch's own session only
    assert "closeout" not in "".join(re.findall(r'data-command="([^"]*)"', hand))
    sess = _card(page, "c-session")
    assert sess.count('class="jump"') == 2  # the batch's and the close-out's


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
    assert commands[0] == expected
    assert commands[-1] == expected + " --closeout"
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


def test_a_hostile_human_lane_reason_and_title_are_escaped() -> None:
    page = _page(hostile=True, run_signals={"r-run": RunSignal("start", HOSTILE)})
    assert HOSTILE not in page and html.escape(HOSTILE, quote=True) in page
    assert "alert" not in _script(page)
    assert '<details class="card needs-you" id="card-r-run"' in page


def test_non_https_urls_are_not_linked() -> None:
    board, _ = _board()
    card = next(c for col in board.columns for c in col.cards if c.batch.id == "r-run")
    evil = card.members[0].__class__("k#1", "t", "javascript:alert(1)", "backlog")
    assert kanban_render._member(evil).count("href") == 0  # type: ignore[attr-defined]


def test_the_script_element_is_the_module_constant() -> None:
    assert _script(_page()) == SCRIPT
    assert _script(_page(hostile=True)) == SCRIPT


def test_refresh_reaches_the_script_as_a_body_attribute() -> None:
    assert '<body data-refresh="30">' in _page()
    assert '<body data-refresh="0">' in _page(refresh=0)
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
    assert ".col.attention" in CSS


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
