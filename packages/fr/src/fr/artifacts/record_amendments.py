"""The `record` kind's 10 -> 11 migration (spec
`2026-11-04-repo-feature-settings-design.md` R16, R19, §5).

The step record's `acceptance:` section gains an amendment item
(`fr.record.model.AmendmentItem`: `{row, op, base?, why, <op fields>}`) beside the
create and move items. It lands on an `extra="forbid"` model that released fr
versions read, so an older fr raises on a record carrying one: a shape change
under `.claude/rules/artifact-versioning.md`. Every v10 record already means "no
amendment", so this rewrites no body; the runner writes the stamp once `fn`
returns.

`fn` refuses to let the runner stamp a record that does not read as version 10.
Nothing was removed or moved, so the live model is still a superset of version 10
and reads it — the one hop allowed to ask it. The day a field is removed, this hop
must be pointed at a frozen `RecordV10` like every earlier hop.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.record_exit_gates import guard_v9_record
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-amendments"

__all__ = ["MIGRATION_NAME", "RECORD_AMENDMENTS_MIGRATION", "guard_v10_record"]


def guard_v10_record(path: Path) -> None:
    """Raise `UnreadableRecordError` unless `path` reads as a record of version 10
    (the live model reads it, the stamp aside), leaving it untouched either way."""
    guard_v9_record(path)


RECORD_AMENDMENTS_MIGRATION = SchemaMigration(
    kind="record",
    from_version=10,
    to_version=11,
    fn=guard_v10_record,
    description="record: add the `acceptance:` amendment item — stamp only, no body change",
)

MIGRATIONS.register(RECORD_AMENDMENTS_MIGRATION)
