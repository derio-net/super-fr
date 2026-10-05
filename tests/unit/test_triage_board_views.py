"""The board's decision views (wave-driver R16-R20; Test Plan 8 and 13).

Pure render over constructed facts: Since last report, Needs you now, Next up,
the wave tabs and the Closing order, in the order R20 gives, with everything the
board showed before still present. The tab MARKUP is asserted (roles, `hidden`,
roving tabindex, preselection, the no-script fallback); the script's key
handling is asserted from its source, because no browser runs in CI.
"""

from __future__ import annotations

import re

from fr.triage.batch_drive import drive_pass
from fr.triage.model import Facts, Judgements
from fr.triage.render import render, wave_table
from fr.triage.snapshot import diff_snapshots, take_snapshot
from fr.triage.views import (
    drive_snapshot,
    needs_you,
    next_up,
    preselected_wave,
)

from tests.unit.triage_board_fixtures import (
    URL,
    batch,
    busy,
    dispatch,
    facts,
    healthy,
    issue,
    j,
    judgements,
    pr,
)


def _section(page: str, sid: str) -> str:
    m = re.search(rf'<section[^>]*id="{sid}".*?</section>', page, flags=re.S)
    assert m, f"no section {sid}"
    return m.group(0)


def _needs(page: str) -> list[tuple[str, str]]:
    return re.findall(r'data-need="([a-z-]+)" data-ref="([^"]*)"', _section(page, "needs-you-now"))


# -------------------------------------------------------------- the order (R20)


def _order(page: str, *needles: str) -> list[int]:
    return [page.index(n) for n in needles]


def _with_pattern() -> tuple[Facts, Judgements]:
    f, jd = busy()
    pattern = {"title": "Shared cause", "ids": ["widgets#3"], "body": "one `root` cause"}
    return f, Judgements.model_validate(
        {**jd.model_dump(mode="json", by_alias=True), "patterns": [pattern]}
    )


def test_the_board_is_ordered_since_needs_next_waves_then_the_folds() -> None:
    page = render(*_with_pattern())
    at = _order(
        page,
        'class="mast"',
        'id="since-last-report"',
        'id="needs-you-now"',
        'id="next-up"',
        'id="waves"',
        'id="backlog-by-tier"',
        'id="ranked-features"',
        'id="parked"',
        'id="patterns"',
        'id="prs"',
        'id="batches"',
    )
    assert at == sorted(at) and len(set(at)) == len(at)


def test_below_the_waves_every_section_is_a_closed_fold_with_its_count() -> None:
    page = render(*_with_pattern())
    for sid in ("backlog-by-tier", "ranked-features", "parked", "patterns", "prs", "batches"):
        m = re.search(rf'<details id="{sid}" class="fold"([^>]*)>(.*?)</summary>', page, re.S)
        assert m, sid
        assert "open" not in m.group(1), sid
        assert re.search(r'<span class="count">\d+</span>', m.group(2)), sid


def test_the_backlog_has_one_nested_fold_per_tier_and_unranked_with_the_filter_bar_inside() -> None:
    page = render(*busy())
    start = page.index('<details id="backlog-by-tier"')
    end = page.index('id="ranked-features"')
    backlog = page[start:end]
    assert backlog.index('id="q"') < backlog.index('data-tier="unranked"')
    assert 'id="q"' not in page[:start] and 'id="q"' not in page[end:]
    ids = re.findall(r'<details id="(backlog-tier-[^"]+)" class="fold"', backlog)
    assert ids == ["backlog-tier-unranked", "backlog-tier-1", "backlog-tier-2"]
    assert '<details id="backlog-tier-1" class="fold" open' not in backlog


