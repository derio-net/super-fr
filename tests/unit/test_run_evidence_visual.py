"""The `visual` derived evidence (spec 2026-09-28-ui-visual-evidence §C, Test
Plan 3–5).

Part 1 drives the pure checks (`fr.run.visual.owed_rows` / `check_visual`,
checks 1–3); part 2 drives the real `fr run resolve --record` path, with a
Claude Code session tree built from captured records (checks 4–5, the witness
transcript per step, unobserved, refusals).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
from pathlib import Path

import pytest
from fr.acceptance.model import Matrix, Row, Visual
from fr.record.model import VisualEvidence, VisualShot
from fr.run.visual import check_visual, owed_rows

OPENED = _dt.datetime(2026, 9, 28, 10, 0, 0, tzinfo=_dt.UTC)


def _row(rid: str = "ui-row", *, post_merge: bool = False, visual: bool = True) -> Row:
    return Row(
        id=rid,
        capability="c",
        acceptance="a",
        origin=("super-fr:docs/superpowers/specs/s.md#R1",),
        status="ci",
        verify="post-merge" if post_merge else None,
        visual=Visual(states=("accepted",), interactions=("20 cap",)) if visual else None,
    )


def _shot(where: Path, name: str, data: bytes = b"\x89PNG bytes", *, age: float = 0) -> Path:
    path = where / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if age:
        stamp = OPENED.timestamp() - age
        os.utime(path, (stamp, stamp))
    else:
        stamp = OPENED.timestamp() + 5
        os.utime(path, (stamp, stamp))
    return path


def _entry(row: str, *shots: tuple[Path | str, tuple[str, ...]], script: str | None = None):
    return VisualEvidence(
        row=row,
        script=script,
        shots=tuple(VisualShot(path=str(p), shows=shows) for p, shows in shots),
    )


def _check(tmp_path: Path, rows, entries, *, fresh: bool = False, ignored: bool = True):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return check_visual(
        rows,
        entries,
        opened=OPENED,
        fresh_required=fresh,
        repo_root=repo,
        records_dir=repo / "docs/superpowers/runs/r1.records",
        is_ignored=lambda _p: ignored,
    )


def _outside(tmp_path: Path) -> Path:
    return tmp_path / "scratch"


# --- owed rows ---------------------------------------------------------------


def test_owed_rows_are_the_phase_rows_with_visual_and_no_post_merge() -> None:
    matrix = Matrix(
        rows=(_row("a"), _row("b", post_merge=True), _row("c", visual=False), _row("d"))
    )

    assert [r.id for r in owed_rows(matrix, phase_rows=("a", "b", "c"))] == ["a"]


def test_owed_rows_at_deliver_are_the_rows_citing_the_spec() -> None:
    other = _row("x").model_copy(update={"origin": ("super-fr:docs/other.md",)})
    matrix = Matrix(rows=(_row("a"), other, _row("b", post_merge=True)))

    rows = owed_rows(matrix, spec_ref="super-fr:docs/superpowers/specs/s.md")

    assert [r.id for r in rows] == ["a"]


def test_no_owed_row_is_none(tmp_path: Path) -> None:
    result = _check(tmp_path, [], [])

    assert result.problems == ()
    assert result.witness() == "none"


# --- check 1: an entry per row -------------------------------------------------


def test_a_missing_row_entry_is_refused(tmp_path: Path) -> None:
    result = _check(tmp_path, [_row()], [])

    assert any("ui-row" in p and "no `visual` entry" in p for p in result.problems)


# --- check 2: coverage ---------------------------------------------------------


def test_an_uncovered_name_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "a.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted",)))])

    assert any("'20 cap'" in p and "no shot shows" in p for p in result.problems)


def test_an_unknown_name_in_shows_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "a.png")
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap", "acceptd")))]
    )

    assert any("'acceptd'" in p and "declares no such" in p for p in result.problems)


# --- check 3: the files --------------------------------------------------------


def test_a_missing_shot_is_refused(tmp_path: Path) -> None:
    missing = _outside(tmp_path) / "gone.png"
    result = _check(tmp_path, [_row()], [_entry("ui-row", (missing, ("accepted", "20 cap")))])

    assert any("missing or empty" in p for p in result.problems)


def test_a_zero_byte_shot_is_refused(tmp_path: Path) -> None:
    empty = _shot(_outside(tmp_path), "e.png", b"")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (empty, ("accepted", "20 cap")))])

    assert any("missing or empty" in p for p in result.problems)


def test_a_shot_in_the_records_dir_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shot = _shot(repo / "docs/superpowers/runs/r1.records", "s.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert any("records dir" in p for p in result.problems)


def test_a_repo_shot_that_is_not_ignored_is_refused(tmp_path: Path) -> None:
    shot = _shot(tmp_path / "repo" / "shots", "s.png")
    result = _check(
        tmp_path,
        [_row()],
        [_entry("ui-row", ("shots/s.png", ("accepted", "20 cap")))],
        ignored=False,
    )

    assert shot.exists()
    assert any("git-ignored" in p for p in result.problems)


def test_a_repo_shot_that_is_ignored_passes(tmp_path: Path) -> None:
    _shot(tmp_path / "repo" / "shots", "s.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", ("shots/s.png", ("accepted", "20 cap")))])

    assert result.problems == ()


def test_a_non_image_suffix_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.txt")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert any("image suffix" in p for p in result.problems)


def test_a_stale_shot_is_refused_when_freshness_is_required(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=60)
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))], fresh=True
    )

    assert any("predates this unit" in p for p in result.problems)


def test_a_stale_shot_is_accepted_when_freshness_is_not_required(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=60)
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert result.problems == ()


def test_one_second_of_slack_on_freshness(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=0.5)
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))], fresh=True
    )

    assert result.problems == ()


# --- the witness ---------------------------------------------------------------


def test_the_witness_hashes_the_shot_bytes_in_path_order(tmp_path: Path) -> None:
    b = _shot(_outside(tmp_path), "b.png", b"BBB")
    a = _shot(_outside(tmp_path), "a.png", b"AAA")
    second = _row("ui-2")
    result = _check(
        tmp_path,
        [_row(), second],
        [
            _entry("ui-row", (b, ("20 cap",)), (a, ("accepted",))),
            _entry("ui-2", (a, ("accepted", "20 cap"))),
        ],
    )

    assert result.problems == ()
    digest = hashlib.sha256(b"AAABBB").hexdigest()[:12]
    single = hashlib.sha256(b"AAA").hexdigest()[:12]
    assert result.witness() == f"ui-row:2:{digest},ui-2:1:{single}"
    assert result.witness(unobserved=True) == (
        f"ui-row:2:{digest}:unobserved,ui-2:1:{single}:unobserved"
    )


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg", ".webp", ".gif", ".PNG"])
def test_every_image_suffix_is_accepted(tmp_path: Path, suffix: str) -> None:
    shot = _shot(_outside(tmp_path), f"s{suffix}")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert result.problems == ()
