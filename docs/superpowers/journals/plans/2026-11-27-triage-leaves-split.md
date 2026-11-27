<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-triage-leaves-split

<!-- fr:journal kind=decision scope=plan id=p1-src-consumers-import-new-homes created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-src-consumers-import-new-homes · decision · src consumers import the moved names from their new homes; batch_drive still re-exports them (phase 1)

mypy strict (no implicit re-export) refused nine src modules that imported moved names
from `fr.triage.batch_drive` through the plain `# noqa: F401` re-export (30 errors). The
`X as X` spelling made ruff's isort split every alias into its own statement (+74 lines,
over the new budget). So `triage_batch_cmd`, `settle/managed`, `batch_merge`, `kanban`,
`operator_entries`, `queue_reports`, `readiness`, `views` and `wave_queue` now import those
names from `batch_drive_types`, `batch_drive_export` and `handback_rules` (import lines only,
R7). `batch_drive` keeps the plain re-export the spec names, so R6 holds and the tests (not
type-checked) keep importing from it (R9). The new import statements are one line each
where they fit, so `triage_batch_cmd.py` (held, budget 8320) shrinks to 8315 lines.
`docs/reference/cli.md` (covers `triage_batch_cmd.py`) got the same
`still true, module split only` stamp.

<!-- fr:journal kind=discovery scope=plan id=p1-unused-model-imports-dropped created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-unused-model-imports-dropped · discovery · four model imports batch_drive no longer used were dropped (phase 1)

After the hand-back move `batch_drive.py` no longer used `typing.Literal`,
`ArchiveConflictEvent`, `CloseoutHandbackEvent` or `ConflictEvent`; ruff removed them. No
module imports any of them from `batch_drive` (all import them from `fr.triage.model`).
An AST comparison against origin/main showed all 30 moved definitions byte-identical.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-stamp-prepended created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-docs-stamp-prepended · discovery · reviewed stamps were prepended, keeping the history (phase 1)

Each page's `reviewed:` got `2026-11-27 still true, module split only; ` prepended to its
existing note, the convention every earlier stamp on these pages follows.

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-not-completed created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-fast-tier-not-completed · discovery · the brief's fast tier selects 11421 tests and could not finish on the loaded host (phase 1)

`pytest --fr-scope origin/main -n 2` selects 11421 tests (the doc stamps pull in every
own_artifacts test, `triage_batch_cmd.py` fans out widely). At host load ~25-35 it ran about
25 tests a minute, and three attempts were killed from outside (SIGTERM, exit 144) within
minutes; the last was stopped by hand at about 300 tests, none failed. In its place, after the final
code commit: every triage batch/drive/kanban/views/readiness/wave_queue/operator/queue/handback
unit file, settle, import direction, the module budget, the explainers tripwire and
test_triage_batch_drive_cmd.py, 1985 passed. CI (`tests: ci`) is the suite evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T20:59:41+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

guard widening, a budget number, doc stamps and a fragment; no code was written that could be cleaned.
