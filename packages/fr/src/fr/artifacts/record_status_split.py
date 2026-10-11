"""The `record` kind's 8 -> 9 migration (spec `2026-10-11-debt-engine-design.md`
§D, R27).

A step record carries the acceptance `Status`, and matrix kind 4 -> 5 split
`skipped` into `unwired` / `walk-owed` / `walked` / `manual`, so the live
`AcceptanceItem` refuses `skipped` by name: a record shape change. An in-flight
record's `status: skipped` entry is rewritten by R6's rule
(`fr.artifacts.matrix_status_split.split_status`), read from the entry and the
matrix row it moves:

- a passing walk on the entry or on the row → `walked`;
- otherwise a post-merge `verify` — the entry's own, else the row's, which a
  move keeps — → `walk-owed`;
- otherwise → `unwired`.

The artifact-versioning rule, kept:

1. **Frozen reader.** The body is read with `fr.record.legacy.RecordV8`, never
   the live model; one that does not read is refused and left on version 8.
   The matrix row is read as plain YAML, never through a model, since the
   matrix may sit on either side of its own 4 -> 5 hop.
2. **Built in memory, written once**, via `write_text_atomic`, only when an
   entry changes and only after the result validates as v9. A `verify` that
   does not resolve refuses the record, byte-identical.
3. **The crash window.** A body that already reads as v9 under a v8 stamp is
   left alone and the runner stamps it — the one legitimate use of the live
   model here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.matrix_status_split import split_status
from fr.artifacts.record_contract import UnconvertibleRecordError
from fr.artifacts.record_questions import UnreadableRecordError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-status-split"

__all__ = ["MIGRATION_NAME", "RECORD_STATUS_SPLIT_MIGRATION", "split_record_status"]


def _repo_root(path: Path) -> Path:
    """`<root>/docs/superpowers/runs/<run>.records/<step>.yaml` → `<root>`."""
    return path.parents[4]


def _is_v9(data: dict[str, Any]) -> bool:
    from fr.record.model import RECORD_SCHEMA_VERSION, StepRecord

    try:
        StepRecord.model_validate({**data, "schema_version": RECORD_SCHEMA_VERSION})
    except ValueError:  # pydantic's ValidationError is one
        return False
    return True


def _matrix_rows(root: Path) -> dict[str, dict[str, Any]]:
    """The matrix's rows by id, as plain mappings; empty when there is none or
    it does not read — the entry alone then decides."""
    try:
        data = yaml.safe_load((root / "docs" / "acceptance" / "matrix.yaml").read_text())
    except (OSError, yaml.YAMLError):
        return {}
    rows = data.get("rows") if isinstance(data, dict) else None
    return {r["id"]: r for r in rows or () if isinstance(r, dict) and isinstance(r.get("id"), str)}


def _walked(item: dict[str, Any], row: dict[str, Any]) -> bool:
    walks = [item.get("walk"), *(row.get("walks") or ())]
    return any(isinstance(w, dict) and w.get("outcome") == "pass" for w in walks)


def split_record_status(path: Path) -> None:
    """Move `path`'s body from v8 to v9 (each `skipped` acceptance entry by
    R6's rule), or raise leaving it untouched."""
    from fr.record.legacy import RecordV8Error, record_v8_from_data
    from fr.verification.model import StrategyError

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
    if _is_v9(data):
        return  # already v9 in body (crash window, or nothing to change)
    try:
        record_v8_from_data({**data, "schema_version": 8})
    except RecordV8Error as e:
        raise UnreadableRecordError(
            f"{path}: not a readable record, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e
    root = _repo_root(path)
    rows = _matrix_rows(root)
    entries: list[Any] = []
    for item in data.get("acceptance") or ():
        if item.get("status") != "skipped":
            entries.append(item)
            continue
        row = rows.get(item["id"], {})
        verify = item.get("verify") if item.get("verify") is not None else row.get("verify")
        try:
            status = split_status(_walked(item, row), verify, root)
        except StrategyError as e:
            raise UnconvertibleRecordError(
                f"{path}: acceptance {item['id']} is `skipped` and its verify {verify!r} does "
                f"not resolve ({e}), so fr cannot tell `walk-owed` from `unwired` — fix it, "
                "then re-run `fr migrate artifacts --yes`. Left on version 8, byte-identical."
            ) from e
        entries.append({**item, "status": status})
    body = {**data, "acceptance": entries}
    if not data.get("acceptance"):
        body.pop("acceptance", None)
    if not _is_v9(body):
        raise UnconvertibleRecordError(
            f"{path}: does not read as a version-9 record once its `skipped` entries are "
            "split. Left on version 8, byte-identical."
        )
    if body != data:
        write_text_atomic(path, yaml.safe_dump(body, sort_keys=False, allow_unicode=True))


RECORD_STATUS_SPLIT_MIGRATION = SchemaMigration(
    kind="record",
    from_version=8,
    to_version=9,
    fn=split_record_status,
    description="record: a `skipped` acceptance entry splits into unwired / walk-owed / walked",
)

MIGRATIONS.register(RECORD_STATUS_SPLIT_MIGRATION)
