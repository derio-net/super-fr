"""The `run` kind's 10 -> 11 migration: `RunState.issue` and `RunState.pr`
(spec `2026-11-04-repo-feature-settings` R12, R14).

Two new optional fields on the `extra="forbid"` `RunState`, which every
released fr reads, so it is a shape change under
`.claude/rules/artifact-versioning.md` even though both are optional and
defaulted: a stamp bump (in `fr.artifacts.registry`), this migration (imported
by the package `__init__`), and validator support
(`fr.artifacts.structure.validate_run` reads with the live model, which knows
the fields).

**Stamp-only, following 9 -> 10 (`fr.artifacts.run_fr_version`).** An old
cursor gets neither field: no issue recorded (the without-issue commit
template applies) and no PR opened through `fr pr create`. There is no body to
translate. What `fn` still owes is the refusal: a cursor it cannot read is not
certified as version 11. A v10 body is asked of
`fr.artifacts.run_usage_split`'s `_already_v10`, the one module allowed to
consult the live model; a body already wholly v11 reads there too, so the
runner finishes the stamp. No legacy model is frozen, because nothing was
removed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-issue"


def refuse_unreadable_v10_cursor(path: Path) -> None:
    """Raise `UnreadableRunCursorError` unless `path` reads as a v10 cursor.

    Recorded by the runner as that one artifact's failure: every other cursor
    still migrates, this one stays on 10, byte-identical, and is retried next
    time.
    """
    from fr.artifacts.run_usage_split import _already_v10

    try:
        text = path.read_text()
        readable = _already_v10(text, yaml.safe_load(text))
    except (OSError, yaml.YAMLError):
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-10 run cursor, so fr will not stamp it as "
            "version 11. Fix the file by hand — it is left on its current version and "
            "will be retried."
        )


RUN_ISSUE_MIGRATION = SchemaMigration(
    kind="run",
    from_version=10,
    to_version=11,
    fn=refuse_unreadable_v10_cursor,
    description=(
        "run cursor: record the run's issue (`issue`) and the PR `fr pr create` opened "
        "(`pr`) — stamp only, no body change"
    ),
)

MIGRATIONS.register(RUN_ISSUE_MIGRATION)
