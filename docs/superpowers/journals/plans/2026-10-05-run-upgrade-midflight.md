# Journal: 2026-10-05-run-upgrade-midflight

<!-- fr:journal kind=discovery scope=plan id=p1-read-callsite-audit created=2026-10-05T21:30:22+00:00 phase=1 -->
### p1-read-callsite-audit · discovery · Audit of _resolve_manifest_for_state call sites (R4) (phase 1)

Call sites of `_resolve_manifest_for_state`: `_unevidenced_units` (read-only report, used by status and check), `_advance_chain`, `_advance_step`, `_resolve_body`, `_next_unit`, `_advance_after_record`, `claim_cmd` (all mutating, kept strict), `_idle_reading` (kept strict: a drifted cursor is `not-advanceable`, which is the liveness answer), and `gates_cmd` (switched to `_resolve_manifest_for_read`). `status` and `cost` never resolved the manifest: `status` now calls the lenient resolver for its single warning (and prints a refusal such as a schema mismatch as a warning, still exit 0, since it is how an operator finds out); `check` calls it likewise, exit codes unchanged. `_unevidenced_units` now uses a schema-checked-only resolve (`_resolve_manifest_checked_schema`) so the evidence report survives a step-list drift instead of silently going empty. `cost` needs no change.

<!-- fr:journal kind=decision scope=plan id=p1-drift-error-subclass created=2026-10-05T21:30:22+00:00 phase=1 -->
### p1-drift-error-subclass · decision · StepDriftError subclass distinguishes drift from schema mismatch (phase 1)

`_StepDriftError(RunStateError)` is raised by `_check_step_drift`, so the read resolver downgrades exactly the drift refusal and still raises on a schema-version mismatch. Shared added/removed computation is `fr.run.reshape.diff_ids`, used by reshape, `_check_step_drift` (top-level and member diffs) and the reshape command.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-05T21:30:22+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

skeleton only: a stub returning its input, nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-05T21:30:22+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the command is a thin wrapper over the pure reshape; the shared diff helper was already extracted in P1.T2.S3

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-05T21:30:22+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

added one small lenient resolver beside the strict one; nothing duplicated to clean
