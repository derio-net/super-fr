"""Every writer refuses what `local_error` refuses (spec 2026-11-14-acceptance-local-status
R2, R3): `add`, `set-status`, `amend --op set-status` and a step record's entry. A
refusal is exit 2 (or `RecordRefusedError`) with every fragment byte-identical."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.fold import load_effective

from tests.unit.test_record_apply import _acceptance_files, _matrix_repo, commit_all, git


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`_matrix_repo` (row `target`, refs own:tests/test_a.py and test_b.py), with CI."""
    root = _matrix_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def no_ci(repo: Path) -> Path:
    git(repo, "rm", "-rq", ".github")
    commit_all(repo, "drop ci")
    return repo


def _fr(*args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(app, ["acceptance", *args])


def _target(root: Path):
    return next(r for r in load_effective(root).rows if r.id == "target")


def test_add_local_with_no_level_is_refused(no_ci: Path) -> None:
    before = _acceptance_files(no_ci)
    out = _fr(
        "add", "--id", "fresh", "--capability", "Cap", "--acceptance", "a",
        "--origin", "own:docs/superpowers/specs/s.md", "--status", "local", "--notes", "n",
    )  # fmt: skip
    assert out.exit_code == 2, out.output
    assert "level ref" in out.output
    assert _acceptance_files(no_ci) == before


def test_set_status_local_in_a_repo_with_ci_is_refused(repo: Path) -> None:
    before = _acceptance_files(repo)
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 2, out.output
    assert "`ci`" in out.output and "unwired" in out.output
    assert _acceptance_files(repo) == before


def test_amend_set_status_local_with_a_missing_test_is_refused(no_ci: Path) -> None:
    git(no_ci, "rm", "-q", "tests/test_b.py")
    commit_all(no_ci, "drop test b")
    before = _acceptance_files(no_ci)
    out = _fr(
        "amend", "--id", "target", "--op", "set-status", "--status", "local",
        "--notes", "n", "--why", "w",
    )  # fmt: skip
    assert out.exit_code == 2, out.output
    assert "tests/test_b.py" in out.output
    assert _acceptance_files(no_ci) == before


def test_a_record_entry_with_an_unresolved_ref_is_refused(no_ci: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    before = _acceptance_files(no_ci)
    item = AcceptanceItem.model_validate(
        {"id": "target", "status": "local", "notes": "n", "levels": {"unit": ["own:tests/no.py"]}}
    )
    with pytest.raises(RecordRefusedError, match="tests/no.py"):
        apply_record(no_ci, None, StepRecord(acceptance=(item,)), target=RecordTarget(message="m"))
    assert _acceptance_files(no_ci) == before


def test_set_status_local_under_ci_none_moves_the_row(no_ci: Path) -> None:
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 0, out.output
    row = _target(no_ci)
    assert row.status == "local"
    assert row.local is None  # only deliver stamps
