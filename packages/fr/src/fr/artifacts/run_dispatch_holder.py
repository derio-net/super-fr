"""The `run` kind's 3 → 4 migration: the dispatch-holder record (spec
`2026-09-20-dispatch-holder-identity-design.md` §4.A/§4.D).

`StepRecord` gained `dispatch`, and `RunState` is `extra="forbid"`, so a
cursor written by this fr raises `RunStateError` in any fr that predates the
field. That makes it a **shape change** under
`.claude/rules/artifact-versioning.md`: a stamp bump (in
`fr.artifacts.registry`, and nowhere else) plus the migration below, which the
package `__init__` imports — a migration nobody imports never runs.

**It rewrites no body, and that is the whole design** — same as the 1→2
migration in `fr.artifacts.run_provenance`, which this module is modelled on
line-for-line. The new field is optional and defaults to absent, which is
exactly what every v1, v2 and v3 cursor already means ("no dispatch recorded for
this step"), so there is nothing to translate; the runner writes the stamp
itself once `fn` returns. What is left for `fn` is the one decision a
stamp-only migration can still get wrong: stamping a file it cannot actually
read. A run cursor is git-tracked and hand-editable, and a truncated or
half-merged one that gets stamped `4` is *worse* than one left below — it now
claims a shape it does not have, and the migration will never look at it
again. So `fn` parses first and refuses, which the runner records as that one
artifact's failure (invariant 3): every other cursor still migrates, the bad
one stays unstamped, and the next run retries it.

That guard is `fr.artifacts.run_cursor.cursor_guard`, shared with the 1 -> 2
and 2 -> 3 migrations. This module used to carry its own copy, which read with
the LIVE run model; the copy went when the guard moved to the frozen legacy
reader (spec `2026-09-20-unit-record-unification-design.md` §4.F), because a
rule that has to be applied in three places is a rule that gets applied in two.
"""

from __future__ import annotations

from fr.artifacts.run_cursor import cursor_guard
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-dispatch-holder"

RUN_DISPATCH_HOLDER_MIGRATION = SchemaMigration(
    kind="run",
    from_version=3,
    to_version=4,
    fn=cursor_guard(4),
    description="run cursor: add the dispatch-holder record (`dispatch`) — stamp only, no "
    "body change",
)

MIGRATIONS.register(RUN_DISPATCH_HOLDER_MIGRATION)
