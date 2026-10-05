# Journal: 2026-10-04-drive-merge-train

<!-- fr:journal kind=discovery scope=plan id=p1-visual-evidence-tests-fail-under-xdist created=2026-10-04T08:58:53+00:00 phase=1 -->
### p1-visual-evidence-tests-fail-under-xdist · discovery · tests/unit/test_run_evidence_visual.py (and a few timing tests) fail in the full -n auto suite but pass alone (phase 1)

The full suite on this host fails 4-7 tests (test_run_evidence_visual.py transcript-witness tests; once also test_records_commit stuck-lock, test_statusline_segment budget, test_sentinel_liveness) in two consecutive runs, yet all pass when run as those files alone (113 passed). They depend on harness transcripts/wall-clock and the host was loaded (suite took ~35 min). None touch the files this phase changed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

train_line and summary_line were small additions beside existing helpers; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

A two-line subclass and one raise site; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

One loop printing train_line before the actions; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

A fragment file and acceptance rows; no code to clean.

<!-- fr:journal kind=finding scope=plan id=rv-stops-api created=2026-10-04T09:02:20+00:00 phase=1 state=open review_scope=in -->
### rv-stops-api · finding [open] (reviewer: in scope) · _stops_train took two optional keywords and silently returned False when given neither (phase 1)

triage_batch_cmd.py _stops_train(*, attempt=None, error=None). The signature allowed a call that meant nothing.

<!-- fr:journal kind=finding scope=plan id=rv-merge-batch-tuple created=2026-10-04T09:02:20+00:00 phase=1 state=open review_scope=in -->
### rv-merge-batch-tuple · finding [open] (reviewer: in scope) · _merge_batch returned a positional 4-tuple across ten return sites (phase 1)

The trailing `stops` flag was easy to get wrong when a return site is edited.

<!-- fr:journal kind=finding scope=plan id=rv-queued-failing-unwarned created=2026-10-04T09:02:20+00:00 phase=1 state=open review_scope=in -->
### rv-queued-failing-unwarned · finding [open] (reviewer: in scope) · A failing PR behind a stopped train was queued silently, so its failure was reported only once it led (phase 1)

_walk_train checked the stop before checking failing. Before this change every failing PR was warned on the first pass.

<!-- fr:journal kind=finding scope=plan id=rv-race-refusal created=2026-10-04T09:02:20+00:00 phase=1 state=open review_scope=out -->
### rv-race-refusal · finding [open] (reviewer: out of scope) · A head moving between _open_head and pr_merge surfaces as a plain forge refusal and is stepped over (phase 1)

batch_merge.py _merge's pr_merge(head_sha=...) refusal path behaved the same before this change. It is harmless, because the next candidate is re-checked and updated, which stops the train.

<!-- fr:journal kind=review scope=plan id=rv-review-phase1 created=2026-10-04T09:02:20+00:00 phase=1 -->
### rv-review-phase1 · review · Independent code review of phase 1: approve, 4 Minor findings (3 in scope, fixed; 1 out of scope) (phase 1)

A dispatched reviewer read the full diff (8cec6f9d7..bd9cacc1d) of packages, plugins, tests and .changes against spec R1–R9 and the §B table, and ran the three touched test files (176 passed). It confirmed the walk order and repo independence, warn-once, the stop table, HeadMovedError compatibility with merge_one and batch merge (R8), the _unlanded/settle/rg-1 interplay without double counting, the output, the mirrors, the fragment and the name-anchored acceptance refs. Findings: rv-stops-api, rv-merge-batch-tuple, rv-queued-failing-unwarned (in scope, fixed in 4bd3d39f9 with a new failing-first test), and rv-race-refusal (out of scope).

<!-- fr:journal kind=finding scope=plan id=rv-stops-api-resolved created=2026-10-04T09:02:20+00:00 phase=1 state=fixed resolves=rv-stops-api -->
### rv-stops-api-resolved · finding [fixed] · resolves rv-stops-api: _stops_train took two optional keywords and silently returned False when given neither (phase 1)

_stops_train now takes one argument, MergeAttempt | MergeStopError.

<!-- fr:journal kind=finding scope=plan id=rv-merge-batch-tuple-resolved created=2026-10-04T09:02:20+00:00 phase=1 state=fixed resolves=rv-merge-batch-tuple -->
### rv-merge-batch-tuple-resolved · finding [fixed] · resolves rv-merge-batch-tuple: _merge_batch returned a positional 4-tuple across ten return sites (phase 1)

_merge_batch returns a _MergeOutcome NamedTuple (line, acted, in_flight, stops).

<!-- fr:journal kind=finding scope=plan id=rv-queued-failing-unwarned-resolved created=2026-10-04T09:02:20+00:00 phase=1 state=fixed resolves=rv-queued-failing-unwarned -->
### rv-queued-failing-unwarned-resolved · finding [fixed] · resolves rv-queued-failing-unwarned: A failing PR behind a stopped train was queued silently, so its failure was reported only once it led (phase 1)

A failing member is stepped over and warned wherever it sits. Pinned by test_a_failing_member_behind_the_stop_is_warned_and_stepped_over (red first). Spec §A step 3 is updated to match.

<!-- fr:journal kind=finding scope=plan id=rv-race-refusal-resolved created=2026-10-04T09:02:20+00:00 phase=1 state=open resolves=rv-race-refusal out_of_scope=true -->
### rv-race-refusal-resolved · finding [out-of-scope] · resolves rv-race-refusal: A head moving between _open_head and pr_merge surfaces as a plain forge refusal and is stepped over (phase 1)

The pr_merge race predates this change and is self-correcting, because the next candidate is updated, which stops the train.

<!-- fr:journal kind=finding scope=plan id=rv-race-refusal-resolved-2 created=2026-10-05T10:49:58+00:00 state=open resolves=rv-race-refusal tracked_by=#962 -->
### rv-race-refusal-resolved-2 · finding [deferred → #962] · resolves rv-race-refusal: A head moving between _open_head and pr_merge surfaces as a plain forge refusal and is stepped over

Filed at closeout as #962.
