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

<!-- fr:journal kind=decision scope=plan id=p2-others-refused-via-actions created=2026-11-25T03:08:29+00:00 phase=2 -->
### p2-others-refused-via-actions · decision · Refused close-out, archive and export candidates are read off the pass's own actions (phase 2) (phase 2)

drive_pass could not grow (batch_drive.py is at its budget), so readiness.refused_others reads the trust rules' refusals from the pass's actions: a candidate is told apart by which PR set (collected_prs, archives, export_prs) holds its number, never by the action text, and the action's detail is the reason. QueueSnapshot.refused (key -> reason) and refused_entries carry them; they are never entries, and wave_queue._base_needs skips them so a refused PR raises no queue Need.

<!-- fr:journal kind=decision scope=plan id=p2-queue-reports-moved created=2026-11-25T03:08:29+00:00 phase=2 -->
### p2-queue-reports-moved · decision · queue_reports and QUEUE_REPORT_KEY moved out of batch_drive to fr.triage.queue_reports (phase 2) (phase 2)

To add the refused hook inside batch_drive.py's 2275-line budget, an equal amount of code left it: the queue's report actions. views.py and the planner test import from the new module.

<!-- fr:journal kind=discovery scope=plan id=p2-board-facts-lack-others created=2026-11-25T03:08:29+00:00 phase=2 -->
### p2-board-facts-lack-others · discovery · The board's facts name no default branch, PR base, collected close-out PR or export PR (phase 2) (phase 2)

drive_snapshot cannot admit or refuse an archive PR on the board (no default branch, no base), and collected close-out and export PRs are not in the facts. So the card's archive PR gets a verdict kanban._archive_view builds from what the facts do say (checks, a conflict, else 'its base branch is not in the collected facts: the driver reads it live'), through the same other_readiness. Close-out and export entries show whenever the plan holds them (Card.others by batch, Board.others for no batch), and render tests cover them.

<!-- fr:journal kind=discovery scope=plan id=p2-opening-wave-order created=2026-11-25T03:08:29+00:00 phase=2 -->
### p2-opening-wave-order · discovery · A ready entry of a wave whose queue is only opening read 'not in the queue this pass' (phase 2) (phase 2)

plan_queue opens a wave's queue with no entries and builds on the next pass, so in_queue_order placed nothing. wave_queue._readiness now orders the opening wave's ready entries first, so the card reads 'Approved, merges next'.

<!-- fr:journal kind=discovery scope=plan id=p2-hints-kept created=2026-11-25T03:08:29+00:00 phase=2 -->
### p2-hints-kept · discovery · The merge-ready, in-queue and awaiting-approval hints were removed; the conflict, unconfigured, draft and CI-pending hints stay (phase 2) (phase 2)

R5 gives an approved conflicting PR no verdict (the queue ejects it), and a repo with no queue block has no queue verdict, so CONFLICT_HINT and HINT_QUEUE_UNCONFIGURED say what the verdict does not. A card whose PR was ready, queued or awaiting now carries no hint; every open batch PR gets a verdict, from snapshot_readiness when its repo has no queue plan. The tests that read the old hints read the verdict instead.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-25T03:08:29+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

other_readiness is new code beside batch_readiness and _other_ready now delegates to it; the only move (the queue report actions out of batch_drive) was done in the same commit to hold the module budget

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-25T03:08:29+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the board change is additive (Card.readiness and Card.others); the hint cleanup is P2.T3.S3

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-11-25T04:44:56+00:00 phase=2 -->
### p2-review · review · Phase 2 code review: one verdict function for board and queue holds (R4); 6 in-scope findings (phase 2)

Reviewer confirmed R4 (board and queue read plan.queues[*].readiness from batch_readiness/other_readiness; equality test over six cases; _other_ready admission unchanged from main), R6 facts and the collection-time line, R7 verdict-first cards, the wave_queue._readiness "merges next" change is label-only, the queue_reports move, and HTML escaping. Findings p2-r1..p2-r6 below. A low-confidence note (archive refusals under a non-repo placement) was not filed.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · R6 pane focus command (non-https Next-action link) is dropped by _link/_safe_url, so session-owned cards never show it (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Refused export PRs carry Action.batch=repo, so _others_of files them under a repo-name key and they render nowhere (R8 gap) (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · A repo with no queue block leads its card "Approved, merges next"; the unconfigured queue is not a queue-held verdict (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · refused_others keys pool/taken by bare PR number across repos, so same-numbered PRs in two repos collide (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Stale docstring in triage_batch_cmd.py names batch_drive._queue_reports after the move (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-25T04:44:56+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Test gaps: no end-to-end test for refused close-out/export, focus-command render, unconfigured verdict; the others' admits test is tautological (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: R6 pane focus command (non-https Next-action link) is dropped by _link/_safe_url, so session-owned cards never show it (phase 2)

64dcdf56c: ReadinessFacts gained `command`; `link` is URL-only; the card renders a Command row as escaped code. Test test_triage_kanban_render_readiness.py::test_a_session_owned_verdicts_focus_command_shows_on_the_page_escaped.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Refused export PRs carry Action.batch=repo, so _others_of files them under a repo-name key and they render nowhere (R8 gap) (phase 2)

9da5c3309: refused_others files a refused entry under a batch only when Action.batch is a real batch id, else under "" (Board.others). Test test_triage_readiness_others.py::test_a_refused_export_pr_reaches_the_boards_others_with_its_reason (fails on the old code).

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: A repo with no queue block leads its card "Approved, merges next"; the unconfigured queue is not a queue-held verdict (phase 2)

9a701a15b, 76c139c0a: queue_snapshot defaults a repo with no queue block to QueueConfig(ci=None) and queue_held_reason names it, so the card reads 'Not ready: queue held: queue not configured …'. admits keeps the entry's own admission (as for a halt-held queue): the held queue is what merges nothing, and the driver's ready set and the unconfigured hint read admits. Test test_triage_board_readiness.py::test_a_repo_with_no_queue_block_still_leads_its_card_with_a_verdict.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: refused_others keys pool/taken by bare PR number across repos, so same-numbered PRs in two repos collide (phase 2)

9da5c3309: pool/taken/out keyed by (repo, number). Test test_triage_readiness_others.py::test_same_numbered_prs_in_two_repos_do_not_share_a_refusal (fails on the old code).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Stale docstring in triage_batch_cmd.py names batch_drive._queue_reports after the move (phase 2)

3b4b923cd: the docstring names fr.triage.queue_reports.queue_reports.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-25T04:44:56+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Test gaps: no end-to-end test for refused close-out/export, focus-command render, unconfigured verdict; the others' admits test is tautological (phase 2)

9da5c3309: test_admits_follows_the_queues_conditions_written_out uses an independent oracle; test_a_refused_closeout_pr_reaches_its_batchs_card_with_its_reason and the export test go through drive_pass and kanban._others_of; focus-command and unconfigured tests above.
