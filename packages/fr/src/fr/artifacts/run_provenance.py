"""The `run` kind's 1 → 2 migration: gate provenance (spec §3.D.2).

`StepRecord` gained `answered_by`, and `RunState` is `extra="forbid"`, so a
cursor written by this fr raises `RunStateError` in any fr that predates the
field. That makes it a **shape change** under
`.claude/rules/artifact-versioning.md`: a stamp bump (in
`fr.artifacts.registry`, and nowhere else) plus the migration below, which the
package `__init__` imports — a migration nobody imports never runs.

**It rewrites no body, and that is the whole design.** The new field is
optional and defaults to absent, which is exactly what every v1 cursor already
means ("no gate was cleared here"), so there is nothing to translate; the
runner writes the stamp itself once `fn` returns. What is left for `fn` is the
one decision a stamp-only migration can still get wrong: stamping a file it
cannot actually read. A run cursor is git-tracked and hand-editable, and a
truncated or half-merged one that gets stamped `2` is *worse* than one left at
1 — it now claims a shape it does not have, and the migration will never look
at it again. So `fn` parses first and refuses: that guard is
`fr.artifacts.run_cursor.cursor_guard`, shared with the 2 -> 3 migration,
which is stamp-only for the same reason.
"""

from __future__ import annotations

from fr.artifacts.run_cursor import UnreadableRunCursorError, cursor_guard
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-gate-provenance"

__all__ = ["MIGRATION_NAME", "RUN_PROVENANCE_MIGRATION", "UnreadableRunCursorError"]


RUN_PROVENANCE_MIGRATION = SchemaMigration(
    kind="run",
    from_version=1,
    to_version=2,
    fn=cursor_guard(2),
    description="run cursor: add gate provenance (`answered_by`) — stamp only, no body change",
)

MIGRATIONS.register(RUN_PROVENANCE_MIGRATION)
