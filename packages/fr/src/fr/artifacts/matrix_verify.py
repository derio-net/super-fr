"""The `matrix` kind's 1 -> 2 migration (spec
`2026-09-28-requirements-traceability-design.md` §H).

`Row.verify` lands on an `extra="forbid"` row, so an older fr rejects a matrix
carrying it: a shape change under `.claude/rules/artifact-versioning.md`, and
the first time the matrix kind moves past 1 — which is why `Matrix` gains
`schema_version` in the same change. `verify` is optional and absent by
default, which is what every v1 row already means, so this rewrites no body:
the runner writes the stamp (above `rows:`, which stays the last top-level key
`fr acceptance add` appends under) once `fn` returns. `fn` only refuses to
stamp a matrix that does not read as a matrix — a stamped broken file would
claim a shape it does not have. It reads through the FROZEN
`fr.acceptance.legacy.MatrixV3`, never the live model: the 3 -> 4 hop
(`fr.artifacts.matrix_strategies`) changed what the live `Row.verify` accepts.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, SchemaMigration

MIGRATION_NAME = "matrix-verify"

__all__ = [
    "MATRIX_VERIFY_MIGRATION",
    "MIGRATION_NAME",
    "UnreadableMatrixError",
    "guard_matrix",
]


class UnreadableMatrixError(ArtifactMigrationError):
    """A matrix the migration will not stamp, because it does not parse."""


def guard_matrix(path: Path) -> None:
    """Refuse to let the runner stamp a matrix that does not parse. Shared by
    every stamp-only matrix hop (`fr.artifacts.matrix_visual`, spec
    2026-09-28-ui-visual-evidence-design.md §G) — no version number in the
    message, since naming one would misreport whichever other hop uses it.

    Reads through the FROZEN `fr.acceptance.legacy.MatrixV3` (versions 1 to
    3), never the live `Matrix`: the 3 -> 4 hop changed `Row.verify`, so the
    live model is no longer a superset of the bodies these hops read (spec
    2026-10-06-verification-strategies §B, artifact-versioning rule)."""
    from fr.acceptance.legacy import MatrixV3Error, parse_matrix_v3

    try:
        parse_matrix_v3(path.read_text())
    except (OSError, MatrixV3Error) as e:
        raise UnreadableMatrixError(
            f"{path}: not a readable matrix, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e


MATRIX_VERIFY_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=1,
    to_version=2,
    fn=guard_matrix,
    description="matrix: add `verify` on a row — stamp only, no body change",
)

MIGRATIONS.register(MATRIX_VERIFY_MIGRATION)
