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

<!-- fr:journal kind=review scope=debug id=0e3c68741a63 created=2026-11-22T21:53:36+00:00 -->
### 0e3c68741a63 · review · Independent adversarial review: approval path sound; 2 important and 3 nits fixed, 3 nits left

A separate reviewer read the branch's code and tests. Approval path: head binding, fork/foreign PRs, unrecorded First, cross-batch reads and gate order all held. Fixed: (important) the migration wait now reads the fetched origin/<default> in a scratch worktree, the tree the verb archives in, instead of the clone's working tree; (important) release_pending matches the gate's own first line only; (nit) an approval no longer releases a body whose Closes lines differ from the record; (nit) the approved head must equal the live head; (nit) the reopened close-out line says to merge or close it by hand. Left, named in the PR: the re-record trusts the forge's head at the verb's run (bounded by the archive-only, single-commit and Closes checks); a planned batch missing from the state keeps a collected session open; an anchor outside a --named selection is not settled (the PR stays held, safe).

<!-- fr:journal kind=finding scope=debug id=rv-1497-narrowed created=2026-11-22T21:55:19+00:00 state=fixed -->
### rv-1497-narrowed · finding [fixed] · An unreadable narrowing state no longer lets an approval skip the Closes check

Automated security review: review_reasons skips the body Closes comparison when the members' narrowing decisions cannot be read, so an approval released a body never compared with the record. That reason is now unreleasable too.

<!-- fr:journal kind=decision scope=debug id=1106d983ffb5 created=2026-11-23T09:21:50+00:00 -->
### 1106d983ffb5 · decision · Rebased onto the wave merge queue (#1602): each member checked against the new close-out code

Merged origin/main at v9.0.0-rc.1. Per member, against main's code:
#1497 NOT fixed by #1602: _collected_step still returns closeout-needs-review whenever review_reasons is non-empty and reads no approval (main batch_drive.py _collected_step). Scope change: the approval now uses the queue's own mechanism for non-batch entries, settle_entry_approval with QueueEntryRef(pr, kind=closeout), recorded on the queue's events and pinned to the patch-id (R12, R32), instead of approval events on the member batches; a recorded Approved admits the PR to the queue (Admitted) rather than an archive merge (R32: the driver no longer calls pr_merge). The per-batch helpers collected_anchor/collected_approval_events are removed. The Closes-lines and narrowing checks still hold an approved PR. The approved-head equality check is dropped: R12 deliberately keeps an approval across a diff-neutral move.
#1494 NOT fixed: main's finish step still closes only the batch and per-batch close-out ids. Kept as is; closeout-merged still archives every member and marks the marker merged under the queue.
#1496 NOT fixed: main's closeout_owed has no resume branch. Kept. Hand-back brief adapted: main still said 'merge origin/<base> in'; R16 adds the verb's migration commit, so it now asks for a rebase of the close-out's commits.
#1569 (a) PARTLY fixed by R16: the close-out migrates the stale artifacts it archives (the observed triage-pages case, the batch's own run cursor) before fr archive. The gate still refuses fr archive over any other stale artifact under placement repo (own_feature admits every path), so release_pending stays, and the driver's wait is narrowed to the stale artifacts R16 does not move (batch_closeout.unowned_stale over Worktree.stale_artifacts and archive_moves), so it never contradicts R16. (b) NOT fixed: --branch on an ended marker is still refused by this branch only.

<!-- fr:journal kind=finding scope=debug id=merge-queue-adapt created=2026-11-23T09:21:53+00:00 state=fixed -->
### merge-queue-adapt · finding [fixed] · Approval, wait and brief re-implemented for the queue; tests moved from archive actions to admissions

gh1497 tests now assert plan.admitted and the queue entry (_queued == closeout#900, no pr_merge, approval on the queue's events); the old 'approval of another head' test is removed (R12 allows a diff-neutral move); test_triage_batch_closeout gains unowned_stale. Module budgets on main moved to 8200/2250; this branch needs 8225/2275.

<!-- fr:journal kind=review scope=debug id=700cae263254 created=2026-11-23T09:41:10+00:00 -->
### 700cae263254 · review · Independent review of the queue adaptation: approval path sound; 1 important and 1 nit fixed

A separate reviewer read the merged branch. Sound: only trusted PRs reach _closeout_approval; settle_entry_approval filters events by PR and kind closeout; only a recorded Approved admits; Closes/narrowing reasons still hold; the queue builds and lands the approved head (pr_merge head_sha guard); dry runs write nothing; the closeout#<pr> key is shared with the unapproved admission by design. Fixed: (important) the migration wait now counts as blocked and shows a Need naming the file and the remedy, retried each pass, instead of one warn while the drive polled silently; (nit) a leftover closeout-wait worktree is removed before the read. Left: an approval is recorded even for a PR review_reasons would admit (benign); a dry run shows needs-review for a first label a --yes pass records (matches housekeeping); a writer error in _closeout_approval aborts the snapshot like _housekeeping_reads; the Closes reasons are matched by prefix, pinned by the two end-to-end tests.
