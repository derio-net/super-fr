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
MATRIX = "docs/acceptance/features/s.yaml"
"""The fragment `make_repo`'s rows land in (spec 2026-11-04 R16: no matrix.yaml)."""


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


def test_the_split_of_a_v5_matrix_stages_no_ignored_report(tmp_path: Path) -> None:
    """The archive retarget and the matrix anchor repair are gone (rows cite specs
    logically; the matrix kind retired, spec 2026-11-04 R18, R19). What still touches
    the reports is the 5 -> 6 split, which deletes only the reports it finds."""
    from fr.artifacts.matrix_fragments import split_matrix

    from tests.unit.acceptance_helpers import RETIRED_MATRIX_REL, make_matrix_repo

    root = make_matrix_repo(tmp_path, row(id="target", status="not-implemented"))
    changed = split_matrix(root / RETIRED_MATRIX_REL)
    assert {p.relative_to(root).as_posix() for p in changed} == {MATRIX}
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
