<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-acceptance-fragments

<!-- fr:journal kind=decision scope=plan id=plan-four-phases created=2026-11-12T00:29:22+00:00 -->
### plan-four-phases · decision · Four agentic phases, one row each; fold library first, then the migration and cutover together

Phase 1 lands the fold as a library nothing reads yet (risk first). Phase 2 cannot split the
migration from the reader cutover: moving the matrix kind's version makes this repo stale until it
is migrated. Phases 3 (amendments) and 4 (reports) depend only on phase 2. The planning-time row
acceptance-effective-matrix-fold (R17/R18) was added so the fold phase owns a row of its own.

<!-- fr:journal kind=discovery scope=plan id=runner-cannot-delete-artifact created=2026-11-12T00:29:22+00:00 phase=2 -->
### runner-cannot-delete-artifact · discovery · The migration runner re-stamps the migrated path after fn, so a migration cannot delete its own artifact (phase 2)

fr/artifacts/runner.py _apply_to_one always calls kind.write_version(path, ...) after fn returns.
Retiring the matrix kind needs a retiring step (no stamp, path must be gone, removal staged).