def test_everything_the_board_showed_before_is_still_there() -> None:
    f, jd = busy()
    page = render(f, jd)
    for needle in (
        'class="mast"',  # masthead and its counts
        'id="q"',  # the filter bar
        'id="prs"',  # PRs
        'id="batches"',  # Batches and the planned merge order
        'data-tier="unranked"',  # unranked
        'data-tier="1"',
        'data-tier="2"',
        "Backlog triage",
        "<footer>",
    ):
        assert needle in page, needle
    for key in ("widgets#3", "widgets#9", "widgets#13"):
        assert f'data-key="{key}"' in page, key
    # the pre-existing sections sit BELOW the new decision sections
    assert page.index('id="waves"') < page.index('data-tier="unranked"') < page.index('id="prs"')


# ------------------------------------------------------- since last report (R17)


def test_the_first_render_says_there_is_no_earlier_snapshot() -> None:
    page = render(*busy())
    assert "No earlier snapshot" in _section(page, "since-last-report")


def _changed() -> tuple[Facts, Judgements, str]:
    f, jd = busy()
    before = take_snapshot(f, jd, acceptance={"row-a": "skipped"})
    merged = pr(11, "feat/batch-b-draft", state="MERGED")
    issues = [i.model_dump(mode="json") for i in f.issues]
    for d in issues:
        if d["number"] in (3, 4):
            d.update(state="closed", prs=[merged.copy()])
    issues.append(issue(14))
    f2 = facts(issues)
    after = take_snapshot(f2, jd, acceptance={"row-a": "ci"})
    return f2, jd, render(f2, jd, diff_snapshots(before, after))


