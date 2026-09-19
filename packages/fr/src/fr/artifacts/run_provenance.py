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
at it again. So `fn` parses first and refuses, which the runner records as
that one artifact's failure (invariant 3): every other cursor still migrates,
the bad one stays unstamped, and the next run retries it.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, SchemaMigration

MIGRATION_NAME = "run-gate-provenance"


class UnreadableRunCursorError(ArtifactMigrationError):
    """A run file the migration will not stamp, because it cannot read it."""


def refuse_unreadable_cursor(path: Path) -> None:
    """Parse `path` as a v1 run cursor, or raise.

    Deliberately the whole of `fn`: there is no body change to make, so the
    only way this migration can do harm is by certifying a file it never
    understood. Goes through `parse_run_state` — the one entry point — rather
    than a second notion of "valid run state" that could drift from the model.

    Imported inside the function: `fr.artifacts` is imported at CLI entry
    before every command, and must not drag the run models in with it.
    """
    from fr.run.model import RunStateError, parse_run_state

    try:
        parse_run_state(path.read_text())
    except (RunStateError, OSError) as e:
        raise UnreadableRunCursorError(
            f"{path}: not a readable run cursor, so fr will not stamp it as version 2 "
            f"({e}). Fix the file by hand — it is left on version 1 and will be "
            f"retried."
        ) from e


RUN_PROVENANCE_MIGRATION = SchemaMigration(
    kind="run",
    from_version=1,
    to_version=2,
    fn=refuse_unreadable_cursor,
    description="run cursor: add gate provenance (`answered_by`) — stamp only, no body change",
)

MIGRATIONS.register(RUN_PROVENANCE_MIGRATION)
