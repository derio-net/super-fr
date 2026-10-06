"""The `record` kind's 7 -> 8 migration (spec
`2026-10-06-verification-strategies-design.md` §B).

`AcceptanceItem.verify` widens from `Literal["post-merge"]` to a strategy name
(refusing the old spelling), and the item gains `scenario`, `issues`,
`harnesses` and `walk`. `AcceptanceItem` is `_Strict`, so this is a record
shape change: the stamp moves to 8.

**Stamp only, almost always.** Records are transient — committed while their
step runs, deleted by the resolve that applies them — and every v7 record is a
valid v8 record except one whose acceptance entry says `verify: post-merge`.
That entry gets what the matrix row got (R7): `verify: live`. The artifact-
versioning rule, kept:

1. **Frozen reader.** The body is read with `fr.record.legacy.RecordV7`, never
   the live model; one that does not read is refused and left on version 7.
2. **Built in memory, written once**, via `write_text_atomic`, and only when an
   entry actually changes — and only after the result validates as v8.
3. **The crash window.** A body that already reads as v8 under a v7 stamp is
   left alone and the runner stamps it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.record_contract import UnconvertibleRecordError
from fr.artifacts.record_questions import UnreadableRecordError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-strategies"

__all__ = ["MIGRATION_NAME", "RECORD_STRATEGIES_MIGRATION", "guard_record_v7"]


def _is_v8(data: dict[str, Any]) -> bool:
    from fr.record.model import RECORD_SCHEMA_VERSION, StepRecord

    try:
        StepRecord.model_validate({**data, "schema_version": RECORD_SCHEMA_VERSION})
    except ValueError:  # pydantic's ValidationError is one
        return False
    return True


def guard_record_v7(path: Path) -> None:
    """Move `path`'s body from v7 to v8 (a `post-merge` acceptance entry
    becomes `live`), or raise leaving it untouched."""
    from fr.record.legacy import RecordV7Error, record_v7_from_data

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
    if _is_v8(data):
        return  # already v8 in body (crash window, or nothing to change)
    try:
        record_v7_from_data({**data, "schema_version": 7})
    except RecordV7Error as e:
        raise UnreadableRecordError(
            f"{path}: not a readable record, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e
    body = {
        **data,
        "acceptance": [
            {**item, "verify": "live"} if item.get("verify") == "post-merge" else item
            for item in data.get("acceptance") or ()
        ],
    }
    if not data.get("acceptance"):
        body.pop("acceptance", None)
    if not _is_v8(body):
        raise UnconvertibleRecordError(
            f"{path}: does not read as a version-8 record once `verify: post-merge` becomes "
            "`verify: live`. Left on version 7, byte-identical."
        )
    write_text_atomic(path, yaml.safe_dump(body, sort_keys=False, allow_unicode=True))


RECORD_STRATEGIES_MIGRATION = SchemaMigration(
    kind="record",
    from_version=7,
    to_version=8,
    fn=guard_record_v7,
    description="record: `verify` names a strategy (`post-merge` becomes `live`)",
)

MIGRATIONS.register(RECORD_STRATEGIES_MIGRATION)