def _rows(sect: str) -> list[list[str]]:
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", sect, flags=re.S)[1:]:
        out.append(
            [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        )
    return out


def test_since_last_report_is_a_table_of_transitions() -> None:
    _, _, page = _changed()
    sect = _section(page, "since-last-report")
    heads = re.findall(r"<th(?:\s[^>]*)?>(.*?)</th>", sect)
    assert heads == ["Change", "Item", "Before", "After"]
    rows = _rows(sect)
    assert ["Merged or closed", "widgets#3", "open", "closed"] in rows
    assert ["Merged or closed", "PR example-org/widgets#11", "open", "merged"] in rows
    assert ["Filed", "widgets#14", "", "open"] in rows
    assert ["Batch stage", "b-draft", "pr-open", "merged"] in rows
    assert ["Acceptance row", "row-a", "skipped", "ci"] in rows
    assert any(r[0] == "Figure" and r[1] == "open" for r in rows)
    assert "No earlier snapshot" not in sect and "<ul>" not in sect


def test_a_batch_row_links_to_its_card() -> None:
    _, _, page = _changed()
    sect = _section(page, "since-last-report")
    assert '<a href="#batch-b-draft">b-draft</a>' in sect
    assert sect.count('href="#batch-') == 1


# ---------------------------------------------------------- needs you now (R18)


def test_needs_you_now_lists_each_kind_and_the_unplaced_issues() -> None:
    page = render(*busy())
    got = set(_needs(page))
    assert got == {
        ("ready-pr", "b-draft"),
        ("failing-ci", "c-red"),
        ("stale-dispatch", "widgets#8"),
        ("blocked-batch", "d-blocked"),
        ("post-merge", "a-merged"),
        ("unplaced", "widgets#7"),
        ("unplaced", "widgets#8"),
        ("unplaced", "widgets#9"),
    }


def test_every_need_row_names_and_links_its_pr_issue_or_batch() -> None:
    page = render(*busy())
    rows = re.findall(r'<li class="need".*?</li>', _section(page, "needs-you-now"), flags=re.S)
    assert len(rows) == 8
    for row in rows:
        assert re.search(r'<a href="(https://[^"]+|#batch-[a-z-]+)"', row), row
    ready = next(r for r in rows if 'data-need="ready-pr"' in r)
    assert "https://github.com/example-org/widgets/pull/11" in ready and "PR #11" in ready
    unplaced = next(r for r in rows if 'data-ref="widgets#9"' in r)
    assert "https://github.com/example-org/widgets/issues/9" in unplaced
    assert 'href="#batch-d-blocked"' in next(r for r in rows if 'data-need="blocked-batch"' in r)


def test_a_healthy_board_needs_nothing() -> None:
    page = render(*healthy())
    assert _needs(page) == []
    assert "Nothing needs you now" in _section(page, "needs-you-now")


def test_needs_you_reads_the_same_facts_the_driver_reads() -> None:
    f, jd = busy()
    plan = drive_pass(drive_snapshot(f, jd))
    driver_blocked = {a.batch for a in plan.actions if a.kind == "blocked"}
    driver_failing = {a.batch for a in plan.actions if a.kind == "warn"}
    rows = needs_you(f, jd)
    assert {r.ref for r in rows if r.kind == "blocked-batch"} == driver_blocked == {"d-blocked"}
    assert {r.ref for r in rows if r.kind == "failing-ci"} == driver_failing == {"c-red"}


def test_removing_the_driver_signal_removes_the_row() -> None:
    """The failing-CI row is the driver's `warn`: with green checks it is gone."""
    f, jd = busy()
    green = [i.model_dump(mode="json") for i in f.issues]
    for d in green:
        for p in d["prs"]:
            p["checks"] = {"pass": 3, "fail": 0, "pending": 0}
    f2 = facts(green, config={"example-org/widgets": {"post_merge": ["make", "deploy"]}})
    assert not [r for r in needs_you(f2, jd) if r.kind == "failing-ci"]


def test_a_foreign_pr_on_a_batch_branch_needs_the_operator() -> None:
    """gh#936: the driver reports it and never merges it; the board lists it."""
    fork = pr(40, "feat/batch-x", cross_repo=True, is_draft=True)  # green draft: never "ready it"
    f = facts([issue(1, prs=[fork])], prs=[fork])
    jd = judgements({"widgets#1": j(1)}, [batch("x", [1], wave=1, events=[dispatch("x")])])
    rows = [r for r in needs_you(f, jd) if r.kind == "foreign-pr"]
    assert [(r.ref, r.href) for r in rows] == [("x", f"{URL}/pull/40")]
    assert "opened from a fork" in rows[0].text
    assert ("foreign-pr", "x") in _needs(render(f, jd))
    assert not [r for r in needs_you(f, jd) if r.kind == "ready-pr"]


def _merged_by_hand(**kw: object) -> tuple[Facts, Judgements]:
    merged = pr(10, "feat/batch-old", state="MERGED", merged_at="2026-09-01T09:00:00Z")
    f = facts(
        [issue(1, state="closed", prs=[merged])],
        config={"example-org/widgets": {"post_merge": ["make", "deploy"]}},
    )
    return f, judgements({"widgets#1": j(1)}, [batch("old", [1], events=[dispatch("old")], **kw)])


def test_an_unwaved_old_merged_batch_has_no_post_merge_row() -> None:
    f, jd = _merged_by_hand()
    assert not [r for r in needs_you(f, jd) if r.kind == "post-merge"]


def test_a_waved_merged_batch_gets_the_row_and_says_when_it_applies() -> None:
    f, jd = _merged_by_hand(wave=1)
    rows = [r for r in needs_you(f, jd) if r.kind == "post-merge"]
    assert [r.ref for r in rows] == ["old"]
    assert "it failed, or no driver is running" in rows[0].text


def test_there_is_no_operator_answer_row_because_no_deterministic_signal_exists() -> None:
    """R18's 'waiting on an operator answer' is not in the facts or the driver's
    snapshot (decision p4-operator-answer-not-derivable); a row of that kind must
    never be invented."""
    assert not [r for r in needs_you(*busy()) if r.kind == "operator-answer"]


# -------------------------------------------------------------- next up (R19)


def _free_batches() -> tuple[Facts, Judgements]:
    f = facts([issue(n) for n in range(1, 6)])
    jd = judgements(
        {f"widgets#{n}": j(tier=n, cx=cx) for n, cx in zip(range(1, 6), "XS S M S XS".split())},
        [
            batch("w2-late", [1], wave=2, after=["w1-first"], rationale="after first"),
            batch("w1-first", [2], wave=1),
            batch("w1-second", [3], wave=1, order=2),
            batch("w1-third", [4], wave=1, order=1),
            batch("w2-free", [5], wave=2),
        ],
        tiers=[{"n": n, "title": f"T{n}"} for n in range(1, 6)],
    )
    return f, jd


def test_next_up_is_the_order_a_drive_plan_prints() -> None:
    f, jd = _free_batches()
    plan = drive_pass(drive_snapshot(f, jd, max_inflight=3))
    printed = [a.batch for a in plan.actions if a.kind == "dispatch"]
    rows = next_up(f, jd, max_inflight=3)
    assert [r.ref for r in rows if r.kind == "batch" and not r.waiting] == printed
    assert printed == ["w1-third", "w1-second", "w1-first"]


def test_next_up_carries_tier_size_dependencies_and_the_reason() -> None:
    f, jd = _free_batches()
    rows = {r.ref: r for r in next_up(f, jd, max_inflight=3)}
    first = rows["w1-first"]
    assert (first.tier, first.size, first.deps) == (2, "S", ())
    assert "wave 1" in first.reason
    late = rows["w2-late"]
    assert late.waiting and late.deps == ("w1-first",)
    assert "w1-first" in late.reason
    free = rows["w2-free"]
    assert free.waiting and "in-flight cap" in free.reason


def test_next_up_page_rows_follow_that_order_and_features_follow_in_rank_order() -> None:
    f, jd = busy()
    page = render(f, jd)
    refs = re.findall(r'data-next="([a-z]+)" data-ref="([^"]*)"', _section(page, "next-up"))
    assert refs == [
        ("batch", "e-next"),
        ("feature", "First feature"),
        ("feature", "Second feature"),
    ]
    sect = _section(page, "next-up")
    assert "most value" in sect and "/fr-goal first" in sect


# ----------------------------------------------------------- closing order (R9)


def test_the_closing_order_counts_kinds_and_draws_waves_features_and_parked() -> None:
    page = render(*busy())
    sect = _section(page, "waves")
    counts = dict(re.findall(r'data-kind="([a-z-]+)"><b>(\d+)</b>', sect))
    assert counts == {"defect": "7", "feature": "2", "parked": "1", "unkinded": "1"}
    for header in ("Batch", "Skill", "Issues", "Why", "Size", "Depends on", "Stage"):
        assert f"<th>{header}</th>" in sect, header
    assert "needs z" in sect and "z-cancelled" in sect
    # the ranked features and the parked list are their own folds now, below the waves
    features = re.search(r'<details id="ranked-features".*?</details>', page, re.S)
    assert features and features.group(0).index("First feature") < features.group(0).index(
        "Second feature"
    )
    assert "First feature" not in sect
    parked = re.search(r'<details id="parked".*?</details>', page, re.S)
    assert parked and "widgets#10" in parked.group(0)


def test_a_file_without_kind_renders_the_old_page_plus_empty_closing_order() -> None:
    f = facts([issue(1)])
    jd = judgements({"widgets#1": j()})
    page = render(f, jd)
    assert 'data-kind="unkinded"><b>1</b>' in page
    assert 'data-key="widgets#1"' in page


# -------------------------------------------------------------- wave tabs (R16)


def _tabs(page: str) -> list[dict[str, str]]:
    sect = _section(page, "waves")
    tabs = re.findall(r'<button[^>]*role="tab"[^>]*>', sect)
    return [dict(re.findall(r'([a-z-]+)="([^"]*)"', t)) for t in tabs]


def test_the_wave_tabs_are_an_aria_tablist_with_roving_focus() -> None:
    page = render(*busy())
    sect = _section(page, "waves")
    assert 'role="tablist"' in sect
    tabs = _tabs(page)
    assert [t["data-key"] for t in tabs] == ["1", "2", "3"]
    assert sum(t["aria-selected"] == "true" for t in tabs) == 1
    for t in tabs:
        assert t["tabindex"] == ("0" if t["aria-selected"] == "true" else "-1")
    panels = re.findall(r'<div[^>]*role="tabpanel"[^>]*>', sect)
    assert len(panels) == 3
    for t in tabs:
        assert re.search(rf'id="{t["aria-controls"]}"[^>]*aria-labelledby="{t["id"]}"', sect)


def test_the_most_recent_unmerged_wave_is_preselected() -> None:
    f, jd = busy()
    assert preselected_wave(f, jd) == 3  # e-next is unmerged in wave 3
    selected = next(t for t in _tabs(render(f, jd)) if t["aria-selected"] == "true")
    assert selected["data-key"] == "3"


def test_when_every_batch_has_merged_the_highest_wave_is_preselected() -> None:
    merged = [pr(10, "feat/batch-a", state="MERGED"), pr(11, "feat/batch-b", state="MERGED")]
    f = facts(
        [issue(1, state="closed", prs=[merged[0]]), issue(2, state="closed", prs=[merged[1]])]
    )
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        [
            batch("a", [1], wave=1, events=[dispatch("a")]),
            batch("b", [2], wave=2, events=[dispatch("b")]),
        ],
    )
    assert preselected_wave(f, jd) == 2
    jd2 = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        [
            batch("a", [1], wave=2, events=[dispatch("a")]),
            batch("b", [2], wave=1, events=[dispatch("b")]),
        ],
    )
    assert preselected_wave(f, jd2) == 2


