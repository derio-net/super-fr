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
from tests.unit.triage_debt_fixtures import LEGACY, body, figures


def _page(issues, since=None):
    return render(facts(issues), judgements({}), since)


def test_one_collapsed_section_with_status_categories_and_owed() -> None:
    page = _page([issue(1, body=body(figures()))])

    assert 'id="debt"' in page
    assert page.count('class="fold"') >= 1
    sect = page[page.index('id="debt"') :]
    assert "<details" in sect and "open" not in sect.split("<summary>")[0].split("<details")[-1]
    assert "not-implemented" in sect and "30" in sect
    assert "archivable" in sect and "stale" in sect
    assert "owed" in sect.lower()


def test_repo_without_a_report_and_legacy_digest_states() -> None:
    none = _page([issue(1)])
    legacy = _page([issue(1, body=body(None, LEGACY))])

    assert "no report" in none
    assert "legacy digest — no figures" in legacy
    assert "no report" not in legacy


def test_trend_against_the_previous_snapshot() -> None:
    old = facts([issue(1, body=body(figures(28)))])
    new = facts([issue(1, body=body(figures(30)))])
    a = take_snapshot(old, judgements({}), acceptance=None)
    b = take_snapshot(new, judgements({}), acceptance=None)

    page = render(new, judgements({}), diff_snapshots(a, b))

    assert "not-implemented 28 → 30" in page


def test_no_trend_without_a_previous_snapshot() -> None:
    page = _page([issue(1, body=body(figures(30)))])

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
    f = facts([issue(1, body=body(figures()))])
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
    old = facts([issue(1, body=body(figures(acceptance={"skipped": 5, "ci": 2})))])
    new = facts([issue(1, body=body(figures(acceptance={"walk-owed": 5, "ci": 2})))])
    a = take_snapshot(old, judgements({}), acceptance=None)
    b = take_snapshot(new, judgements({}), acceptance=None)

    page = render(new, judgements({}), diff_snapshots(a, b))

    assert "skipped 5 → 0" in page
    assert "status split" in page
    assert "walk-owed 0 → 5" in page
