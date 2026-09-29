"""The `record` kind's 5 -> 6 migration (spec
`2026-09-29-fr-goal-light-path-design.md` §A).

`StepRecord.shape` — the brainstorm record's declaration that the run
continues on another workflow shape (`fr-goal-light`) — lands on an
`extra="forbid"` model, so an older fr raises on a record carrying it: a shape
change under `.claude/rules/artifact-versioning.md`. It is optional and
absent-by-default, which is what every v5 record already means, so this
rewrites no body — the runner writes the stamp once `fn` returns. `fn` is the
same guard every record hop uses: never stamp a record that does not read.
Nothing is removed or moved, so no frozen legacy model is owed.
"""

from __future__ import annotations

from fr.artifacts.record_questions import guard_record
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-shape"

__all__ = ["MIGRATION_NAME", "RECORD_SHAPE_MIGRATION"]

RECORD_SHAPE_MIGRATION = SchemaMigration(
    kind="record",
    from_version=5,
    to_version=6,
    fn=guard_record,
    description="record: add `StepRecord.shape` — stamp only, no body change",
)

MIGRATIONS.register(RECORD_SHAPE_MIGRATION)
