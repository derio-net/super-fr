"""The `local` acceptance status (spec 2026-11-14-acceptance-local-status)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_the_module_imports() -> None:
    import fr.acceptance.local as local

    assert "2026-11-14-acceptance-local-status" in (local.__doc__ or "")


# --- Task 2: the status, LocalStamp and the fold's stamp rules (R1, R5, §A) -------------

STAMP = {
    "at": "2026-11-14",
    "tree": "a" * 40,
    "log": "/tmp/suite.log",
    "files": {"tests/test_x.py": "b" * 40},
}


def _row(**over: object):
    from fr.acceptance.model import Row

    data: dict[str, object] = {
        "id": "r1",
        "capability": "widgets",
        "acceptance": "it works",
        "levels": {"unit": ["super-fr:tests/test_x.py#test_y"]},
        "status": "local",
    }
    data.update(over)
    return Row.model_validate(data)


def _set_status(status: str, **over: object):
    from fr.acceptance.fragment import SetStatus

    data: dict[str, object] = {
        "op": "set-status",
        "row": "r1",
        "base": 0,
        "why": "moved",
        "status": status,
        "notes": "n",
    }
    data.update(over)
    return SetStatus.model_validate(data)


def test_local_is_a_listed_status_and_never_debt() -> None:
    from fr.acceptance.model import DEBT_STATUSES, LISTED_STATUSES, is_debt

    assert _row().status == "local"
    assert "local" in LISTED_STATUSES
    assert "local" not in DEBT_STATUSES
    assert not is_debt("local")


def test_local_stamp_is_closed_and_needs_files() -> None:
    from fr.acceptance.model import LocalStamp

    assert LocalStamp.model_validate(STAMP).files == STAMP["files"]
    with pytest.raises(ValidationError):
        LocalStamp.model_validate({**STAMP, "extra": 1})
    with pytest.raises(ValidationError):
        LocalStamp.model_validate({**STAMP, "files": {}})
    for key in ("at", "tree", "log", "files"):
        with pytest.raises(ValidationError):
            LocalStamp.model_validate({k: v for k, v in STAMP.items() if k != key})


def test_row_and_set_status_carry_a_stamp() -> None:
    assert _row(local=STAMP).local is not None
    assert _row().local is None
    assert _set_status("local", local=STAMP).local is not None


def test_set_status_to_local_with_a_stamp_puts_it_on_the_row() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(status="unwired"), _set_status("local", local=STAMP))
    assert out.status == "local"
    assert out.local is not None and out.local.tree == "a" * 40


def test_set_status_to_local_without_a_stamp_clears_an_older_one() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("local"))
    assert out.status == "local"
    assert out.local is None


def test_set_status_to_another_status_drops_the_stamp() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("ci"))
    assert out.status == "ci"
    assert out.local is None


def test_level_amendments_keep_the_stamp() -> None:
    from fr.acceptance.fold import apply_amendment
    from fr.acceptance.fragment import AddLevel, DropLevel

    row = _row(local=STAMP)
    add = AddLevel(op="add-level", row="r1", base=0, why="w", level="unit", ref="super-fr:t.py")
    drop = DropLevel(
        op="drop-level", row="r1", base=0, why="w", level="unit", ref="super-fr:t.py"
    )
    assert apply_amendment(row, add).local == row.local
    assert apply_amendment(row, drop).local == row.local
