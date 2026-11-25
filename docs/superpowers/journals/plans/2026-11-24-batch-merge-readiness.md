<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-batch-merge-readiness

<!-- fr:journal kind=decision scope=plan id=p1-readiness-module-imports created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-readiness-module-imports · decision · readiness imports wave_queue; wave_queue imports readiness lazily (phase 1)

`fr.triage.readiness` needs `QueueSnapshot`, `base_refusal`, `is_deferred` and the new
`queue_held_reason` from `wave_queue`, and `wave_queue._ready` / `plan_queue` call
`batch_readiness`. So readiness imports wave_queue at module level and wave_queue
imports readiness inside the two functions (and under TYPE_CHECKING for
`QueuePlan.readiness`), the same lazy pattern batch_drive and wave_queue already use.

<!-- fr:journal kind=decision scope=plan id=p1-livepr-url created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-livepr-url · decision · LivePr gains url so R6's links need no host guess (phase 1)

R6 links the PR and its checks tab; `LivePr` carried no URL. Both Snapshot builders
now fill `LivePr.url` from the batch PR's facts; `fact_cursors` (in readiness.py)
fills `Snapshot.cursors` the same way for both builders.

<!-- fr:journal kind=decision scope=plan id=p1-queue-held-verdict created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-queue-held-verdict · decision · Queue held means another scope holds the hold, or this scope's open queue is halted (phase 1)

R5's first verdict reads `wave_queue.queue_held_reason`: the R31 hold of another scope
(`held_by_other`, now shared with `_held`) or the `live_halt` of this scope's open
queue. It never changes `admits`, which stays the queue's own entry rule.

<!-- fr:journal kind=discovery scope=plan id=p1-test-worlds-default-delivered created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-test-worlds-default-delivered · discovery · Every queue and drive test world now defaults to a delivered run (phase 1)

83 existing tests assumed approved + green merges. Their snapshot helpers (planner,
operator view, batch_drive, draft_red), the board fixtures (`DELIVERED` in
triage_board_fixtures) and the drive command's World/DriveCheckout (a delivered PR
head serves one `deliver: done` cursor; `world.pr(..., delivered=False)` opts out)
now default to delivered, so each still tests what it did; new tests cover the hold.

<!-- fr:journal kind=discovery scope=plan id=p1-batch-drive-at-budget created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-batch-drive-at-budget · discovery · batch_drive.py sits exactly at its 2275-line budget (phase 1)

`_member_reports` now reads `batch_readiness`, and `Snapshot.cursors` / `LivePr.url`
were added; comments were trimmed to stay at 2275. Phase 2's board work in batch_drive
has no headroom: put it in readiness.py or kanban.

<!-- fr:journal kind=discovery scope=plan id=p1-cursor-unread-not-cached created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-cursor-unread-not-cached · discovery · The driver no longer caches an unread cursor head (phase 1)

`_Driver.cursor_at` used to cache `None` for a head the clone could not reach, so a
head fetched later in the same process was never read again. It now caches only a
`read` answer (a commit never changes); an `unread` one is asked again next pass.

<!-- fr:journal kind=discovery scope=plan id=p1-facts-fixtures-regenerated created=2026-11-25T00:48:18+00:00 phase=1 -->
### p1-facts-fixtures-regenerated · discovery · Facts schema 17 regenerates six committed scenario fixtures (phase 1)

`tests/scenarios/fixtures/*-facts.json` carry the facts stamp; their generators
(`make_*_facts.py`) were re-run, so only the `schema` line moved.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-25T00:48:18+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke task: one docstring module, one test and a fragment, nothing to clean

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-25T02:01:21+00:00 phase=1 -->
### p1-review · review · Phase 1 code review: merge gate sound (no undelivered batch is readied, admitted or merged); 7 in-scope findings (phase 1)

Reviewer checked R2 (no bypass of batch_readiness: _ready, _entries re-filter, _queue_entry pr_ready, queue_exec pr_merge, foreground batch merge), R1 (fold_positions fails closed, distinct reasons, live pr_view head vs facts head_oid), R5 order and admits = old _ready + delivered, R3 voiding sha from ApprovalEvent.voided_at, R12 wording, FACTS_READS 3-17 with cursor_read None reading unread, and readiness.py purity. All held. Findings p1-r1..p1-r7 below.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · `fr triage batch merge <id>` refuses an approved-but-undelivered batch as "not approved", because approved-not-delivered now lands in Pass.awaiting (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · _member_reports no longer reports a gated approved PR as held/awaiting while CI is pending or the queue is held (reads r.kind, not the gate) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · in_queue_order leaves an admitted batch absent from the plan's order (e.g. ejected) reading "Approved, merges next" (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · _voided_sha reads a stale voided_at for a Held verdict, so a re-labelled PR still says "Approval voided ... re-label" (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · no driver-level test that facts head_oid != live pr_view head holds the PR (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · no test that an old-facts PR (deliver-done cursor, cursor_read None) reads not delivered (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-25T02:01:21+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · the approve-pr Need still asks to label a green PR approved-fr while its run has not delivered (contradicts R4, invites an approval R3 voids) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: `fr triage batch merge <id>` refuses an approved-but-undelivered batch as "not approved", because approved-not-delivered now lands in Pass.awaiting (phase 1)

276f12b64: readiness.merge_refusal decides 'not approved' from the verdict; an approved hold names its readiness reason. Test test_triage_batch_merge.py::test_a_named_approved_batch_whose_run_has_not_delivered_is_held_for_that_reason.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: _member_reports no longer reports a gated approved PR as held/awaiting while CI is pending or the queue is held (reads r.kind, not the gate) (phase 1)

d8d17cd75: _member_reports holds an approved PR when not delivered or readiness.gated(...), whatever CI/queue state. Test test_triage_readiness_queue.py::test_the_driver_holds_a_gated_approved_pr_for_devops_whatever_its_ci.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: in_queue_order leaves an admitted batch absent from the plan's order (e.g. ejected) reading "Approved, merges next" (phase 1)

d8d17cd75: new not-queued verdict (eject reason at live head, else 'not in the queue this pass'). Tests test_triage_readiness.py::test_an_admitted_batch_outside_the_plans_order_is_not_merges_next and ::test_an_ejected_batch_outside_the_order_reads_its_eject_reason.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: _voided_sha reads a stale voided_at for a Held verdict, so a re-labelled PR still says "Approval voided ... re-label" (phase 1)

d8d17cd75: _voided_sha returns None for Held. Test test_triage_readiness.py::test_a_held_approval_never_reads_an_older_void.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: no driver-level test that facts head_oid != live pr_view head holds the PR (phase 1)

2241610b9: test_triage_batch_drive_cmd.py::test_a_pr_whose_head_moved_since_the_cursor_was_read_is_held_with_both_heads (no queue-open, no pr_ready, no merge, both heads named).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: no test that an old-facts PR (deliver-done cursor, cursor_read None) reads not delivered (phase 1)

2241610b9: test_triage_cursor_read.py::test_a_cursor_with_no_read_status_is_never_delivered and ::test_a_schema_16_facts_files_delivered_cursor_is_not_admitted.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-25T02:01:21+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: the approve-pr Need still asks to label a green PR approved-fr while its run has not delivered (contradicts R4, invites an approval R3 voids) (phase 1)

c2549b27a: needs_you reads readiness.snapshot_readiness over the board's snapshot; no label Need while undelivered, R12 Need for a PR with no cursor. Test test_merge_train_label_board.py::test_a_green_pr_whose_run_has_not_delivered_is_never_asked_for_the_label.
