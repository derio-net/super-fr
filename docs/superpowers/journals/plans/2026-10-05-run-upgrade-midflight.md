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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-05T21:35:14+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · fr run reshape's schema-mismatch refusal never names fr run adopt --supersede (R2) (phase 1)

reshape_cmd pre-checked the schema with _resolve_manifest_checked_schema, whose refusal says 'start a new run', so reshape()'s rule 1 was unreachable from the CLI and its message lacked --supersede too.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-05T21:35:14+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · fr run check's drift warning (R4) is untested though the row's notes claim it (phase 1)

Only gates and status had tests; a regression in check (refusing, or warning twice) would go unseen.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-05T21:35:14+00:00 phase=1 state=open review_scope=out -->
### p1-r3 · finding [open] (reviewer: out of scope) · fr pickup's _run_unit_record uses the strict resolver and swallows the error on a drifted cursor (phase 1)

pickup_cmd.py:247 drops the record brief silently on a drifted cursor. Pre-existing; R4 covers fr run read-only commands only (spec Non-goals).

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-05T21:35:14+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: p1-r1, p1-r2 (in), p1-r3 (out) (phase 1)

Independent reviewer checked reshape rules 1-5, the write path, the resolver call-site audit (no mutating command lenient), single warnings, artifact shape unchanged. Raised p1-r1, p1-r2 (in scope) and p1-r3 (out of scope).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-05T21:35:14+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: fr run reshape's schema-mismatch refusal never names fr run adopt --supersede (R2) (phase 1)

reshape_cmd now resolves the shape by name and lets reshape() own rule 1, whose message names `fr run adopt <plan-dir> --supersede`; unit test tightened, CLI test test_reshape_across_a_schema_change_refuses_naming_supersede added (exit 2, bytes and commit count unchanged).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-05T21:35:14+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: fr run check's drift warning (R4) is untested though the row's notes claim it (phase 1)

Added test_check_answers_a_drifted_cursor_with_one_warning and cited it on run-read-drifted-cursor.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-05T21:35:14+00:00 phase=1 state=open resolves=p1-r3 out_of_scope=true -->
### p1-r3-resolved · finding [out-of-scope] · resolves p1-r3: fr pickup's _run_unit_record uses the strict resolver and swallows the error on a drifted cursor (phase 1)

Not caused by this change: fr pickup predates it and is not an `fr run` read-only command; listed in the spec's Non-goals. Reshape removes the drift it trips on.
