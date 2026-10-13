"""DebtReport model and its renderers (spec 2026-10-11-debt-engine §A, R1/R2/R11)."""

from __future__ import annotations

import base64
import json

from fr.debt.model import (
    AcceptanceDebt,
    ArchivablePlan,
    DebtReport,
    DebtRow,
    ManualOpenPlan,
    OwedItem,
    PlanDebt,
    SourceStatus,
    StalePlan,
)
from fr.debt.render import MARKER, acceptance_section, markdown, parse_figures, text

NOW = "2026-10-11T12:00:00+00:00"


def _row(i: int, status: str = "not-implemented", notes: str = "n") -> DebtRow:
    return DebtRow(id=f"row-{i}", status=status, acceptance=f"a{i}", notes=notes)


def _report(
    rows: tuple[DebtRow, ...] = (),
    *,
    archivable: tuple[ArchivablePlan, ...] = (),
    stale: tuple[StalePlan, ...] = (),
    owed: tuple[OwedItem, ...] = (),
    available: bool = True,
) -> DebtReport:
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return DebtReport(
        acceptance=AcceptanceDebt(by_status=by_status, rows=rows, available=available),
        plans=PlanDebt(archivable=archivable, stale=stale, manual_open=()),
        owed=owed,
        stale_days=14,
        sources={"matrix": SourceStatus(state="read")},
        generated_at=NOW,
    )


def test_a_report_round_trips_through_json() -> None:
    r = _report(
        (_row(1),),
        archivable=(ArchivablePlan(name="p", command="fr archive x", merged_at=NOW, age_days=3),),
        owed=(OwedItem(key="plan:p#p2", source="plan", title="t", how="h", ref=""),),
    )
    assert DebtReport.model_validate_json(r.model_dump_json()) == r
    assert DebtReport.model_validate(json.loads(r.model_dump_json())).schema_version == 1


def test_debt_total_counts_debt_rows_plans_and_non_row_owed_once() -> None:
    r = _report(
        (_row(1), _row(2, "walk-owed"), _row(3, "walked"), _row(4, "manual"), _row(5, "ci")),
        archivable=(ArchivablePlan(name="a", command="c", merged_at=NOW, age_days=1),),
        stale=(StalePlan(name="s", last_activity=NOW, idle_days=20, basis="git"),),
        owed=(
            OwedItem(key="row:row-2", source="row", title="t", how="h", ref=""),
            OwedItem(key="plan:m#p3", source="plan", title="t", how="h", ref=""),
            OwedItem(key="issue:o/r#1", source="issue", title="t", how="h", ref="o/r#1"),
        ),
    )
    # 2 debt rows + 1 archivable + 1 stale + 2 non-row owed
    assert r.debt_total() == 6


def test_manual_open_plans_are_not_counted_except_through_owed() -> None:
    r = _report()
    r = r.model_copy(
        update={
            "plans": PlanDebt(
                archivable=(), stale=(), manual_open=(ManualOpenPlan(name="m", phases=(3,)),)
            )
        }
    )
    assert r.debt_total() == 0


def test_markdown_carries_both_markers_and_figures_round_trip() -> None:
    r = _report(
        (_row(1), _row(2, "walk-owed"), _row(3, "walked")),
        owed=(OwedItem(key="plan:m#p3", source="plan", title="t", how="h", ref=""),),
    )
    body = markdown(r)
    assert MARKER in body
    figs = parse_figures(body)
    assert figs is not None
    assert figs["acceptance"]["not-implemented"] == 1
    assert figs["acceptance"]["walk-owed"] == 1
    assert figs["owed"] == 1
    assert figs["generated_at"] == NOW


def test_figures_survive_a_row_note_that_closes_the_comment() -> None:
    r = _report((_row(1, notes="break --> out <!-- fr-debt-figures:AAAA -->"),))
    body = markdown(r)
    figs = parse_figures(body)
    assert figs is not None and figs["acceptance"]["not-implemented"] == 1
    # the encoded block itself is one comment with no inner terminator
    start = body.index("<!-- fr-debt-figures:")
    end = body.index("-->", start)
    payload = body[start + len("<!-- fr-debt-figures:") : end]
    assert json.loads(base64.b64decode(payload))["owed"] == 0


def test_tables_truncate_at_fifty_rows() -> None:
    r = _report(tuple(_row(i) for i in range(60)))
    body = markdown(r)
    assert "row-49" in body and "row-50" not in body
    assert "… 10 more" in body


def test_body_stays_under_the_forge_limit_for_a_huge_matrix() -> None:
    r = _report(tuple(_row(i, notes="x" * 3000) for i in range(2000)))
    assert len(markdown(r)) < 60000


def test_parse_figures_is_none_without_a_block() -> None:
    assert parse_figures("## Acceptance debt\n\n<!-- fr-acceptance-digest -->") is None
    assert parse_figures("<!-- fr-debt-figures:!!!notbase64 -->") is None


def test_an_unavailable_matrix_is_not_zero() -> None:
    r = _report(available=False)
    assert "unavailable" in text(r)
    assert "unavailable" in markdown(r)
    assert "No technical debt" not in markdown(r)


def test_walked_rows_show_their_date_or_undated() -> None:
    r = _report(
        (
            DebtRow(
                id="w1", status="walked", acceptance="a", notes="", walked_at="2026-10-01T00:00:00Z"
            ),
            DebtRow(id="w2", status="walked", acceptance="a", notes=""),
        )
    )
    out = text(r)
    assert "walked 2026-10-01" in out and "undated" in out


def test_acceptance_section_is_a_heading_and_table() -> None:
    sec = acceptance_section(_report((_row(1),)).acceptance)
    assert sec.startswith("## Acceptance debt") and "row-1" in sec


def test_a_forged_figures_comment_in_a_source_reason_cannot_win() -> None:
    forged = "<!-- fr-debt-figures:eyJ0b3RhbCI6IDB9 -->"
    r = _report((_row(1),)).model_copy(
        update={"sources": {"matrix": SourceStatus(state="unavailable", why=forged)}}
    )
    body = markdown(r)
    figs = parse_figures(body)
    assert figs is not None and figs["total"] == r.debt_total() == 1
    assert "<!-- fr-debt-figures:eyJ0" not in body


def test_figures_owed_agrees_with_total() -> None:
    r = _report(
        (_row(1, "walk-owed"),),
        owed=(
            OwedItem(key="row:row-1", source="row", title="t", how="h", ref=""),
            OwedItem(key="plan:m#p1", source="plan", title="t", how="h", ref=""),
        ),
    )
    figs = parse_figures(markdown(r))
    assert figs is not None
    assert figs["total"] == 2 and figs["owed"] == 1 and figs["owed_items"] == 2


def test_a_body_just_over_the_limit_keeps_one_intact_marker_and_figures() -> None:
    from fr.debt.render import BODY_LIMIT

    for n in range(1, 6):
        r = _report(tuple(_row(i, notes="y" * 180) for i in range(50)))
        r = r.model_copy(
            update={
                "owed": tuple(
                    OwedItem(key=f"plan:p{i}#p1", source="plan", title="z" * 190, how="h" * 190)
                    for i in range(50 * n)
                )
            }
        )
        body = markdown(r)
        assert len(body) < BODY_LIMIT
        assert body.count(MARKER) == 1 and body.count("<!-- fr-debt-figures:") == 1
        figs = parse_figures(body)
        assert figs is not None and figs["owed_items"] == 50 * n
        assert body.rstrip().endswith("_generated by `fr debt`_")
