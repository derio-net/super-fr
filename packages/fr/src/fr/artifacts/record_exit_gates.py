"""The `record` kind's 9 -> 10 migration (spec `2026-10-14-exit-gates-design.md`
§C, R12).

`JournalItem.gate` and `JournalItem.narrows` — a decision's Owner gate — and
`JournalItem.filed_as` — where `fr journal file` filed an owed entry (R10) — land on
an `extra="forbid"` model that released fr versions read, so an older fr raises
on a record carrying them: a shape change under
`.claude/rules/artifact-versioning.md`. All three are optional and absent by default,
which is what every v9 record already means, so this rewrites no body; the
runner writes the stamp once `fn` returns.

`fn` refuses to let the runner stamp a record that does not read as version 9.
Nothing was removed or moved, so the live model is still a superset of version 9
and reads it — the one hop allowed to ask it. The day a field is removed, this
hop must be pointed at a frozen `RecordV9` like every earlier hop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.record_questions import UnreadableRecordError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-exit-gates"

__all__ = ["MIGRATION_NAME", "RECORD_EXIT_GATES_MIGRATION", "guard_v9_record"]


def guard_v9_record(path: Path) -> None:
    """Raise `UnreadableRecordError` unless `path` reads as a record of version 9,
    leaving it untouched either way."""
    from pydantic import ValidationError

    from fr.record.model import StepRecord

    try:
        data: Any = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise UnreadableRecordError(
            f"{path}: cannot read as YAML, so fr will not stamp it ({e})."
        ) from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise UnreadableRecordError(
            f"{path}: top level must be a mapping, got {type(data).__name__}"
        )
    body = {k: v for k, v in data.items() if k != "schema_version"}
    try:
        StepRecord.model_validate(body)
    except ValidationError as e:
        raise UnreadableRecordError(
            f"{path}: not a readable record, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e


RECORD_EXIT_GATES_MIGRATION = SchemaMigration(
    kind="record",
    from_version=9,
    to_version=10,
    fn=guard_v9_record,
    description=(
        "record: add `JournalItem.gate`/`narrows`/`filed_as` — stamp only, no body change"
    ),
)

MIGRATIONS.register(RECORD_EXIT_GATES_MIGRATION)
