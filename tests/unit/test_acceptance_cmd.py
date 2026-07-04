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

runner = CliRunner()

MATRIX_HEADER = "org: derio-net\nrepo: own\nrows:\n"

ROW_TMPL = """\
  - id: {id}
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: [{origin}]
    levels:
      unit: [{unit}]
    status: {status}
    notes: "n"
"""


def row(
    id: str = "r1",
    origin: str = '"own:docs/superpowers/specs/s.md"',
    unit: str = '"own:tests/test_a.py"',
    status: str = "ci",
) -> str:
    return ROW_TMPL.format(id=id, origin=origin, unit=unit, status=status)


def make_repo(
    tmp_path: Path,
    matrix_rows: str,
    *,
    name: str = "own",
    git: bool = True,
    header: str = MATRIX_HEADER,
) -> Path:
    root = tmp_path / name
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / "docs" / "superpowers" / "implemented" / "specs").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "docs" / "superpowers" / "specs" / "s.md").write_text("# s\n\n## Test Plan\n\n1. x\n")
    (root / "tests" / "test_a.py").write_text("def test_a(): pass\n")
    (root / "docs" / "acceptance" / "matrix.yaml").write_text(header + matrix_rows)
    if git:
        (root / ".git").mkdir()
    return root


def run_check(root: Path, monkeypatch: pytest.MonkeyPatch, *extra: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "check", *extra])


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
