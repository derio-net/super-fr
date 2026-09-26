"""The `record` kind's 1 -> 2 migration: question-round declarations (spec
`2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B).

`StepRecord` gained `questions`, and it is `extra="forbid"`, so this is a
shape change under `.claude/rules/artifact-versioning.md`: a stamp bump (in
`fr.artifacts.registry`, and nowhere else) plus this migration, which the
package `__init__` imports for its side effect — a migration nobody imports
never runs.

**It rewrites no body, and that is the whole design.** `questions` is
optional and absent-by-default, which is exactly what every v1 record
already means ("one round, undeclared"), so there is nothing to translate:
the runner writes the new stamp itself once `fn` returns. What is left for
`fn` is the one decision a stamp-only migration can still get wrong:
stamping a file it cannot actually read. A record is git-tracked and
hand-editable while its step is in progress, and a truncated or malformed
one that gets stamped `2` is *worse* than one left at 1 — it now claims a
shape it does not have, and the migration will never look at it again. So
`fn` loads the raw yaml mapping, builds a copy with `schema_version` replaced
by 2, and validates THAT copy against the live `StepRecord` (a v1 body is a
valid v2 body — the change is additive) before letting the runner write the
stamp; a record that fails is reported and left on its current version, like
`run_provenance`'s guard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, SchemaMigration

MIGRATION_NAME = "record-question-rounds"

__all__ = ["MIGRATION_NAME", "RECORD_QUESTIONS_MIGRATION", "UnreadableRecordError"]


class UnreadableRecordError(ArtifactMigrationError):
    """A record file the migration will not stamp, because it does not read
    as a version-2 `StepRecord`."""


def _guard(path: Path) -> None:
    from fr.record.model import RECORD_SCHEMA_VERSION, StepRecord

    try:
        text = path.read_text()
    except OSError as e:
        raise UnreadableRecordError(f"{path}: cannot read: {e}") from e
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise UnreadableRecordError(
            f"{path}: not valid YAML, so fr will not stamp it as record version "
            f"{RECORD_SCHEMA_VERSION} ({e})."
        ) from e
    if not isinstance(data, dict):
        raise UnreadableRecordError(
            f"{path}: top level must be a mapping, got {type(data).__name__}"
        )
    candidate = {**data, "schema_version": RECORD_SCHEMA_VERSION}
    try:
        StepRecord.model_validate(candidate)
    except ValidationError as e:
        raise UnreadableRecordError(
            f"{path}: not a readable record, so fr will not stamp it as version "
            f"{RECORD_SCHEMA_VERSION} ({e}). Fix the file by hand — it is left on its "
            "current version and will be retried."
        ) from e


RECORD_QUESTIONS_MIGRATION = SchemaMigration(
    kind="record",
    from_version=1,
    to_version=2,
    fn=_guard,
    description="record: add question-round declaration (`questions`) — stamp only, no body change",
)

MIGRATIONS.register(RECORD_QUESTIONS_MIGRATION)
