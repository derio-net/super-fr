"""The `run` kind's 9 -> 10 migration: `RunState.fr_version` (spec
`2026-10-07-cloud-triage-design` §G, R16).

A new optional field on the `extra="forbid"` `RunState`, which every released
fr reads, so it is a shape change under `.claude/rules/artifact-versioning.md`
even though it is optional and defaulted: a stamp bump (in
`fr.artifacts.registry`), this migration (imported by the package `__init__`),
and validator support (`fr.artifacts.structure.validate_run` reads with the
live model, which knows the field).

**Stamp-only, following 7 -> 8 (`fr.artifacts.run_driver`) and 8 -> 9
(`fr.artifacts.run_bound_model`).** An old cursor gets no field, which is
exactly what R17 means by "no recorded version": the triage driver reports it
and never re-homes it. There is no body to translate. What `fn` still owes is
the refusal: a cursor it cannot read is not certified as version 10. A v9 body
is asked of `fr.artifacts.run_usage_split`'s `_already_v9`, the one module
allowed to consult the live model; a body already wholly v10 (it carries
`fr_version` under a 9 stamp, the crash window) reads there too, so the runner
finishes the stamp. No legacy model is frozen, because nothing was removed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-fr-version"


def refuse_unreadable_v9_cursor(path: Path) -> None:
    """Raise `UnreadableRunCursorError` unless `path` reads as a v9 cursor.

    Recorded by the runner as that one artifact's failure: every other cursor
    still migrates, this one stays on 9, byte-identical, and is retried next
    time.
    """
    from fr.artifacts.run_usage_split import _already_v9

    try:
        text = path.read_text()
        readable = _already_v9(text, yaml.safe_load(text))
    except (OSError, yaml.YAMLError):
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-9 run cursor, so fr will not stamp it as "
            "version 10. Fix the file by hand — it is left on its current version and "
            "will be retried."
        )


RUN_FR_VERSION_MIGRATION = SchemaMigration(
    kind="run",
    from_version=9,
    to_version=10,
    fn=refuse_unreadable_v9_cursor,
    description=(
        "run cursor: record the fr version a run started under (`fr_version`) — "
        "stamp only, no body change"
    ),
)

MIGRATIONS.register(RUN_FR_VERSION_MIGRATION)
