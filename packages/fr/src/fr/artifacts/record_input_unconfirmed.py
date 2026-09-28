"""The `record` kind's 2 -> 3 migration (spec
`2026-09-28-requirements-traceability-design.md` §H).

`JournalItem.input`, `AcceptanceItem.verify` and `ResolutionState` +
`unconfirmed` land on an `extra="forbid"` model, so an older fr raises on a
record carrying them: a shape change under
`.claude/rules/artifact-versioning.md`. Every addition is optional and
absent-by-default, which is what every v2 record already means, so this
rewrites no body — the runner writes the stamp once `fn` returns. `fn` is the
same guard the 1 -> 2 hop uses: never stamp a record that does not read.
Nothing is removed or moved, so no frozen legacy model is owed.
"""

from __future__ import annotations

from fr.artifacts.record_questions import guard_record
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-input-unconfirmed"

__all__ = ["MIGRATION_NAME", "RECORD_INPUT_UNCONFIRMED_MIGRATION"]

RECORD_INPUT_UNCONFIRMED_MIGRATION = SchemaMigration(
    kind="record",
    from_version=2,
    to_version=3,
    fn=guard_record,
    description=(
        "record: add `input`, `verify` and the `unconfirmed` resolution — stamp only, "
        "no body change"
    ),
)

MIGRATIONS.register(RECORD_INPUT_UNCONFIRMED_MIGRATION)
