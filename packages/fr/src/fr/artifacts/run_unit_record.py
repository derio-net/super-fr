"""The `run` kind's 4 → 5 migration: one record per unit (spec
`2026-09-20-unit-record-unification-design.md` §4.F).

`StepRecord.items`, `StepRecord.dispatch` and the top-level
`RunState.accounting` collapse into one `StepRecord.units` map. **This is the
first `run` migration that rewrites a body** — 1 → 2, 2 → 3 and 3 → 4 were all
stamp-only — and a body rewrite can go wrong in two ways a stamp cannot:

1. **It can half-write.** So the v5 body is built entirely in memory by the
   pure `fr.run.legacy.v4_to_v5` and written ONCE, through
   `fr.artifacts.atomic.write_text_atomic`. Every refusal fires before a byte
   moves, so a cursor fr cannot convert — unreadable, carrying a partial
   measurement, or carrying cost for a unit no step records — is left
   **byte-identical** and reported as that one artifact's failure while every
   other cursor migrates (runner invariant 3).
2. **It can be interrupted between the body and the stamp.** `fn` writes the
   body; the runner writes the stamp afterwards. A crash in between leaves a v5
   body under `schema_version: 4`, and the frozen v4 reader is `extra="forbid"`
   and has never heard of `units` — so a naive `fn` would refuse that file on
   every later run, forever, and it is by construction the cursor of a run that
   was in flight. `fn` therefore accepts a body that is ALREADY wholly v5 and
   lets the runner finish stamping it.

**It reads with the frozen legacy models**, like every other hop
(`fr.artifacts.run_cursor`). Case 2 above asks "is this already a v5 body?",
which the v5 model answers — and since run 6 -> 7 removed fields from the live
model, that is the frozen `fr.run.legacy.RunStateV6` (a superset of v5 and v6),
never the live one (spec `2026-09-25-lean-cost-aware-process-design` §5.B.4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-unit-record"

__all__ = [
    "MIGRATION_NAME",
    "RUN_UNIT_RECORD_MIGRATION",
    "UnconvertibleRunCursorError",
    "rewrite_to_unit_records",
]

_LEGACY_STEP_KEYS = ("items", "dispatch")


class UnconvertibleRunCursorError(UnreadableRunCursorError):
    """A v4 cursor fr READ fine and still will not rewrite, because a faithful
    v5 body does not exist for it (`fr.run.legacy.RunMigrationError`).

    A subclass of the unreadable error so one `except` covers "this cursor was
    left alone", while the message keeps the two apart: one says fix the YAML,
    the other names the figure fr refused to invent.
    """


def _carries_legacy_maps(data: dict[str, Any]) -> bool:
    if "accounting" in data:
        return True
    steps = data.get("steps")
    if not isinstance(steps, dict):
        return False
    return any(
        isinstance(record, dict) and any(key in record for key in _LEGACY_STEP_KEYS)
        for record in steps.values()
    )


def _already_unit_records(text: str, data: object) -> bool:
    """Is `text` a body this migration already wrote — wholly v5, stamp aside?

    The crash-window case in the module docstring. Both halves are required: no
    legacy map anywhere (so `units` beside `accounting`, a half-merged file, is
    NOT accepted), and the live model reads it. The stamp is ignored on
    purpose — it is the one thing known to be behind.
    """
    from fr.run.legacy import parse_run_state_v6
    from fr.run.model import RunStateError

    if not isinstance(data, dict) or _carries_legacy_maps(data):
        return False
    try:
        parse_run_state_v6(text)
    except RunStateError:
        return False
    return True


def is_unit_record_body(text: str) -> bool:
    """Does `text` parse as a cursor wholly in the v5 shape, stamp aside?

    The public face of `_already_unit_records`, for the 5 -> 6 hop's guard
    (`fr.artifacts.run_main_session`). Answered by the frozen
    `fr.run.legacy.RunStateV6`: run 6 -> 7 removed fields from the live model,
    so the live model can no longer read a v5 body that carries them.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return _already_unit_records(text, data)


def rewrite_to_unit_records(path: Path) -> None:
    """Rewrite the run cursor at `path` from the v4 shape to the v5 one.

    Parses first and refuses rather than certifying a cursor it cannot read
    (the `run_provenance` invariant); writes nothing at all when the rewrite
    changes nothing, because this replaces bytes someone else authored and is
    not a YAML normaliser; and never touches the stamp, which is the runner's.

    Imports are inside the function: `fr.artifacts` is imported at CLI entry
    before every command, and must not drag the run models in with it.
    """
    from fr.run.legacy import RunMigrationError, parse_run_state_v4, v4_to_v5
    from fr.run.model import RunStateError, dump_cursor_yaml

    try:
        text = path.read_text()
        parse_run_state_v4(text)
    except (RunStateError, OSError) as e:
        try:
            data = yaml.safe_load(text) if isinstance(e, RunStateError) else None
        except yaml.YAMLError:
            data = None
        if data is not None and _already_unit_records(text, data):
            return
        raise UnreadableRunCursorError(
            f"{path}: not a readable run cursor, so fr will not rewrite it to version 5 "
            f"({e}). Fix the file by hand — it is left byte-identical on its current "
            f"version and will be retried."
        ) from e

    data = yaml.safe_load(text)
    try:
        converted = v4_to_v5(data)
    except RunMigrationError as e:
        raise UnconvertibleRunCursorError(
            f"{path}: fr will not rewrite this run cursor to version 5 — {e}"
        ) from e

    if converted == data:
        return
    write_text_atomic(path, dump_cursor_yaml(converted))


RUN_UNIT_RECORD_MIGRATION = SchemaMigration(
    kind="run",
    from_version=4,
    to_version=5,
    fn=rewrite_to_unit_records,
    description="run cursor: one record per unit — rewrites the body (`items`, `dispatch` "
    "and `accounting` fold into `units`); a cursor it cannot convert is left untouched",
)

MIGRATIONS.register(RUN_UNIT_RECORD_MIGRATION)