def test_an_earlier_wave_is_preselected_while_it_is_the_one_with_unmerged_work() -> None:
    f, jd = healthy()  # a-merged (wave 1) merged; b-next (wave 2) not
    assert preselected_wave(f, jd) == 2
    pending = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        [
            batch("a-merged", [1], wave=1, events=[dispatch("a-merged")]),
            batch("b-done", [2], wave=2, events=[dispatch("b-done")]),
        ],
    )
    merged = pr(11, "feat/batch-b-done", state="MERGED")
    f2 = facts(
        [issue(1, prs=[pr(10, "feat/batch-a-merged")]), issue(2, state="closed", prs=[merged])]
    )
    assert preselected_wave(f2, pending) == 1


def test_with_scripts_disabled_every_wave_is_shown() -> None:
    sect = _section(render(*busy()), "waves")
    panels = re.findall(r'<div[^>]*role="tabpanel"[^>]*>', sect)
    assert panels and not any(" hidden" in p for p in panels), "no panel is hidden in the markup"
    tablist = re.search(r'<div[^>]*role="tablist"[^>]*>', sect)
    assert tablist is not None and " hidden" in tablist.group(0), (
        "the tab row is inert without a script, so it is hidden until one runs"
    )
    labels = re.findall(
        r'<div[^>]*role="tabpanel"[^>]*>\s*<h3 class="panel-label">([^<]+)</h3>', sect
    )
    tab_texts = re.findall(r'role="tab"[^>]*>([^<]+)</button>', sect)
    assert labels == tab_texts and len(labels) == len(panels), "every pane names its wave"
    assert all(t.startswith("Wave ") or t == "No wave" for t in labels)


