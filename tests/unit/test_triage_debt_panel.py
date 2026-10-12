"""The Debt panel and snapshot schema 2 (debt-engine spec §C, R15)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fr.triage.render import render
from fr.triage.snapshot import (
    Snapshot,
    diff_snapshots,
    previous_snapshot,
    store_snapshot,
    take_snapshot,
)

from tests.unit.triage_board_fixtures import facts, issue, judgements
from tests.unit.triage_debt_fixtures import LEGACY, body, digest, figures


def _page(issues, since=None):
    return render(facts(issues), judgements({}), since)


def test_one_collapsed_section_with_status_categories_and_owed() -> None:
    page = _page([digest(1, figures())])

    assert 'id="debt"' in page
    assert page.count('class="fold"') >= 1
    sect = page[page.index('id="debt"') :]
    assert "<details" in sect and "open" not in sect.split("<summary>")[0].split("<details")[-1]
    assert "not-implemented" in sect and "30" in sect
    assert "archivable" in sect and "stale" in sect
    assert "owed" in sect.lower()


def test_repo_without_a_report_and_legacy_digest_states() -> None:
    none = _page([issue(1)])
    legacy = _page([digest(1, None, marker=LEGACY)])

    assert "no report" in none
    assert "legacy digest — no figures" in legacy
    assert "no report" not in legacy


def test_trend_against_the_previous_snapshot() -> None:
    old = facts([digest(1, figures(28))])
    new = facts([digest(1, figures(30))])
    a = take_snapshot(old, judgements({}), acceptance=None)
    b = take_snapshot(new, judgements({}), acceptance=None)

    page = render(new, judgements({}), diff_snapshots(a, b))

    assert "not-implemented 28 → 30" in page


def test_no_trend_without_a_previous_snapshot() -> None:
    page = _page([digest(1, figures(30))])

    assert (
        "→"
        not in page[page.index('id="debt"') : page.index('id="debt"') + 3000].split("</section>")[0]
    )


def test_hostile_text_is_escaped() -> None:
    f = facts(
        [
            issue(
                1,
                title="<script>alert(1)</script>",
                body=body(figures(generated_at="<img onerror=x>")),
            )
        ]
    )

    page = render(f, judgements({}))

    assert "<img onerror" not in page
    assert "<script>alert(1)" not in page


def test_snapshot_v2_stores_debt_and_v1_reads_as_no_trend(tmp_path: Path) -> None:
    f = facts([digest(1, figures())])
    snap = take_snapshot(f, judgements({}), acceptance=None)
    assert snap.schema_version == 2
    assert snap.debt is not None and snap.debt["example-org/widgets"]["acceptance"]["ci"] == 40
    v1 = Snapshot.model_validate({**snap.model_dump(exclude={"debt"}), "schema_version": 1})
    assert v1.debt is None

    d = diff_snapshots(v1, snap)

    assert d is not None and d.debt_before is None
    page = render(f, judgements({}), d)
    assert "predates" in page  # the panel notes the split when the previous snapshot is schema 1


def test_a_stored_v1_file_still_reads(tmp_path: Path) -> None:
    f = facts([issue(1)])
    snap = take_snapshot(f, judgements({}), acceptance=None)
    v1 = Snapshot.model_validate({**snap.model_dump(exclude={"debt"}), "schema_version": 1})
    store_snapshot(tmp_path, v1, datetime(2026, 10, 1, tzinfo=UTC))

    assert previous_snapshot(tmp_path, snap) == v1


def test_skipped_to_new_statuses_is_noted() -> None:
    old = facts([digest(1, figures(acceptance={"skipped": 5, "ci": 2}))])
    new = facts([digest(1, figures(acceptance={"walk-owed": 5, "ci": 2}))])
    a = take_snapshot(old, judgements({}), acceptance=None)
    b = take_snapshot(new, judgements({}), acceptance=None)

    page = render(new, judgements({}), diff_snapshots(a, b))

    assert "status split" in page
    assert "walk-owed 0 → 5" in page


def _panel(page: str) -> str:
    return page[page.index('id="debt"') :]


def test_only_debt_statuses_are_debt() -> None:
    acc = {
        "ci": 40,
        "scheduled": 7,
        "not-implemented": 4,
        "unwired": 1,
        "walk-owed": 2,
        "failing": 1,
        "walked": 5,
        "manual": 3,
    }
    line = _panel(_page([digest(1, figures(acceptance=acc))]))
    debt = line[
        line.index("debt-acceptance") : line.index("</span>", line.index("debt-acceptance"))
    ]

    for s in ("not-implemented 4", "unwired 1", "walk-owed 2", "failing 1"):
        assert s in debt
    for s in ("ci", "scheduled", "walked", "manual"):
        assert s not in debt
    listed = line[line.index("debt-listed") : line.index("</span>", line.index("debt-listed"))]
    assert "walked 5" in listed and "manual 3" in listed and "ci" not in listed


def test_the_badge_is_each_repos_own_total_and_agrees_with_fr_debt() -> None:
    from fr.debt.model import AcceptanceDebt, ArchivablePlan, DebtReport, PlanDebt
    from fr.debt.render import markdown

    report = DebtReport(
        acceptance=AcceptanceDebt(by_status={"not-implemented": 4, "ci": 9}),
        plans=PlanDebt(archivable=(ArchivablePlan(name="p", command="c"),)),
        generated_at="2026-10-11T06:00:00+00:00",
    )
    one = {**digest(1, None), "body": markdown(report)}
    two = digest(
        2,
        figures(
            acceptance={"not-implemented": 11},
            plans={"archivable": 0, "stale": 0, "manual_open": 0},
            owed=0,
        ),
        repo="example-org/gadgets",
    )
    f = facts([one, two], repos=["example-org/widgets", "example-org/gadgets"])

    page = render(f, judgements({}))

    w = _panel(page).split('id="debt-example-org-gadgets"')
    assert f'<span class="count">{report.debt_total()}</span>' in w[0]
    assert report.debt_total() == 5
    assert '<span class="count">11</span>' in w[1]


def test_an_untrusted_digest_is_named_and_its_figures_never_shown() -> None:
    page = _page([digest(4, figures(not_implemented=999), author="stranger")])

    sect = _panel(page)
    assert "untrusted digest ignored (#4)" in sect
    assert "999" not in sect and "no report" in sect


def test_the_oldest_trusted_digest_wins() -> None:
    page = _page(
        [
            digest(9, figures(not_implemented=111)),
            digest(3, figures(not_implemented=22)),
            digest(1, figures(not_implemented=333), author="stranger"),
        ]
    )

    sect = _panel(page)
    assert "not-implemented 22" in sect and "111" not in sect and "333" not in sect
    assert "untrusted digest ignored (#1)" in sect


def _line(sect: str, cls: str) -> str:
    start = sect.index(f'class="{cls}"')
    return sect[sect.index(">", start) + 1 : sect.index("</span>", start)]


def test_a_digest_without_a_matrix_is_not_a_false_zero() -> None:
    page = _page([digest(1, figures(acceptance={}, acceptance_available=False))])

    sect = _panel(page)
    assert "Acceptance: matrix unavailable" in sect
    assert "Acceptance debt: " not in sect


def test_manual_open_is_listed_not_plan_debt_and_the_badge_is_the_visible_sum() -> None:
    import re

    page = _page(
        [
            digest(
                1,
                figures(
                    4,
                    acceptance={"not-implemented": 4, "walk-owed": 2},
                    plans={"archivable": 2, "stale": 1, "manual_open": 5},
                    owed=3,
                ),
            )
        ]
    )

    sect = _panel(page)
    assert "manual_open" not in _line(sect, "debt-plans")
    assert "manual phases open 5 (counted under Owed)" in _line(sect, "debt-listed")
    visible = sum(
        int(n)
        for cls in ("debt-acceptance", "debt-plans", "debt-owed")
        for n in re.findall(r"(?<!→ )\b(\d+)\b(?!\s*→)", _line(sect, cls))
    )
    badge = int(re.search(r'<span class="count">(\d+)</span>', sect).group(1))
    assert badge == visible == 12


def test_schema_8_facts_without_authors_render_a_digest_as_untrusted() -> None:
    import json

    from fr.triage.model import Facts

    raw = facts([digest(1, figures(999))]).to_json()
    raw["schema"] = 8
    for i in raw["issues"]:
        del i["author"]
    old = Facts.model_validate(json.loads(json.dumps(raw)))

    sect = _panel(render(old, judgements({})))

    assert "untrusted digest ignored (#1)" in sect and "999" not in sect
