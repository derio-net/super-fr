"""`walked` means proven by a passing walk (spec 2026-10-11-debt-engine R5, p1-r2):
`set-status --status walked` refuses a row with no passing walk unless the same
command records one, the record engine refuses the same, and `fr acceptance
check` errors on a `walked` row with no passing walk."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.check import check
from fr.acceptance.model import Matrix, Row, Walk, load_matrix

from tests.unit.test_record_apply import _matrix_repo

MATRIX = Path("docs") / "acceptance" / "matrix.yaml"
WALK = ("--walk", "walk.log", "--harness", "claude-code", "--model", "opus", "--strategy", "live")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _matrix_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def _fr(*args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(app, ["acceptance", *args])


def _status(root: Path) -> str:
    return next(r for r in load_matrix(root / MATRIX).rows if r.id == "target").status


def _walked(*extra: str):
    return _fr("set-status", "--id", "target", "--status", "walked", "--notes", "n", *extra)


def test_walked_without_a_passing_walk_is_refused(repo: Path) -> None:
    before = (repo / MATRIX).read_text()
    out = _walked()
    assert out.exit_code == 2, out.output
    assert "passing walk" in out.output
    assert (repo / MATRIX).read_text() == before


def test_walked_with_a_failing_walk_is_refused(repo: Path) -> None:
    out = _walked(*WALK, "--walk-outcome", "fail")
    assert out.exit_code == 2, out.output
    assert _status(repo) == "ci"


def test_walked_recording_a_passing_walk_moves_the_row(repo: Path) -> None:
    out = _walked(*WALK, "--walk-at", "2026-07-09")
    assert out.exit_code == 0, out.output
    row = next(r for r in load_matrix(repo / MATRIX).rows if r.id == "target")
    assert row.status == "walked"
    assert row.walks[-1].at == "2026-07-09T00:00:00Z"


def test_walked_over_an_existing_passing_walk_needs_no_new_one(repo: Path) -> None:
    assert _fr("set-status", "--id", "target", "--status", "walk-owed", "--notes", "n", *WALK)\
        .exit_code == 0
    out = _walked()
    assert out.exit_code == 0, out.output
    assert _status(repo) == "walked"


def test_a_malformed_walk_at_is_refused(repo: Path) -> None:
    out = _walked(*WALK, "--walk-at", "last tuesday")
    assert out.exit_code == 2, out.output
    assert "--walk-at" in out.output


def test_the_record_engine_refuses_walked_without_a_passing_walk(repo: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    record = StepRecord(acceptance=(AcceptanceItem(id="target", status="walked", notes="n"),))
    with pytest.raises(RecordRefusedError, match="passing walk"):
        apply_record(repo, None, record, target=RecordTarget(message="m"))


def test_check_errors_on_a_walked_row_with_no_passing_walk(tmp_path: Path) -> None:
    fail = Walk(strategy="live", harness="h", model="m", outcome="fail", at="2026-10-01", evidence="e")
    rows = (
        Row(id="bare", capability="c", acceptance="a", status="walked"),
        Row(id="failed", capability="c", acceptance="a", status="walked", walks=(fail,)),
        Row(id="good", capability="c", acceptance="a", status="walked",
            walks=(fail.model_copy(update={"outcome": "pass"}),)),
    )  # fmt: skip
    result = check(Matrix(org="o", repo="r", rows=rows), tmp_path)
    walked_errors = [e for e in result.errors if "passing walk" in e]
    assert len(walked_errors) == 2
    assert any("bare" in e for e in walked_errors) and any("failed" in e for e in walked_errors)
