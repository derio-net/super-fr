"""The `matrix` kind's version-3 migration — spec
`2026-09-28-ui-visual-evidence-design.md` §G: `Row.visual` on an
`extra="forbid"` row, additive, so this is a stamp-only hop. Nothing removed,
so no frozen legacy model.
"""

from __future__ import annotations

from pathlib import Path

from fr.acceptance.model import load_matrix
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION

_V2_MATRIX = """\
# header comment — must survive
schema_version: 2
org: acme
repo: widget
rows:
  - id: a
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["widget:docs/x.md"]
    levels:
      unit: ["widget:tests/test_x.py"]
    status: ci
    notes: "n"
"""


def _matrix(root: Path, text: str = _V2_MATRIX) -> Path:
    path = root / "docs" / "acceptance" / "matrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_matrix_kind_is_at_version_three() -> None:
    assert artifact_kind("matrix").current_version == 3


def test_the_chain_from_one_reaches_three_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert [(s.from_version, s.to_version) for s in chain] == [(1, 2), (2, 3)]


def test_a_v2_matrix_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _matrix(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == before.replace("schema_version: 2\n", "schema_version: 3\n")
    m = load_matrix(path)
    assert m.schema_version == 3 and [r.id for r in m.rows] == ["a"]


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _matrix(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v2_matrix_is_refused_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V2_MATRIX.replace("status: ci", "status: sheduled"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_this_repos_own_matrix_is_current(repo_root: Path) -> None:
    kind = artifact_kind("matrix")
    assert kind.read_version(repo_root / "docs" / "acceptance" / "matrix.yaml") == 3
