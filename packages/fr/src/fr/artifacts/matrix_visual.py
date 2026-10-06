"""The `matrix` kind's 2 -> 3 migration (spec
`2026-09-28-ui-visual-evidence-design.md` §G).

`Row.visual` lands on an `extra="forbid"` row, so an older fr rejects a matrix
carrying it: a shape change under `.claude/rules/artifact-versioning.md`.
`visual` is optional and absent by default, which is what every v2 row already
means, so this rewrites no body — the runner writes the stamp once `fn`
returns. `fn` only refuses to stamp a matrix that does not read as a matrix —
a stamped broken file would claim a shape it does not have. It shares
`guard_matrix`, which reads through the frozen `fr.acceptance.legacy.MatrixV3`
since the 3 -> 4 hop (`fr.artifacts.matrix_strategies`).
"""

from __future__ import annotations

from fr.artifacts.matrix_verify import guard_matrix
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "matrix-visual"

__all__ = ["MATRIX_VISUAL_MIGRATION", "MIGRATION_NAME"]

MATRIX_VISUAL_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=2,
    to_version=3,
    fn=guard_matrix,
    description="matrix: add `visual` on a row — stamp only, no body change",
)

MIGRATIONS.register(MATRIX_VISUAL_MIGRATION)
