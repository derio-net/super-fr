"""Shared fixture builders for the acceptance-matrix test files."""

from __future__ import annotations

from pathlib import Path

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
    """A minimal fr-shaped repo: matrix, one Test-Plan spec, one test file."""
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
