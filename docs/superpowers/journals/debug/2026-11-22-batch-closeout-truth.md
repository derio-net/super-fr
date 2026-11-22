<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-batch-closeout-truth

<!-- fr:journal kind=hypothesis scope=debug id=0c4691e1db5c created=2026-11-22T21:14:28+00:00 -->
### 0c4691e1db5c · hypothesis · The four members share close-out bookkeeping but trace to four separate defects

Read against origin/main 0bca17ec3. (1) #1496: batch_closeout_cmd computes closeout_owed (which skips any batch with a closeout event) before narrowing to mine.planned (triage_batch_cmd.py:3186-3189), so the marker's own --branch resume always prints 'nothing to close out'. (2) #1497: _collected_step returns closeout-needs-review whenever review_reasons is non-empty (batch_drive.py:1168) and no approval is collected or consulted for a collected close-out PR. (3) #1494: the finish step closes batch_item_id and closeout_item_id only (batch_drive.py:2097), never the collected_item_id session. (4) #1569: (a) any deterministic step failure, including the artifact-migration gate's refusal on the default branch, becomes a durable closeout_hold; (b) open_markers excludes closed markers, so a --branch retry on a held branch creates a fresh marker while the closed one sees a live PR on its branch and reports closeout-reopened (batch_drive.py:1934). Verdict: not one root cause.

<!-- fr:journal kind=decision scope=debug id=b92e0a52b993 created=2026-11-22T21:15:04+00:00 decided_by=operator -->
### b92e0a52b993 · decision · Fix all four defects in the one batch PR

Operator chose to keep the batch's single PR: one failing test per defect, then each fix.

<!-- fr:journal kind=finding scope=debug id=rv-1497-sec created=2026-11-22T21:29:03+00:00 state=fixed -->
### rv-1497-sec · finding [fixed] · Approval release hardened after an automated security review of the #1497 commit

Three findings, all fixed: (1) a First verdict could release a held PR the pass never recorded; now only Approved does. (2) Required checks were fetched only when the live head was the recorded one; now for every open head. (3) The verdict read one anchor batch's events; now every approval event of the PR across the marker's batches, oldest first, on both the record and the read side.

<!-- fr:journal kind=decision scope=debug id=51531ee4c24d created=2026-11-22T21:29:28+00:00 -->
### 51531ee4c24d · decision · #1496 keeps R15(3); the hand-back brief says rebase (operator's choice in the question round)

The hand-back brief told the session to merge origin/<base> in, which can never satisfy exit-gates R15(3) (the recorded head is the only commit past the base). The operator chose, in this session's question round, to keep the trust anchor: the brief tells the session to rebase its one commit and force-push with lease, then re-record. A merged-in head stays closeout-needs-review, which approved-fr (#1497) releases. fr could not verify the answer from the transcript, so this entry does not claim answered_by operator.

<!-- fr:journal kind=repro scope=debug id=036d91903681 created=2026-11-22T21:47:21+00:00 -->
### 036d91903681 · repro · Four reproductions, each a failing test first

#1494 test_gh1494_the_collected_closeout_session_closes_with_its_last_finished_batch (no close for the collected item); #1497 test_gh1497_an_approved_held_closeout_pr_is_merged_at_the_approved_head (Snapshot had no approval for a close-out PR); #1496 test_gh1496_the_markers_own_session_re_records_a_handed_back_head (second run printed 'nothing to close out'); #1569 test_gh1569_a_branch_retry_on_an_ended_closeout_is_refused_with_the_retry_command and test_gh1569_no_collected_closeout_starts_while_the_repos_artifacts_await_a_release.

<!-- fr:journal kind=root-cause scope=debug id=3316c050927b created=2026-11-22T21:47:25+00:00 -->
### 3316c050927b · root-cause · Four defects in the collected close-out's bookkeeping, one per member

#1496: closeout_owed skips a batch whose close-out event names the resuming marker, before the command narrows to that marker's planned batches; and the hand-back brief asked for a merge, which exit-gates R15 (3) can never auto-merge. #1497: _collected_step never consulted an approval and none was collected for a close-out PR. #1494: drive_pass step 5 closed the batch and per-batch close-out ids, never the collected item. #1569: any archive refusal was a durable hold, the migration gate's included; and --branch on a closed marker updated that closed marker, which the driver then read as closed and reopened.

<!-- fr:journal kind=finding scope=debug id=fix-closeout-truth created=2026-11-22T21:47:28+00:00 state=fixed -->
### fix-closeout-truth · finding [fixed] · Fixed test-first, one commit per member

#1494: the finish step also closes the collected item once its PR merged and every batch it planned or carried is finished. #1497: close-out PR approvals are settled like a batch PR's and a recorded Approved verdict merges a held PR at its live head (hardened by rv-1497-sec). #1496: closeout_owed takes resuming=<branch>; the hand-back brief asks for a rebase and --force-with-lease. #1569: release_pending classifies the migration refusal as transient; the driver's closeout_waits (pending_migration on the clone) defers the close-out and warns once; --branch on an ended marker is refused with the retry command. Module budgets raised (+50/+75), split deferred to #1516.
