"""The `record` kind's 3 -> 4 migration (spec
`2026-09-28-ui-visual-evidence-design.md` §G).

`AcceptanceItem.visual` and `StepRecord.visual` land on an `extra="forbid"`
model, so an older fr raises on a record carrying them: a shape change under
`.claude/rules/artifact-versioning.md`. Both are optional and absent-by-
default, which is what every v3 record already means, so this rewrites no
body — the runner writes the stamp once `fn` returns. `fn` is the same guard
every record hop uses: never stamp a record that does not read. Nothing is
removed or moved, so no frozen legacy model is owed.
"""

from __future__ import annotations

from fr.artifacts.record_questions import guard_record
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-visual"

__all__ = ["MIGRATION_NAME", "RECORD_VISUAL_MIGRATION"]

RECORD_VISUAL_MIGRATION = SchemaMigration(
    kind="record",
    from_version=3,
    to_version=4,
    fn=guard_record,
    description=(
        "record: add `AcceptanceItem.visual` and `StepRecord.visual` — stamp only, "
        "no body change"
    ),
)

MIGRATIONS.register(RECORD_VISUAL_MIGRATION)
