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

from tests.unit.triage_board_fixtures import busy, facts, issue

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
    h = tabs("wave", "Waves", [("2", "Wave 2", "<p>x</p>"), ("none", "No wave", "")], 0)
    for key in ("2", "none"):
        assert f'id="wave-panel-{key}"' in h
        assert f'aria-controls="wave-panel-{key}"' in h
        assert f'id="wave-tab-{key}"' in h
    assert 'role="tabpanel"' in h and 'role="tab"' in h
    assert "fromHash" in TABS_SCRIPT and "hashchange" in TABS_SCRIPT


def test_the_hash_step_selects_the_panel_an_element_is_inside() -> None:
    # the script walks every group's panels: `p === target || p.contains(target)`
    assert "p.contains(target)" in TABS_SCRIPT
    assert "location.hash" in FOLD_SCRIPT and "n.open = true" in FOLD_SCRIPT


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
