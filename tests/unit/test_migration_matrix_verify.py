"""The `matrix` kind's version-2 migration — spec
`2026-09-28-requirements-traceability-design.md` §H: `Row.verify` on an
`extra="forbid"` row, the first time the matrix kind moves past 1, so `Matrix`
gains `schema_version` in the same change (artifact-versioning rule). Stamp
only; nothing removed, so no frozen legacy model.
"""

from __future__ import annotations

from pathlib import Path

from fr.acceptance.model import load_matrix
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION

_V1_MATRIX = """\
# header comment — must survive
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


def _matrix(root: Path, text: str = _V1_MATRIX) -> Path:
    path = root / "docs" / "acceptance" / "matrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_a_one_to_two_hop_exists() -> None:
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert chain[0].from_version == 1 and chain[0].to_version == 2


def test_a_v1_matrix_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    """A v1 matrix now chains all the way to the current version (spec
    2026-09-28-ui-visual-evidence-design.md §G added a 2 -> 3 hop after this
    one); what this pins is that the body is untouched throughout."""
    path = _matrix(tmp_path)
    before = path.read_text().splitlines(keepends=True)
    kind = artifact_kind("matrix")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    after = path.read_text().splitlines(keepends=True)
    stamp_line = f"schema_version: {kind.current_version}\n"
    assert stamp_line in after
    assert [ln for ln in after if ln != stamp_line] == before
    rows_at = after.index("rows:\n")
    trailing_top_level_keys = [
        ln for ln in after[rows_at + 1 :] if ln and not ln[0].isspace() and ":" in ln
    ]
    assert not trailing_top_level_keys, (
        f"a top-level key follows rows: {trailing_top_level_keys!r} — "
        "rows: must stay the last top-level key"
    )
    m = load_matrix(path)
    assert m.schema_version == kind.current_version and [r.id for r in m.rows] == ["a"]


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _matrix(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v1_matrix_is_refused_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V1_MATRIX.replace("status: ci", "status: sheduled"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_this_repos_own_matrix_is_current(repo_root: Path) -> None:
    kind = artifact_kind("matrix")
    assert (
        kind.read_version(repo_root / "docs" / "acceptance" / "matrix.yaml") == kind.current_version
    )