def test_with_scripts_enabled_the_label_is_visually_hidden_but_stays_in_the_dom() -> None:
    page = render(*busy())
    script = next(
        s for s in re.findall(r"<script\b[^>]*>(.*?)</script>", page, flags=re.S) if "tablist" in s
    )
    assert 'classList.add("js")' in script, "the script marks the component as live"
    css = re.search(r"<style>(.*?)</style>", page, flags=re.S)
    assert css is not None
    rule = re.search(r"\.tabs\.js [^{]*panel-label\s*\{([^}]*)\}", css.group(1))
    assert rule is not None and "clip" in rule.group(1)
    assert "display: none" not in rule.group(1), "assistive tech still reads it"
    sect = _section(page, "waves")
    assert sect.count('class="panel-label"') == len(re.findall(r'role="tabpanel"', sect))


def test_the_tab_script_hides_panels_with_the_hidden_attribute_and_handles_the_keys() -> None:
    page = render(*busy())
    script = re.findall(r"<script\b[^>]*>(.*?)</script>", page, flags=re.S)
    tabs_script = next(s for s in script if "tablist" in s)
    for token in ("ArrowRight", "ArrowLeft", "Home", "End", "hidden", "tabindex", "aria-selected"):
        assert token in tabs_script, token
    assert len(script) == 1, "one script element: the viewer's and the shared tab script"


