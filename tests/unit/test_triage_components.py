"""The shared fold, page CSS/script and the Linker (spec 2026-11-18-triage-pages-ux R8, R11,
R12, R17; §D, §E, §I). Every input is an in-memory fixture."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from fr.triage import components
from fr.triage.architecture import Subsystems, render_architecture
from fr.triage.components import (
    FOLD_CSS,
    FOLD_SCRIPT,
    PAGE_CSS,
    PAGE_SCRIPT,
    TABS_CSS,
    TABS_SCRIPT,
    Linker,
    batch_href,
    fold,
    tabs,
    wave_href,
)
from fr.triage.fragments import Entry, Resolved
from fr.triage.history import GENERATED as HISTORY_GENERATED
from fr.triage.history import render_history
from fr.triage.kanban import build_board
from fr.triage.kanban_render import render_board
from fr.triage.model import Facts
from fr.triage.origins import Origins, OriginsFacts, render_origins
from fr.triage.render import inline, render_backlog, render_issues

from tests.unit.triage_board_fixtures import busy, facts, issue, j, judgements

AT = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)

# ------------------------------------------------------------------------- the fold


def test_a_fold_renders_its_summary_with_heading_and_count() -> None:
    h = fold("needs", "Needs <you>", 3, "<p>b</p>", open_=True, heading="h2")
    assert h.startswith('<details id="needs" class="fold" open>')
    assert '<summary><h2>Needs &lt;you&gt;</h2> <span class="count">3</span></summary>' in h
    assert h.endswith("<p>b</p></details>")


def test_a_fold_is_closed_unless_it_says_open_and_a_count_is_optional() -> None:
    h = fold("x", "T", None, "")
    assert h == '<details id="x" class="fold"><summary>T</summary></details>'
    assert " open" not in h.split(">")[0]


def test_a_fold_refuses_a_heading_that_is_not_a_heading() -> None:
    with pytest.raises(ValueError):
        fold("x", "T", None, "", heading="script")


def test_collapsed_is_gone() -> None:
    assert not hasattr(components, "collapsed")


def test_page_css_and_script_carry_the_tab_and_fold_pieces() -> None:
    assert TABS_CSS in PAGE_CSS and FOLD_CSS in PAGE_CSS
    assert TABS_SCRIPT in PAGE_SCRIPT and FOLD_SCRIPT in PAGE_SCRIPT
    assert PAGE_SCRIPT.index(TABS_SCRIPT) < PAGE_SCRIPT.index(FOLD_SCRIPT)  # tab, then fold


def _every_page() -> dict[str, str]:
    f, jd = busy()
    resolved = Resolved(order=[Entry(g) for g in HISTORY_GENERATED])
    return {
        "backlog": render_backlog(f, jd, rendered_at=AT),
        "issues": render_issues(f, jd, rendered_at=AT),
        "history": render_history(f, jd, snapshots=[], resolved=resolved),
        "architecture": render_architecture(
            f, jd, subsystems=Subsystems(), measured={}, resolved=Resolved(order=[])
        ),
        "origins": render_origins(
            OriginsFacts(scope=f.scope, since="2026-01-01", collected_at=f.collected_at, issues=[]),
            Origins(),
        ),
    }


@pytest.mark.parametrize("name", ["backlog", "issues", "history", "architecture", "origins"])
def test_every_renderer_includes_the_page_css_and_script(name: str) -> None:
    page = _every_page()[name]
    assert PAGE_CSS in page and PAGE_SCRIPT in page


def test_the_batches_page_includes_the_page_css_and_script() -> None:
    f, jd = busy()
    page = render_board(
        build_board(f, jd, {}), scope_args=["--repo", "example-org/widgets"],
        rendered_at=AT, refresh=0, notes=[],
    )  # fmt: skip
    assert PAGE_CSS in page and PAGE_SCRIPT in page


# --------------------------------------------------------------- the tabs contract


def test_tabs_markup_has_the_ids_the_hash_script_relies_on() -> None:
    h = tabs("wave", "Waves", [("2", "Wave 2", "<p>x</p>"), ("none", "No wave", "")], 1)
    for key in ("2", "none"):
        assert f'id="wave-panel-{key}"' in h
        assert f'aria-controls="wave-panel-{key}"' in h
        assert f'id="wave-tab-{key}"' in h
    # the default tab is the selected one and the only one in the tab order
    assert re.search(r'id="wave-tab-none"[^>]*aria-selected="true"[^>]*tabindex="0"', h)
    assert re.search(r'id="wave-tab-2"[^>]*aria-selected="false"[^>]*tabindex="-1"', h)
    # with scripts off every panel shows and the tab row does not
    assert '<div role="tablist" aria-label="Waves" hidden>' in h
    assert h.count("hidden") == 1


def test_every_tab_of_a_rendered_page_controls_a_panel_a_hash_can_name() -> None:
    from tests.unit.triage_board_fixtures import id_ancestors

    for name, page in _every_page().items():
        ids = id_ancestors(page)
        for target in re.findall(r'role="tab"[^>]*aria-controls="([^"]+)"', page):
            assert target in ids, (name, target)
    backlog = _every_page()["backlog"]
    ids = id_ancestors(backlog)
    assert "wave-panel-1" in ids and "wave-tab-1" in ids
    # a link to a panel (backlog.html#wave-panel-<k>) names an element that exists
    for href in re.findall(r'href="backlog\.html#(wave-panel-[^"]+)"', backlog):
        assert href in ids, href


def test_the_fold_targets_a_hash_can_reach_sit_inside_their_details() -> None:
    from tests.unit.triage_board_fixtures import id_ancestors

    page = _every_page()["backlog"]
    ids = id_ancestors(page)
    folds = [i for i, chain in ids.items() if i in {
        "since-last-report", "needs-you-now", "next-up", "waves", "batches"
    }]  # fmt: skip
    assert len(folds) == 5
    for card in re.findall(r'<details class="batch"[^>]*\bid="(batch-[^"]+)"', page):
        assert ("details", "batches") in ids[card], card  # a card link opens the Batches fold
    for panel in re.findall(r'role="tabpanel" id="(wave-panel-[^"]+)"', page):
        assert ("details", "waves") in ids[panel], panel  # a wave link opens the Waves fold
    issues = id_ancestors(render_issues(*busy(), rendered_at=AT))
    for row in [i for i in issues if i.startswith("backlog-tier-")]:
        assert ("details", "backlog-by-tier") in issues[row], row


# --------------------------------------------------------------------- the Linker


def _linked() -> tuple[Facts, Linker]:
    f = facts([issue(12), issue(13), issue(14)])
    return f, Linker.from_facts(f)


def test_a_known_key_links_to_its_own_url() -> None:
    f, linker = _linked()
    out = inline("see example-org/widgets#12", linker)
    assert (
        '<a href="https://github.com/example-org/widgets/issues/12" rel="noopener noreferrer">'
        "example-org/widgets#12</a>" in out
    )


def test_qualified_and_bare_references_link_in_a_single_repo_scope() -> None:
    _, linker = _linked()
    out = inline("see example-org/widgets#12 and #13", linker)
    assert out.count("<a ") == 2
    assert 'href="https://github.com/example-org/widgets/issues/13"' in out


def test_only_qualified_references_link_in_an_org_scope() -> None:
    f = facts([issue(12), issue(13)], kind="org", repos=["example-org/widgets"])
    out = inline("see example-org/widgets#12 and #13", Linker.from_facts(f))
    assert out.count("<a ") == 1
    assert "#13" in out and 'issues/13"' not in out


def test_an_unknown_number_links_to_issues_on_github_and_stays_text_elsewhere() -> None:
    _, linker = _linked()
    assert 'href="https://github.com/example-org/widgets/issues/99"' in inline("#99", linker)
    gl = Linker(
        {"corp/app#1": "https://git.example.com/corp/app/-/issues/1"},
        {"corp/app": "https://git.example.com/corp/app"},
        None,
    )
    out = inline("corp/app#1 and corp/app#2", gl)
    assert (
        out.count("<a ") == 1
        and "corp/app#2" in out
        and 'href="https://git.example.com/corp/app/-/issues/1"' in out
    )


def test_text_in_backticks_is_never_linked() -> None:
    _, linker = _linked()
    out = inline("`#12` and **`#13`** and **#14**", linker)
    assert "<code>#12</code>" in out and "<code>#13</code>" in out
    assert out.count("<a ") == 1  # only the bold #14, outside code
    assert "<strong><a " in out


def test_prose_cannot_make_an_href_or_inject_markup() -> None:
    _, linker = _linked()
    out = inline('<script>x</script> "#12" a/b#1"onmouseover="x', linker)
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert out.count("<a ") == 1  # `#12` only; a/b is unknown and not github-based
    for href in re.findall(r'href="([^"]*)"', out):
        assert href == "https://github.com/example-org/widgets/issues/12"
    assert 'onmouseover="x' not in out.replace("&quot;onmouseover=&quot;x", "")


def test_an_entity_and_a_word_inside_text_are_not_references() -> None:
    _, linker = _linked()
    assert "<a " not in inline("it's fine, abc#12 and 5#12 and ##12", linker)
    assert "<a " not in inline("a path foo/bar/baz#12", linker)


def test_without_a_linker_nothing_links() -> None:
    assert "<a " not in inline("example-org/widgets#12 and #13")


def test_a_non_https_url_is_never_kept() -> None:
    f = facts([issue(1, url="javascript:alert(1)")])
    linker = Linker.from_facts(f)
    assert "<a " not in inline("example-org/widgets#1", linker)


def test_wave_and_batch_targets() -> None:
    assert wave_href("2", False) == "backlog.html#wave-panel-2"
    assert wave_href("2", True) == "history.html#history-wave-panel-2"
    assert batch_href("a-b") == "backlog.html#batch-a-b"
    assert batch_href("a b") == "backlog.html#batch-a%20b"


def test_the_linker_is_built_from_every_item_the_inputs_hold() -> None:
    f, jd = busy()
    linker = Linker.from_facts(f)
    assert linker.single == "example-org/widgets"
    assert (
        linker.href("example-org/widgets", 11) == "https://github.com/example-org/widgets/pull/11"
    )
    assert (
        linker.href("Example-Org/Widgets", 3) == "https://github.com/example-org/widgets/issues/3"
    )
    assert jd.batches


def test_the_linker_is_built_from_the_issues_and_prs_origins_facts_hold() -> None:
    from fr.triage.origins import ClosingPr, MergedPr, OriginIssue, OriginsFacts

    issue = OriginIssue(
        key="widgets#1", repo="example-org/widgets", number=1, title="t",
        url="https://github.com/example-org/widgets/issues/1", created_at="2026-09-01T00:00:00Z",
        state="closed",
        closing_prs=[ClosingPr(repo="example-org/widgets", number=7, title="c",
                               url="https://github.com/example-org/widgets/pull/7")],
    )  # fmt: skip
    bad = OriginIssue(
        key="other#2", repo="x/other", number=2, title="t", url="http://insecure.test/other/2",
        created_at="2026-09-01T00:00:00Z", state="open",
    )  # fmt: skip
    pr = MergedPr(repo="example-org/widgets", number=9, title="p",
                  url="https://git.example.test/example-org/widgets/pull/9",
                  merged_at="2026-09-02T00:00:00Z")  # fmt: skip
    facts = OriginsFacts(
        scope="example-org/widgets", since="2026-09-01", collected_at="2026-09-03T00:00:00Z",
        issues=[issue, bad], prs=[pr],
    )  # fmt: skip
    linker = Linker.from_origins(facts)
    assert linker.single == "example-org/widgets"
    assert linker.href("example-org/widgets", 7) == "https://github.com/example-org/widgets/pull/7"
    assert (
        linker.href("example-org/widgets", 9)
        == "https://git.example.test/example-org/widgets/pull/9"
    )
    assert (
        linker.href("example-org/widgets", 50) == "https://github.com/example-org/widgets/issues/50"
    )
    assert linker.href("x/other", 2) is None  # an http url is never kept
    # a group or an org scope is not a single repo
    group = facts.model_copy(update={"scope": "a/b,c/d"})
    assert Linker.from_origins(group).single is None
    assert Linker.from_origins(facts.model_copy(update={"scope": "example-org"})).single is None


# ------------------------------------------------ issue keys in lists link (review p2-r1)


def test_a_known_key_renders_as_a_link_and_an_unknown_one_as_text() -> None:
    _, linker = _linked()
    assert linker.key_link("widgets#12") == (
        '<a href="https://github.com/example-org/widgets/issues/12" '
        'rel="noopener noreferrer">widgets#12</a>'
    )
    assert linker.key_link("widgets#99") == "widgets#99"
    assert linker.key_links(["widgets#12", "widgets#99"]).count("<a ") == 1
    assert linker.key_links([]) == ""


def test_a_key_link_never_takes_a_non_https_url_and_escapes_the_text() -> None:
    f = facts([issue(1, url="javascript:alert(1)")])
    linker = Linker.from_facts(f)
    assert linker.key_link("widgets#1") == "widgets#1"
    assert "&lt;b&gt;" in linker.key_link("<b>")


def test_the_lists_that_name_issues_link_them() -> None:
    f, jd = busy()
    waves = render_backlog(f, jd, rendered_at=AT)
    href = 'href="https://github.com/example-org/widgets/issues/6"'
    row = re.search(r'<tr data-batch="d-blocked".*?</tr>', waves, re.S)
    assert row and href in row.group(0)  # the wave table's Issues column
    card = re.search(r'<details class="batch" data-batch="e-next".*?</details>', waves, re.S)
    assert card and 'issues/13"' in card.group(0)  # the batch card's members
    issues = render_issues(f, jd, rendered_at=AT)
    feature = re.search(r'<tr data-feature="First feature".*?</tr>', issues, re.S)
    assert feature and ">widgets#11</a>" in feature.group(0)  # the feature's ids


def test_a_pattern_lists_its_issues_as_links() -> None:
    f = facts([issue(1), issue(2)])
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        patterns=[{"title": "P", "ids": ["widgets#1", "widgets#2"], "body": "b"}],
    )
    page = render_issues(f, jd, rendered_at=AT)
    pat = re.search(r"<article><h3>P</h3>.*?</article>", page, re.S)
    assert pat and pat.group(0).count('<a href="https://github.com/') == 2


def test_the_history_wave_table_links_its_issues_too() -> None:
    from tests.unit.test_triage_history import _finished, _page

    page = _page(*_finished())
    sect = page[page.index('id="finished-waves"') :]
    assert 'href="https://github.com/example-org/widgets/issues/1"' in sect


# ------------------------------------------- Depends on links to the cards (review p2-r2)


def test_a_wave_tables_depends_on_links_each_batch_to_its_card() -> None:
    f, jd = busy()
    page = render_backlog(f, jd, rendered_at=AT)
    row = re.search(r'<tr data-batch="d-blocked".*?</tr>', page, re.S)
    assert row
    cell = re.search(r'data-label="Depends on">(.*?)</td>', row.group(0), re.S)
    assert cell and cell.group(1) == '<a href="backlog.html#batch-z-cancelled">z-cancelled</a>'
    none = re.search(r'<tr data-batch="e-next".*?</tr>', page, re.S)
    assert none and 'data-label="Depends on">-</td>' in none.group(0)


def test_an_escaped_literal_entity_is_not_a_reference() -> None:
    _, linker = _linked()
    out = inline("a literal &#12; and &#x27; text", linker)
    assert "<a " not in out
    assert "&amp;#12;" in out
    # the reference next to it still links
    assert inline("&#12; but #12", linker).count("<a ") == 1
