"""Phase 2 — `fr acceptance check`: gate, ref resolution, staleness, exits.

Pins spec traps 1 (archive twins), 2 (sibling-root default `..`),
3 (fragments stripped for existence checks), 4 (`.git` presence heuristic)
and the exit contract (2 failing / 1 errors / 0 warnings-only).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.check import resolve_identity
from fr.acceptance.model import AcceptanceError, load_matrix
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def run_check(root: Path, monkeypatch: pytest.MonkeyPatch, *extra: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "check", *extra])


# ── report-set enforcement folded into check (existence-gated) ──────────────


def test_check_unaffected_when_no_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A repo with no committed reports is not forced to have them (bounds the
    blast radius on report-less matrices/fixtures)."""
    root = make_repo(tmp_path, row())
    assert not (root / "docs" / "acceptance" / "report.html").exists()
    assert run_check(root, monkeypatch).exit_code == 0


def test_check_enforces_report_set_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    # In sync → passes.
    assert runner.invoke(app, ["acceptance", "report", "--deterministic"]).exit_code == 0
    assert run_check(root, monkeypatch).exit_code == 0
    # Touch the matrix without regenerating → check goes red.
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    matrix.write_text(matrix.read_text() + row(id="drift"))
    res = run_check(root, monkeypatch)
    assert res.exit_code == 1, res.output
    assert "report" in res.output.lower()


def test_check_fails_when_one_report_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", "--deterministic"]).exit_code == 0
    (root / "docs" / "acceptance" / "report_linked.md").unlink()
    res = run_check(root, monkeypatch)
    assert res.exit_code == 1, res.output
    assert "report_linked.md" in res.output


# ── T1: CLI skeleton + identity resolution ─────────────────────────────────


def test_check_green_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "1 rows OK" in result.output


def test_check_no_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1
    assert "fr acceptance init" in result.output


def _git_repo_with_remote(tmp_path: Path, url: str) -> Path:
    root = tmp_path / "g"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=root, check=True)
    return root


def test_resolve_identity_matrix_keys_win(tmp_path: Path) -> None:
    root = _git_repo_with_remote(tmp_path, "https://github.com/other/rem.git")
    (root / "m.yaml").write_text("org: derio-net\nrepo: own\nrows: []\n")
    matrix = load_matrix(root / "m.yaml")
    assert resolve_identity(matrix, root) == ("derio-net", "own")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/derio-net/super-fr.git",
        "https://github.com/derio-net/super-fr",
        "git@github.com:derio-net/super-fr.git",
    ],
)
def test_resolve_identity_from_remote(tmp_path: Path, url: str) -> None:
    root = _git_repo_with_remote(tmp_path, url)
    (root / "m.yaml").write_text("rows: []\n")
    matrix = load_matrix(root / "m.yaml")
    assert resolve_identity(matrix, root) == ("derio-net", "super-fr")


def test_resolve_identity_no_remote_no_keys(tmp_path: Path) -> None:
    root = tmp_path / "g"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "m.yaml").write_text("rows: []\n")
    with pytest.raises(AcceptanceError, match="org.*repo"):
        resolve_identity(load_matrix(root / "m.yaml"), root)


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/derio-net/super-fr.git",
        "git@gitlab.com:derio-net/super-fr.git",
        "https://gitea.example.com/derio-net/super-fr.git",
    ],
)
def test_resolve_identity_from_non_github_remote(tmp_path: Path, url: str) -> None:
    """resolve_identity's remote-parsing fallback is not GitHub-only —
    without this, `fr acceptance init` would hard-fail on a fresh
    GitLab/Gitea repo before it could even write the matrix that would
    make org/repo explicit going forward (docs/superpowers/specs/
    2026-07-09-multi-backend-git-host-adapters-design.md §10)."""
    root = _git_repo_with_remote(tmp_path, url)
    (root / "m.yaml").write_text("rows: []\n")
    matrix = load_matrix(root / "m.yaml")
    assert resolve_identity(matrix, root) == ("derio-net", "super-fr")


# ── T2: ref resolution ─────────────────────────────────────────────────────


def test_own_ref_missing_file_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/nope.py"'))
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1
    assert "does not resolve" in result.output
    assert "own:tests/nope.py" in result.output