def test_the_tab_component_is_one_reusable_function() -> None:
    from fr.triage.components import tabs

    html = tabs("arch", "Views", [("a", "First", "<p>1</p>"), ("b", "Second", "<p>2</p>")], 1)
    assert html.count('role="tab"') == 2 and html.count('role="tabpanel"') == 2
    assert html.index('aria-selected="true"') > html.index("First")
    assert 'id="arch-tab-b"' in html and 'aria-controls="arch-panel-b"' in html


# ------------------------------------------------- the page itself (R12), no patch


def test_the_page_has_a_real_title_and_the_three_theme_variants() -> None:
    page = render(*busy())
    assert re.search(r"<title>[^<]*widgets[^<]*</title>", page)
    css = re.search(r"<style>(.*?)</style>", page, flags=re.S)
    assert css is not None
    css_text = css.group(1)
    assert "prefers-color-scheme: dark" in css_text
    assert ':root[data-theme="dark"]' in css_text and ':root[data-theme="light"]' in css_text
    assert "color-scheme: light dark" in css_text


def test_the_phone_gutter_is_sixteen_pixels() -> None:
    css = re.search(r"<style>(.*?)</style>", render(*busy()), flags=re.S).group(1)  # type: ignore[union-attr]
    phone = re.search(r"@media \(max-width: 4\d\dpx\) \{(.*?)\n\}", css, flags=re.S)
    assert phone is not None
    assert re.search(r"main \{[^}]*padding-left: 16px; padding-right: 16px", phone.group(1))
    assert "padding: 0 10px" not in css


def test_render_stays_deterministic_and_escapes_new_text() -> None:
    f, jd = busy()
    assert render(f, jd) == render(f, jd)
    evil = judgements(
        {"widgets#1": j()},
        [batch("x", [1], wave=1, rationale="<script>alert(1)</script>")],
    )
    page = render(facts([issue(1)]), evil)
    assert "<script>alert(1)</script>" not in page


def test_no_waves_means_no_tabs() -> None:
    f = facts([issue(1)])
    page = render(f, judgements({"widgets#1": j()}))
    assert '<div role="tablist"' not in page
    assert "No waves" in _section(page, "waves")


# ------------------------------------------------- finished waves (triage-pages-goal R8)

CANCEL = {"kind": "cancel", "at": "2026-10-02T10:00:00Z", "reason": "no longer wanted"}
CLOSEOUT = {
    "kind": "closeout",
    "at": "2026-10-03T10:00:00Z",
    "runner": "fake",
    "handle": "h",
    "archived": 12,
}


def _stages(f: Facts, jd: Judgements) -> dict[str, str]:
    from fr.triage.batch import derive_batch_stage

    return {b.id: derive_batch_stage(b, f) for b in jd.batches}


