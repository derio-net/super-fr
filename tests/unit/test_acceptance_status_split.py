"""The `skipped` split (spec 2026-10-11-debt-engine §D, R5, R8): four statuses
replace `skipped`, `DEBT_STATUSES` is the one debt set, and a matrix still
saying `skipped` is refused by name with the way forward."""

from __future__ import annotations

import pytest
from fr.acceptance.check import open_rows
from fr.acceptance.model import (
    DEBT_STATUSES,
    AcceptanceError,
    Matrix,
    Row,
    parse_matrix,
)


def _row(status: str, rid: str = "r") -> Row:
    return Row(id=rid, capability="c", acceptance="a", status=status)  # type: ignore[arg-type]


def test_a_skipped_row_is_refused_by_name_with_the_migrate_command() -> None:
    text = (
        "schema_version: 5\nrows:\n- id: r\n  capability: c\n  acceptance: a\n  status: skipped\n"
    )
    with pytest.raises(AcceptanceError) as e:
        parse_matrix(text)
    assert "skipped" in str(e.value)
    assert "fr migrate artifacts --yes" in str(e.value)


@pytest.mark.parametrize("status", ["unwired", "walk-owed", "walked", "manual"])
def test_each_new_status_parses(status: str) -> None:
    assert _row(status).status == status


def test_debt_statuses_are_exactly_the_four() -> None:
    assert DEBT_STATUSES == frozenset({"not-implemented", "unwired", "walk-owed", "failing"})


def test_open_rows_is_exactly_the_debt_statuses() -> None:
    statuses = [
        "ci",
        "scheduled",
        "unwired",
        "walk-owed",
        "walked",
        "manual",
        "not-implemented",
        "failing",
    ]
    matrix = Matrix(rows=tuple(_row(s, rid=s) for s in statuses))
    assert {r.status for r in open_rows(matrix)} == set(DEBT_STATUSES)
