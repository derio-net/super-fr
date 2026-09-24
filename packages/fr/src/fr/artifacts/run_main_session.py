"""The `run` kind's 5 -> 6 migration: `StepRecord.main_session` (spec
`2026-09-24-fr-goal-scope-proportion-cost-design.md` §D).

A new optional field on the `extra="forbid"` `StepRecord`, which every released
fr since 4.x reads — so a cursor carrying it RAISES in an older fr rather than
being ignored, and that makes it a shape change under
`.claude/rules/artifact-versioning.md`: a stamp bump (in
`fr.artifacts.registry`, and nowhere else), this migration (imported by the
package `__init__` — a migration nobody imports never runs) and validator
support (`fr.artifacts.structure.validate_run`).

**Stamp-only, like 1 -> 2 and 3 -> 4.** Absent `main_session` is exactly what
every v5 step already means ("not measured"), so there is no body to translate
and the runner writes the stamp once `fn` returns. What `fn` still owes is the
refusal: a cursor it cannot read is not certified as version 6. The v1-v4
guard (`fr.artifacts.run_cursor.cursor_guard`) reads with the frozen v4 model,
which does not know `units`, so it cannot be reused here; a v5 body is asked
of `fr.artifacts.run_unit_record.is_unit_record_body` instead — the one
module allowed to consult the live model, and correct for v5 only while the
change stays additive. No legacy model is frozen, because nothing was removed.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-main-session"


def refuse_unreadable_v5_cursor(path: Path) -> None:
    """Raise `UnreadableRunCursorError` unless `path` reads as a v5 cursor.

    Recorded by the runner as that one artifact's failure: every other cursor
    still migrates, this one stays on 5 and is retried next time.
    """
    from fr.artifacts.run_unit_record import is_unit_record_body

    try:
        readable = is_unit_record_body(path.read_text())
    except OSError:
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-5 run cursor, so fr will not stamp it as "
            "version 6. Fix the file by hand — it is left on its current version and "
            "will be retried."
        )


RUN_MAIN_SESSION_MIGRATION = SchemaMigration(
    kind="run",
    from_version=5,
    to_version=6,
    fn=refuse_unreadable_v5_cursor,
    description="run cursor: add main-session usage per step (`main_session`) — stamp "
    "only, no body change",
)

MIGRATIONS.register(RUN_MAIN_SESSION_MIGRATION)
