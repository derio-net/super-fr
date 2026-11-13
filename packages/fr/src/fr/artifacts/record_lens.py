"""The `record` kind's 11 -> 12 migration (spec `2026-11-12-review-lenses-design.md`
§3.B, R4).

A step record's `journal:` section takes a `lens` item (`{kind: lens, lens: <id>,
title: <why>}`): a new value of `JournalItem.kind` and a new field,
`JournalItem.lens`, on an `extra="forbid"` model released fr versions read. Every
v11 record already means "no lens", so this rewrites no body; the runner writes the
stamp once `fn` returns.

`fn` refuses to let the runner stamp a record that does not read as version 11.
Nothing was removed or moved, so the live model reads every v11 record; what it
would also accept, and version 11 would not, is exactly the lens addition, so the
hop refuses a record carrying one (no fr at record 11 could have written it). The
day a field is removed, this hop must be pointed at a frozen `RecordV11` like every
earlier hop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.record_amendments import guard_v10_record
from fr.artifacts.record_questions import UnreadableRecordError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-lens"

__all__ = ["MIGRATION_NAME", "RECORD_LENS_MIGRATION", "guard_v11_record"]


def _carries_a_lens(data: Any) -> bool:
    items = data.get("journal") if isinstance(data, dict) else None
    return isinstance(items, list) and any(
        isinstance(i, dict) and (i.get("kind") == "lens" or "lens" in i) for i in items
    )


def guard_v11_record(path: Path) -> None:
    """Raise `UnreadableRecordError` unless `path` reads as a record of version 11,
    leaving it untouched either way."""
    guard_v10_record(path)
    if _carries_a_lens(yaml.safe_load(path.read_text())):
        raise UnreadableRecordError(
            f"{path}: stamped record version 11 but carries a `lens` journal item, which "
            "no fr at version 11 could write; left as it is (fix the file by hand)"
        )


RECORD_LENS_MIGRATION = SchemaMigration(
    kind="record",
    from_version=11,
    to_version=12,
    fn=guard_v11_record,
    description="record: add the `lens` journal item — stamp only, no body change",
)

MIGRATIONS.register(RECORD_LENS_MIGRATION)
