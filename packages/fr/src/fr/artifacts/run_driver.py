"""The `run` kind's 7 -> 8 migration: `RunState.driver` (gh#761).

A new optional field on the `extra="forbid"` `RunState`, which every released
fr reads, so it is a shape change under `.claude/rules/artifact-versioning.md`
even though it is optional and defaulted: a stamp bump (in
`fr.artifacts.registry`), this migration (imported by the package
`__init__`), and validator support (`fr.artifacts.structure.validate_run`
reads with the live model, which knows the field).

**Stamp-only, like 5 -> 6.** An absent `driver` is exactly what every v7
cursor already means (the pipeline drives it), so there is no body to
translate. What `fn` still owes is the refusal: a cursor it cannot read is
not certified as version 8. A v7 body is asked of
`fr.artifacts.run_usage_split`'s `_already_v7`, the one module allowed to
consult the live model, and correct for v7 only while this change stays
additive. No legacy model is frozen, because nothing was removed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-driver"


def refuse_unreadable_v7_cursor(path: Path) -> None:
    """Raise `UnreadableRunCursorError` unless `path` reads as a v7 cursor.

    Recorded by the runner as that one artifact's failure: every other cursor
    still migrates, this one stays on 7 and is retried next time.
    """
    from fr.artifacts.run_usage_split import _already_v7

    try:
        text = path.read_text()
        readable = _already_v7(text, yaml.safe_load(text))
    except (OSError, yaml.YAMLError):
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-7 run cursor, so fr will not stamp it as "
            "version 8. Fix the file by hand — it is left on its current version and "
            "will be retried."
        )


RUN_DRIVER_MIGRATION = SchemaMigration(
    kind="run",
    from_version=7,
    to_version=8,
    fn=refuse_unreadable_v7_cursor,
    description="run cursor: add who drives the run (`driver`) — stamp only, no body change",
)

MIGRATIONS.register(RUN_DRIVER_MIGRATION)
