"""The `matrix` kind's last hop, 5 -> 6: the split into fragments (spec
`2026-11-04-repo-feature-settings-design.md` R19).

`docs/acceptance/matrix.yaml` is split by origin spec into one fragment per
feature, `docs/acceptance/features/<spec-slug>.yaml` (`fr.acceptance.fragment`):

- every row's origin and level refs go through `fr.acceptance.logical.to_logical`,
  so a spec or plan path becomes `spec:<slug>[#R<n>]` / `plan:<slug>` (refs into
  another repo keep their path);
- a row whose converted origins name exactly one spec lands in that spec's
  fragment; one naming none (a debug journal, code) or more than one goes to
  `legacy.yaml`;
- every fragment carries `repo: <org>/<repo>`, the matrix's identity (spec
  journal decision `fragment-repo-identity`);
- the matrix and its committed reports are deleted: the effective matrix is now a
  fold (`fr.acceptance.fold`), and reports are derived (R20).

The kind is RETIRED by this hop (`SchemaMigration.retires`): the runner writes no
stamp and checks the matrix is gone. Per `.claude/rules/artifact-versioning.md`:

1. **Frozen reader.** The body is read with `fr.acceptance.legacy.MatrixV5`
   only, never the live model.
2. **Built in memory, written once.** Every fragment text is rendered and parsed
   back (`parse_fragment`), and the whole set — with any fragment already on
   disk — is folded in memory and compared row for row with the matrix, before
   the first `write_text_atomic`. A matrix that cannot be split is left
   byte-identical and reported as that artifact's failure.
3. **The crash window.** A fragment already on disk with exactly the bytes the
   split would write is not rewritten, so a run that died after writing the
   fragments finishes by deleting the matrix and reports. A fragment on disk
   with OTHER bytes refuses the split: fr will not overwrite it.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.matrix_strategies import UnconvertibleMatrixError
from fr.artifacts.matrix_verify import UnreadableMatrixError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "acceptance-fragments"

__all__ = ["MATRIX_FRAGMENTS_MIGRATION", "MIGRATION_NAME", "split_matrix", "split_texts"]

_DELETED_REPORTS: tuple[str, ...] = (
    "docs/acceptance/report_local.html",
    "docs/acceptance/report_linked.html",
    "docs/acceptance/report_linked.md",
    "docs/acceptance/report.github.html",
)
"""The committed reports R19 deletes — named here, not read from `fr.acceptance.report`,
because they are what a v5 repo carried, whatever the report module writes later."""


def _root(path: Path) -> Path:
    """`<root>/docs/acceptance/matrix.yaml` → `<root>` (the kind's locator)."""
    return path.parents[2]


def _identity(org: str | None, repo: str | None, root: Path) -> str:
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.model import AcceptanceError, Matrix

    try:
        o, r = resolve_identity(Matrix(org=org, repo=repo), root)
    except AcceptanceError as e:
        raise UnconvertibleMatrixError(
            f"every fragment carries `repo: <org>/<repo>`, and this matrix names none: {e}. "
            "Add `org:` and `repo:` to matrix.yaml, then re-run `fr migrate artifacts --yes`. "
            "Left on version 5, byte-identical."
        ) from e
    return f"{o}/{r}"


def split_texts(text: str, root: Path) -> dict[str, str]:
    """The fragment texts (repo-relative path → text) the split of a v5 matrix
    *text* writes, validated; raises leaving nothing written."""
    from fr.acceptance.edit import render_fragment
    from fr.acceptance.fold import fold_texts
    from fr.acceptance.fragment import (
        FRAGMENTS_DIR,
        LEGACY_FEATURE,
        fragment_slug_for_spec,
    )
    from fr.acceptance.legacy import MatrixV5Error, parse_matrix_v5
    from fr.acceptance.logical import parse_logical, to_logical
    from fr.acceptance.model import AcceptanceError, Row
    from fr.artifacts.matrix_anchors import conversions

    try:
        old = parse_matrix_v5(text)
    except MatrixV5Error as e:
        raise UnreadableMatrixError(
            f"not a readable v5 matrix, so fr will not split it ({e}). Fix the file by hand "
            "— it is left on its current version and will be retried."
        ) from e
    repo = _identity(old.org, old.repo, root)
    own = repo.partition("/")[2]
    anchors = conversions(root / "docs" / "acceptance" / "matrix.yaml")

    def convert(ref: str) -> str:
        return to_logical(anchors.get(ref, ref), own_repo=own)

    by_feature: dict[str, list[Row]] = {}
    expected: dict[str, dict[str, object]] = {}
    for v5 in old.rows:
        data = v5.model_dump()
        data["origin"] = [convert(o) for o in v5.origin]
        data["levels"] = {lv: [convert(r) for r in refs] for lv, refs in v5.levels.items()}
        try:
            row = Row.model_validate(data)
        except ValueError as e:
            raise UnconvertibleMatrixError(
                f"row {v5.id} does not read as a fragment row once its refs are logical "
                f"({e}). Left on version 5, byte-identical."
            ) from e
        specs = {parse_logical(o).slug for o in row.origin if o.startswith("spec:")}
        feature = (
            fragment_slug_for_spec(f"{next(iter(specs))}.md")
            if len(specs) == 1
            else (LEGACY_FEATURE)
        )
        by_feature.setdefault(feature, []).append(row)
        expected[row.id] = row.model_dump()

    out = {
        f"{FRAGMENTS_DIR.as_posix()}/{feature}.yaml": render_fragment(feature, repo, rows)
        for feature, rows in sorted(by_feature.items())
    }
    folder = root / FRAGMENTS_DIR
    on_disk = (
        {f"{FRAGMENTS_DIR.as_posix()}/{p.name}": p.read_text() for p in folder.glob("*.yaml")}
        if folder.is_dir()
        else {}
    )
    clashes = sorted(rel for rel, t in out.items() if rel in on_disk and on_disk[rel] != t)
    if clashes:
        raise UnconvertibleMatrixError(
            f"{', '.join(clashes)} already exist with other content, so fr will not "
            "overwrite them with the split of matrix.yaml — move them aside (or merge "
            "them by hand), then re-run `fr migrate artifacts --yes`. "
            "Left on version 5, byte-identical."
        )
    try:
        effective = fold_texts({**on_disk, **out})
    except AcceptanceError as e:
        raise UnconvertibleMatrixError(
            f"the split does not fold with the fragments already here ({e}). "
            "Left on version 5, byte-identical."
        ) from e
    got = {r.id: r.model_dump() for r in effective.matrix.rows}
    lost = sorted(rid for rid, want in expected.items() if got.get(rid) != want)
    if lost:
        raise UnconvertibleMatrixError(
            f"the split would not carry these rows over unchanged: {', '.join(lost)}. "
            "Left on version 5, byte-identical."
        )
    return out


def _deleted(path: Path) -> list[Path]:
    root = _root(path)
    return [root / rel for rel in _DELETED_REPORTS]


def _companions(path: Path) -> list[Path]:
    """Every file the split may write or delete beside the matrix, named before it
    runs so the uncommitted-changes veto covers them (an unreadable matrix names
    only the reports: the split will refuse it anyway)."""
    root = _root(path)
    try:
        written = [root / rel for rel in split_texts(path.read_text(), root)]
    except Exception:
        written = []
    return [*written, *_deleted(path)]


def split_matrix(path: Path) -> list[Path]:
    """Split *path* into fragments, delete it and its committed reports, or raise
    leaving every file untouched. Returns the fragments written and the reports
    deleted (the runner records *path* itself as removed)."""
    root = _root(path)
    try:
        text = path.read_text()
    except OSError as e:
        raise UnreadableMatrixError(f"{path}: cannot read: {e}") from e
    try:
        texts = split_texts(text, root)
    except (UnreadableMatrixError, UnconvertibleMatrixError) as e:
        raise type(e)(f"{path}: {e}") from e
    changed: list[Path] = []
    for rel, body in texts.items():
        target = root / rel
        if not target.exists() or target.read_text() != body:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(target, body)
        changed.append(target)
    for report in _deleted(path):
        if report.exists():
            report.unlink()
            changed.append(report)
    path.unlink()
    return changed


MATRIX_FRAGMENTS_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=5,
    to_version=6,
    fn=split_matrix,
    description="matrix: split into per-feature fragments under docs/acceptance/features/ "
    "with logical refs; the matrix and its committed reports are deleted (kind retired)",
    companions=_companions,
    retires=True,
)

MIGRATIONS.register(MATRIX_FRAGMENTS_MIGRATION)
