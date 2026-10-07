"""The `run` kind's 8 -> 9 migration: `Attempt.tier` and `Attempt.bound`
(spec `2026-10-06-cost-evidence-design` §D, R7).

Two new optional fields on the `extra="forbid"` `Attempt`, which every
released fr reads, so it is a shape change under
`.claude/rules/artifact-versioning.md` even though both are optional and
defaulted: a stamp bump (in `fr.artifacts.registry`), this migration
(imported by the package `__init__`), and validator support
(`fr.artifacts.structure.validate_run` reads with the live model, which knows
the fields).

**Stamp-only, following 7 -> 8 (`fr.artifacts.run_driver`).** An attempt with
neither field is exactly what every v8 cursor already holds, and reads as "not
recorded", so there is no body to translate. What `fn` still owes is the
refusal: a cursor it cannot read is not certified as version 9. A v8 body is
asked of `fr.artifacts.run_usage_split`'s `_already_v8`, the one module
allowed to consult the live model. NOT `cursor_guard`: that parses with the
frozen v1-v4 reader and would refuse every v8 cursor. No legacy model is
frozen, because nothing was removed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-bound-model"


def refuse_unreadable_v8_cursor(path: Path) -> None:
    """Raise `UnreadableRunCursorError` unless `path` reads as a v8 cursor.

    Recorded by the runner as that one artifact's failure: every other cursor
    still migrates, this one stays on 8 and is retried next time.
    """
    from fr.artifacts.run_usage_split import _already_v8

    try:
        text = path.read_text()
        readable = _already_v8(text, yaml.safe_load(text))
    except (OSError, yaml.YAMLError):
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-8 run cursor, so fr will not stamp it as "
            "version 9. Fix the file by hand — it is left on its current version and "
            "will be retried."
        )


RUN_BOUND_MODEL_MIGRATION = SchemaMigration(
    kind="run",
    from_version=8,
    to_version=9,
    fn=refuse_unreadable_v8_cursor,
    description=(
        "run cursor: add the dispatched tier and its bound model to subagent attempts "
        "(`tier`, `bound`) — stamp only, no body change"
    ),
)

MIGRATIONS.register(RUN_BOUND_MODEL_MIGRATION)
