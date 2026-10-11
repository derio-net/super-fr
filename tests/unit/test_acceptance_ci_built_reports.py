"""Spec 2026-10-12 R1-R3 (`acceptance-ci-built-reports`): a report the repo
gitignores is CI-built; the check paths skip it, `--deterministic` still writes it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.check import check
from fr.acceptance.model import load_matrix
from fr.acceptance.report import (
    REPORT_SET,
    ci_built_reports,
    render_committed_set,
    tracked_reports,
)
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()
IGNORE_ALL = "docs/acceptance/report*.html\ndocs/acceptance/report*.md\n"
LOCAL = "docs/acceptance/report_local.html"
LINKED_MD = "docs/acceptance/report_linked.md"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path, gitignore: str) -> Path:
    root = make_repo(tmp_path, row(), git=False)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text(gitignore)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


def _write_reports(root: Path, *rels: str, stale: bool = False) -> None:
    rendered = render_committed_set(load_matrix(root / "docs/acceptance/matrix.yaml"), root)
    for rel in rels:
        (root / rel).write_text(rendered[rel] + ("<!-- stale -->\n" if stale else ""))


def _drift(root: Path) -> list[str]:
    result = check(load_matrix(root / "docs/acceptance/matrix.yaml"), root)
    return [e for e in result.errors if "report drift" in e]


def _report(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "report", *args])


def test_ignored_reports_are_ci_built_and_none_are_tracked(tmp_path: Path) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    assert ci_built_reports(root) == frozenset(REPORT_SET)
    assert tracked_reports(root) == {}


def test_an_ignored_but_force_tracked_report_is_not_ci_built(tmp_path: Path) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    _write_reports(root, LOCAL)
    _git(root, "add", "-f", LOCAL)
    assert LOCAL not in ci_built_reports(root)
    assert set(tracked_reports(root)) == {LOCAL}


def test_a_non_git_directory_has_no_ci_built_reports(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    assert ci_built_reports(root) == frozenset()
    assert tracked_reports(root) == REPORT_SET


def test_check_reports_no_drift_for_absent_or_stale_ignored_reports(tmp_path: Path) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    assert _drift(root) == []
    _write_reports(root, *REPORT_SET, stale=True)
    assert _drift(root) == []


def test_check_still_reports_drift_for_a_stale_tracked_report_only(tmp_path: Path) -> None:
    root = _repo(tmp_path, "docs/acceptance/report_linked.md\n")
    _write_reports(root, *REPORT_SET)
    _write_reports(root, LOCAL, stale=True)
    drift = _drift(root)
    assert len(drift) == 1
    assert all(LINKED_MD not in e for e in drift)
    assert any(LOCAL in e for e in drift)


def test_report_check_passes_with_ignored_reports_absent_and_names_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    result = _report(root, monkeypatch, "--check")
    assert result.exit_code == 0, result.output
    assert "CI-built, skipped" in result.output


def test_report_check_still_exits_3_on_a_stale_tracked_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, "docs/acceptance/report_linked.md\n")
    _write_reports(root, LOCAL, "docs/acceptance/report_linked.html", stale=True)
    result = _report(root, monkeypatch, "--check")
    assert result.exit_code == 3, result.output


def test_report_check_with_an_explicit_out_compares_an_ignored_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    _write_reports(root, LINKED_MD, stale=True)
    result = _report(root, monkeypatch, "--check", "--out", LINKED_MD)
    assert result.exit_code == 3, result.output


def test_report_deterministic_writes_ignored_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, IGNORE_ALL)
    result = _report(root, monkeypatch, "--deterministic")
    assert result.exit_code == 0, result.output
    assert all((root / rel).is_file() for rel in REPORT_SET)
