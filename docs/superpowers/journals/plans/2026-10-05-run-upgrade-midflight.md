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

<!-- fr:journal kind=decision scope=plan id=p2-implement-return-rule created=2026-10-05T21:57:21+00:00 phase=2 -->
### p2-implement-return-rule · decision · Clause 2 reads every other phase/N unit's returned, the reviewer check's own implementer rule (phase 2)

`implement_returned` takes the latest `returned` over every `phase/N/*` unit except the review unit being resolved — the same "every other member of the phase" rule `_verify_reviewer` uses for implementers — so the bound needs no knowledge of which member id is the implement one. Adoption identifies the review member as the group member whose `evidence` declares `review`.

<!-- fr:journal kind=decision scope=plan id=p2-adopt-records-only-done created=2026-10-05T21:57:21+00:00 phase=2 -->
### p2-adopt-records-only-done · decision · Adoption records only inferred-done review units; a not-inferable one stays absent (pending) with a note (phase 2)

A review member adoption cannot infer is left unrecorded, exactly as before (the next `advance` dispatches it), rather than written as an explicit `pending` unit. The cursor moves past the group only when it was ON the group (the all-complete fallback) and every member of every non-manual phase is done; an unticked manual phase keeps it on the group.

<!-- fr:journal kind=discovery scope=plan id=p2-adopted-implement-debt created=2026-10-05T21:57:21+00:00 phase=2 -->
### p2-adopted-implement-debt · discovery · Adopted implement-phase units already show `unevidenced` debt for `visual` under fr-goal (phase 2)

Pre-existing, not introduced here: an adopted `phase/N/implement-phase: done` unit carries no evidence, and fr-goal's implement-phase declares `visual`, so `fr run status` prints "unevidenced (predates the evidence gate)" for it. R9 only exempts historical REVIEW units; the R9 test asserts on the review unit's block only.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-05T21:57:21+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the bound landed as a new pure module (fr/run/historical.py) and the findings witness string was extracted there as findings_witness on first use; nothing left duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-05T21:57:21+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

adoption reuses the bound, reviews_phase, phase_finding_states, unauthorized_fixes and findings_witness directly; no copy of the gate's logic was made, so nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-05T22:13:30+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · deliver checks only the ## Historical reviews heading; a live PR body can drop the list the trust model rests on (phase 2)

missing_sections checks heading lines only, so `## Historical reviews` followed by `None.` passed deliver.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-05T22:13:30+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · clause 1 trusts an unvalidated cursor `started`; moving it lets a self-written review pass with no reviewer dispatch (phase 2)

The accepted-case fixture itself moved started into the future. Fix: refuse a started later than now, and a review unit this cursor briefed before started. Also the background security scan's authorization-bypass flag.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-05T22:13:30+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · clause 2 accepts a review stamped in the same second as the implement return (phase 2)

`created < returned` let a tie through, unlike clause 1's fail-closed tie.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-05T22:13:30+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · refusal tests other than clause 1 do not assert the cursor is unchanged; no tests for unparseable/offset stamps (phase 2)

Test quality: refusals only checked exit code and message.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-05T22:13:30+00:00 phase=3 state=open review_scope=out -->
### p2-r5 · finding [open] (reviewer: out of scope) · spec's supersede ordering (carry after inference) hides carried implement returns from clause 2 at adoption (phase 3)

Not caused by phase 2 (adopt_run has no supersede yet). Phase 3 must check clause 2 against the carried attempts; spec §D amended to say so.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-05T22:13:30+00:00 phase=2 -->
### p2-review-1 · review · phase 2 review: p2-r1..p2-r4 (in), p2-r5 (out, filed to phase 3) (phase 2)

Independent adversarial reviewer checked the historical bound, the by-hand branch (no regression for other reviewer values; flat unit refused), adoption inference (open findings and unauthorized fixes excluded, identical findings witness, manual/incomplete phases skipped), the PR-body requirement and status/check debt. Raised p2-r1..p2-r4 in scope, p2-r5 out of scope (phase 3).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-05T22:13:30+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: deliver checks only the ## Historical reviews heading; a live PR body can drop the list the trust model rests on (phase 2)

historical_review_lines is the one spelling pr_body renders and _deliver_pr_gate now requires line by line on the live PR; test_deliver_refuses_a_live_body_that_keeps_the_heading_but_drops_the_list fails without the fix.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-05T22:13:30+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: clause 1 trusts an unvalidated cursor `started`; moving it lets a self-written review pass with no reviewer dispatch (phase 2)

historical_review_refusal refuses a started later than now and a review unit briefed before started (review_dispatched from the unit's last attempt). Fixture rebuilt as a supersede-shaped cursor with every time in the past; tests test_a_started_in_the_future_is_refused and test_a_review_briefed_before_the_run_started_is_refused. Residual (a cursor edited to a past started and the unit re-briefed) is stated in the module docstring and spec §D as a visible tracked diff plus the PR-body list.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-05T22:13:30+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: clause 2 accepts a review stamped in the same second as the implement return (phase 2)

Clause 2 refuses on `<=`; test_a_review_in_the_same_second_as_the_implement_return_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-05T22:13:30+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: refusal tests other than clause 1 do not assert the cursor is unchanged; no tests for unparseable/offset stamps (phase 2)

Every by-hand refusal test now asserts no evidence was written and the unit is still running (_unchanged); pure tests for an unparseable created (fails closed) and offset stamps (compared as instants).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-05T22:13:30+00:00 phase=2 state=open resolves=p2-r5 out_of_scope=true -->
### p2-r5-resolved · finding [out-of-scope] · resolves p2-r5: spec's supersede ordering (carry after inference) hides carried implement returns from clause 2 at adoption (phase 2)

Not caused by phase 2 — supersede does not exist yet. Spec §D amended so phase 3's inference checks clause 2 against the old cursor's implement attempts; phase 3 is briefed with it.
