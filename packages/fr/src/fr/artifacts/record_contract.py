"""The `record` kind's 6 -> 7 migration (spec
`2026-09-29-spec-is-the-contract-design.md` §C).

`JournalItem.delegated` and the `unconfirmed` member of `ResolutionState` are
REMOVED from the live, `extra="forbid"` model: the spec is the contract, so no
decision is marked "your call" and no spec-review finding is built unconfirmed.
The rules of `.claude/rules/artifact-versioning.md` for a removal, each kept
here:

1. **Frozen reader.** The old body is read with `fr.record.legacy.RecordV6` (a
   superset of versions 1 to 6), never the live model — and so is every
   earlier hop (`fr.artifacts.record_questions.guard_record`).
2. **Drop, or refuse.** `delegated` carries nothing a v7 reader needs, so it is
   dropped. A resolution whose state is `unconfirmed` has no honest v7
   equivalent — calling it fixed, refuted or out of scope would each claim
   something that did not happen — so that record is refused: left
   byte-identical and reported as that one artifact's failure, while every
   other record migrates.
3. **Built in memory, written once**, via `write_text_atomic`, after every
   refusal has had its chance to fire and the result has validated as v7.
4. **The crash window between body and stamp.** A body that is already wholly
   v7 under a v6 stamp (the rewrite landed, the stamp did not) reads as v7 with
   its stamp replaced; nothing is written and the runner just stamps it — the
   one legitimate use of the live model here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.record_questions import UnreadableRecordError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "record-contract"

__all__ = ["MIGRATION_NAME", "RECORD_CONTRACT_MIGRATION", "UnconvertibleRecordError"]


class UnconvertibleRecordError(UnreadableRecordError):
    """A v6 record fr READ fine and still will not rewrite."""


def _is_v7(data: dict[str, Any]) -> bool:
    """Whether `data` already reads as version 7 — asked of the FROZEN
    `fr.record.legacy.RecordV7` since the 7 -> 8 hop (spec
    2026-10-06-verification-strategies §B): the live model answers "is this
    v8?", which is not this hop's question."""
    from fr.record.legacy import RecordV7Error, record_v7_from_data

    try:
        record_v7_from_data({**data, "schema_version": 7})
    except RecordV7Error:
        return False
    return True


def drop_removed_fields(path: Path) -> None:
    """Rewrite `path` from v6 to v7 in place, or raise leaving it untouched."""
    from fr.record.legacy import RecordV6Error, record_v6_from_data

    try:
        text = path.read_text()
        data: Any = yaml.safe_load(text)
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
    if _is_v7(data):
        return  # already v7 in body (crash window): the runner only stamps it
    try:
        record_v6_from_data(data)
    except RecordV6Error as e:
        raise UnreadableRecordError(
            f"{path}: not a readable record, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e
    unconfirmed = [
        r.get("id") for r in data.get("resolves") or () if r.get("state") == "unconfirmed"
    ]
    if unconfirmed:
        raise UnconvertibleRecordError(
            f"{path}: resolves {', '.join(map(str, unconfirmed))} as `unconfirmed`, a state "
            "fr no longer has and that has no honest equivalent — close each as fixed, "
            "refuted or out-of-scope by hand, then re-run `fr migrate artifacts --yes`. "
            "Left on version 6, byte-identical."
        )
    body = {
        **data,
        "journal": [
            {k: v for k, v in item.items() if k != "delegated"}
            for item in data.get("journal") or ()
        ],
    }
    if not data.get("journal"):
        body.pop("journal", None)
    if not _is_v7(body):
        raise UnconvertibleRecordError(
            f"{path}: does not read as a version-7 record once "
            "`delegated` is dropped. Left on version 6, byte-identical."
        )
    if body != data:
        write_text_atomic(path, yaml.safe_dump(body, sort_keys=False, allow_unicode=True))


RECORD_CONTRACT_MIGRATION = SchemaMigration(
    kind="record",
    from_version=6,
    to_version=7,
    fn=drop_removed_fields,
    description="record: drop `JournalItem.delegated`; refuse an `unconfirmed` resolution",
)

MIGRATIONS.register(RECORD_CONTRACT_MIGRATION)
