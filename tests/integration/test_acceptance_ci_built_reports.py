"""Spec 2026-10-12 R1 (`acceptance-ci-built-reports`): every fr commit path
succeeds in a repo that gitignores the generated reports, and stages none."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.report import REPORT_SET
from fr.cli import app
from fr.record.apply import RecordTarget, apply_record
from fr.record.model import AcceptanceItem, StepRecord
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()
IGNORE_ALL = "docs/acceptance/report*.html\ndocs/acceptance/report*.md\n"
MATRIX = "docs/acceptance/matrix.yaml"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path, matrix_rows: str | None = None, gitignore: str = IGNORE_ALL) -> Path:
    root = make_repo(tmp_path, matrix_rows or row(id="target", status="not-implemented"), git=False)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text(gitignore)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    _git(root, "checkout", "-qb", "feat/x")
    return root


def _last_commit_files(root: Path) -> set[str]:
    return set(_git(root, "show", "--name-only", "--format=", "HEAD").split())


def _assert_matrix_only(root: Path, before: str) -> None:
    assert _git(root, "rev-parse", "HEAD").strip() != before, "no commit was made"
    files = _last_commit_files(root)
    assert MATRIX in files
    assert not files & set(REPORT_SET)


def _cli(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


def test_a_record_with_an_acceptance_row_commits_without_ignored_reports(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = _git(root, "rev-parse", "HEAD").strip()
    record = StepRecord(acceptance=(AcceptanceItem(id="target", status="ci", notes="n"),))
    apply_record(root, None, record, target=RecordTarget(message="move target"))
    _assert_matrix_only(root, before)
    assert not any((root / rel).exists() for rel in REPORT_SET)


def test_acceptance_add_commits_without_ignored_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    before = _git(root, "rev-parse", "HEAD").strip()
    result = _cli(
        root,
        monkeypatch,
        *["add", "--id", "new-row", "--capability", "Caps", "--acceptance", "Operator can add"],
        *["--origin", "own:docs/superpowers/specs/s.md", "--level", "unit=own:tests/test_a.py"],
        *["--status", "not-implemented", "--notes", "born in a test"],
    )
    assert result.exit_code == 0, result.output
    _assert_matrix_only(root, before)


def test_acceptance_set_status_commits_without_ignored_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    before = _git(root, "rev-parse", "HEAD").strip()
    result = _cli(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "why"
    )
    assert result.exit_code == 0, result.output
    _assert_matrix_only(root, before)


def test_the_archive_retarget_stages_the_matrix_and_no_ignored_report(tmp_path: Path) -> None:
    from fr.archive import MoveLog
    from fr.commands.archive_cmd import _ArchiveOpts, _retarget_matrix

    block_row = (
        "  - id: target\n    capability: Cap\n    acceptance: X\n    origin:\n"
        "    - own:docs/superpowers/specs/s.md\n    levels:\n      unit:\n"
        "      - own:tests/test_a.py\n    status: ci\n    notes: n\n"
    )
    root = _repo(tmp_path, block_row)
    src = Path("docs/superpowers/specs/s.md")
    dst = Path("docs/superpowers/implemented/specs/s.md")
    _git(root, "mv", str(src), str(dst))
    _retarget_matrix(root, MoveLog(moves=[(src, dst)]), _ArchiveOpts())
    staged = set(_git(root, "diff", "--cached", "--name-only").split())
    assert MATRIX in staged
    assert not staged & set(REPORT_SET)


def test_matrix_anchor_repair_covers_no_ignored_report(tmp_path: Path) -> None:
    from fr.artifacts.matrix_anchors import _fn, _report_paths

    root = _repo(tmp_path, row(id="target", unit='"own:tests/test_a.py#L1"'))
    matrix = root / MATRIX
    assert _report_paths(matrix) == []
    assert list(_fn(matrix)) == []
    assert "#test_a" in matrix.read_text()
    assert not any((root / rel).exists() for rel in REPORT_SET)


def test_init_reports_ignored_reports_as_skipped_and_writes_none(tmp_path: Path) -> None:
    from fr.acceptance.scaffold import init

    root = tmp_path / "bare"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text(IGNORE_ALL)
    outcome = init(root, "example-org", "demo", backend="gitlab")
    assert sorted(outcome.ci_built) == sorted(REPORT_SET)
    assert not set(REPORT_SET) & set(outcome.skipped)
    assert not set(REPORT_SET) & set(outcome.created)
    assert not any((root / rel).exists() for rel in REPORT_SET)
