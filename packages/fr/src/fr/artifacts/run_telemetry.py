"""The `run` kind's 2 → 3 migration: measured tokens (spec §5.C).

`PhaseAccounting` gained `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens` and `output_tokens`, and `RunState` is
`extra="forbid"`, so a cursor written by this fr raises `RunStateError` in any
fr that predates them. That makes it a **shape change** under
`.claude/rules/artifact-versioning.md` — "optional and defaulted" buys nothing
against a closed-world reader — so it ships a stamp bump (in
`fr.artifacts.registry`, and nowhere else), the migration below, and an
updated structure validator, all in one PR. The package `__init__` imports this
module: a migration nobody imports never runs.

**It rewrites no body**, for the same reason the 1 → 2 migration did not: the
new fields default to absent, and absent is precisely what every v2 cursor
already means — *nobody measured this unit*. Writing zeros instead would
manufacture a measurement that was never taken, which is the exact confusion
between "no measurement" and "a measured zero" that these fields are `None`-
defaulted to prevent. So the whole of `fn` is the shared guard: refuse to
certify a cursor fr cannot read.
"""

from __future__ import annotations

from fr.artifacts.run_cursor import cursor_guard
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-measured-tokens"

RUN_TELEMETRY_MIGRATION = SchemaMigration(
    kind="run",
    from_version=2,
    to_version=3,
    fn=cursor_guard(3),
    description=(
        "run cursor: add measured token accounting (V2 telemetry) — stamp only, no body change"
    ),
)

MIGRATIONS.register(RUN_TELEMETRY_MIGRATION)