def test_fragment_stripped_for_existence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trap 3: `#L10` is URL decoration, not part of the path on disk."""
    root = make_repo(tmp_path, row(unit='"own:tests/test_a.py#L1"'))
    assert run_check(root, monkeypatch).exit_code == 0


def test_sibling_with_git_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(unit='"sib:lib/f.py"'))
    sib = tmp_path / "sib"
    (sib / "lib").mkdir(parents=True)
    (sib / ".git").mkdir()
    (sib / "lib" / "f.py").write_text("x = 1\n")
    assert run_check(root, monkeypatch).exit_code == 0


def test_sibling_with_git_missing_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(unit='"sib:lib/nope.py"'))
    sib = tmp_path / "sib"
    (sib / "lib").mkdir(parents=True)
    (sib / ".git").mkdir()
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1
    assert "does not resolve" in result.output


def test_sibling_without_git_warns_not_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trap 4: a plain directory at the sibling path is NOT a checkout."""
    root = make_repo(tmp_path, row(unit='"sib:lib/f.py"'))
    (tmp_path / "sib" / "lib").mkdir(parents=True)
    (tmp_path / "sib" / "lib" / "f.py").write_text("x = 1\n")
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0
    assert "not checked out" in result.output


def test_sibling_absent_warns_once_per_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = row(id="r1", unit='"gone:a.py"') + row(id="r2", unit='"gone:b.py"')
    root = make_repo(tmp_path, rows)
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0
    assert result.output.count("gone not checked out") == 1


def test_check_runs_from_repo_subdirectory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trap 6 pinned directly: no VK_REPO_ROOT, cwd = a subdirectory of a
    real git repo — the root resolves via git, not the process cwd."""
    root = make_repo(tmp_path, row(), git=False)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.delenv("VK_REPO_ROOT", raising=False)
    monkeypatch.chdir(root / "docs" / "acceptance")
    result = runner.invoke(app, ["acceptance", "check"])
    assert result.exit_code == 0, result.output
    assert "1 rows OK" in result.output


# ── T3: archive twins + staleness ──────────────────────────────────────────


def test_archived_ref_downgrades_to_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trap 1: the close-out that archives a cited spec must not break check."""
    root = make_repo(tmp_path, row())
    spec = root / "docs" / "superpowers" / "specs" / "s.md"
    dest = root / "docs" / "superpowers" / "implemented" / "specs" / "s.md"
    spec.rename(dest)
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "moved to" in result.output
    assert "update the matrix ref when convenient" in result.output


def test_staleness_uncited_test_plan_spec_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row())
    other = root / "docs" / "superpowers" / "specs" / "uncited.md"
    other.write_text("# u\n\n## Test Plan\n\n1. y\n")
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1
    assert "staleness" in result.output
    assert "uncited.md" in result.output


def test_staleness_citation_survives_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spec cited via its pre-archive path stays cited after the move."""
    root = make_repo(tmp_path, row())
    spec = root / "docs" / "superpowers" / "specs" / "s.md"
    spec.rename(root / "docs" / "superpowers" / "implemented" / "specs" / "s.md")
    result = run_check(root, monkeypatch)
    assert "staleness" not in result.output


def test_spec_without_test_plan_exempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    (root / "docs" / "superpowers" / "specs" / "no-plan.md").write_text("# n\n\nprose only\n")
    assert run_check(root, monkeypatch).exit_code == 0


# ── T4: exit contract + CI annotations ─────────────────────────────────────


def test_failing_row_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(status="failing"))
    result = run_check(root, monkeypatch)
    assert result.exit_code == 2
    assert "failing acceptance rows" in result.output
    assert "r1" in result.output


def test_failing_beats_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = row(id="r1", status="failing") + row(id="r2", unit='"own:tests/nope.py"')
    root = make_repo(tmp_path, rows)
    assert run_check(root, monkeypatch).exit_code == 2


def test_warning_rows_annotate_and_exit_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = row(id="r1", status="skipped") + row(id="r2", status="not-implemented", unit="")
    root = make_repo(tmp_path, rows)
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0
    assert "::warning title=acceptance-matrix::r1 is skipped" in result.output
    assert "::warning title=acceptance-matrix::r2 is not-implemented" in result.output


def test_all_ci_no_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    result = run_check(root, monkeypatch)
    assert result.exit_code == 0
    assert "::warning" not in result.output