def test_finished_waves_needs_every_batch_terminal() -> None:
    from fr.triage.views import finished_waves

    merged = pr(10, "feat/batch-c", state="MERGED")
    closed = pr(11, "feat/batch-d", state="CLOSED")
    f = facts(
        [
            issue(1),
            issue(2, state="closed", prs=[merged]),
            issue(3, prs=[closed]),
            issue(4, state="closed", prs=[merged]),
            issue(5),
        ]
    )
    jd = judgements(
        {f"widgets#{n}": j() for n in range(1, 6)},
        [
            # wave 1: cancelled + archived-by-closeout
            batch("a", [1], wave=1, events=[dispatch("a"), CANCEL]),
            batch("c", [2], wave=1, events=[dispatch("c"), CLOSEOUT]),
            # wave 2: abandoned (PR closed unmerged) + archived
            batch("d", [3], wave=2, events=[dispatch("d")]),
            batch("e", [4], wave=2, events=[dispatch("e"), CLOSEOUT]),
            # wave 3: a merged-but-unarchived batch holds the wave open
            batch("g", [2], wave=3, events=[dispatch("c")]),
            # no wave: never yields a key
            batch("z", [5], events=[dispatch("z"), CANCEL]),
        ],
    )
    done = finished_waves(jd.batches, _stages(f, jd))
    assert done == frozenset({"1", "2"})


def test_finished_waves_is_the_driver_predicate_re_exported() -> None:
    from fr.triage import batch_drive, views

    assert views.finished_waves is batch_drive.finished_waves


def test_preselected_wave_is_restricted_to_among() -> None:
    f = facts([issue(1), issue(2), issue(3)])
    jd = judgements(
        {f"widgets#{n}": j() for n in (1, 2, 3)},
        [
            batch("a", [1], wave=1, events=[dispatch("a")]),
            batch("b", [2], wave=2, events=[dispatch("b")]),
            batch("c", [3], wave=3, events=[dispatch("c")]),
        ],
    )
    assert preselected_wave(f, jd) == 3
    assert preselected_wave(f, jd, among={"1", "2"}) == 2
    assert preselected_wave(f, jd, among={"1"}) == 1
    assert preselected_wave(f, jd, among=set()) is None


def test_among_finished_keys_picks_the_highest_finished() -> None:
    f = facts([issue(1), issue(2)])
    jd = judgements(
        {f"widgets#{n}": j() for n in (1, 2)},
        [
            batch("a", [1], wave=1, events=[dispatch("a"), CANCEL]),
            batch("b", [2], wave=2, events=[dispatch("b"), CANCEL]),
        ],
    )
    from fr.triage.views import finished_waves

    done = finished_waves(jd.batches, _stages(f, jd))
    assert preselected_wave(f, jd, among=done) == 2


def test_batch_stages_derives_every_batch() -> None:
    from fr.triage.views import batch_stages

    f = facts([issue(1)])
    jd = judgements({"widgets#1": j()}, [batch("a", [1], wave=1, events=[dispatch("a")])])
    assert batch_stages(f, jd) == {"a": "dispatched"}


# ------------------------------------------------------------- the Tier column (R4)


def test_the_wave_table_has_a_tier_column_after_batch() -> None:
    page = render(*busy())
    heads = re.findall(r"<th(?:\s[^>]*)?>(.*?)</th>", _section(page, "waves"))
    assert heads[:8] == [
        "Batch",
        "Tier",
        "Skill",
        "Issues",
        "Why",
        "Size",
        "Depends on",
        "Stage",
    ]


def test_the_tier_is_the_lowest_member_tier_or_a_dash() -> None:
    from fr.triage.views import batch_tier

    f = facts([issue(1), issue(2), issue(3)])
    jd = judgements({"widgets#1": j(2), "widgets#2": j(1)}, [batch("lo", [1, 2], wave=1)])
    assert batch_tier(jd.batches[0].ids, jd.issues) == 1
    assert batch_tier(["widgets#3"], jd.issues) is None
    unjudged = jd.batches[0].model_copy(update={"id": "none", "ids": ["widgets#3"]})
    rows = {r[0]: r[1] for r in _rows(wave_table([*jd.batches, unjudged], f, jd))}
    assert rows == {"lo": "1", "none": "—"}


def test_the_wave_tables_scroll_sideways_instead_of_wrapping_by_the_letter() -> None:
    from fr.triage.components import GRID_CSS

    assert "min-width" in GRID_CSS and "white-space: nowrap" in GRID_CSS
    page = render(*busy())
    assert GRID_CSS in page
    assert 'class="tablewrap"' in _section(page, "waves")
