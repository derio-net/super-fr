# Journal: 2026-10-06-drive-board-lows

<!-- fr:journal kind=repro scope=debug id=9ac26f61e94c created=2026-10-06T16:58:17+00:00 -->
### 9ac26f61e94c · repro · Five members, five root causes

Batch drive-board-lows was dispatched as one root cause. Checked on origin/main fa99a3aa (after #1031): #937 routine overlap compares paths only (batch_merge._behind_only_routinely); #962 a pr_merge head-SHA refusal is caught as a generic FORGE_ERRORS refusal (_merge); #884 a test-only gap; #985 kanban.py maps partial -> done; #1025 four degraded-forge exits. Operator decision 2026-10-06: fix all in one PR; #985 gets its own column; #937 treats docs/acceptance/** as overlapping every archive commit.

<!-- fr:journal kind=repro scope=debug id=a52540135e27 created=2026-10-06T16:58:18+00:00 -->
### a52540135e27 · repro · #937: an archive merge lets a matrix-only PR merge unupdated

test_an_archive_merge_updates_a_pr_that_changes_the_acceptance_matrix: main ahead by one archive commit (moves plans/X -> implemented/plans/X), PR changes only docs/acceptance/matrix.yaml -> merge_ready returns merged, expected updated.

<!-- fr:journal kind=root-cause scope=debug id=3aa271b5d035 created=2026-10-06T16:58:20+00:00 -->
### 3aa271b5d035 · root-cause · #937: the overlap rule sees paths, the matrix holds paths as content

_behind_only_routinely skips the update when no path the archive commit touched is a path the PR changed. matrix.yaml cites specs/plans by path in its content, so an archive move can dangle a ref with no path overlap.

<!-- fr:journal kind=finding scope=debug id=f-937 created=2026-10-06T16:58:51+00:00 state=fixed -->
### f-937 · finding [fixed] · #937 fixed: docs/acceptance/** overlaps every archive commit

batch_merge._behind_only_routinely: a PR touching docs/acceptance/ is not routine-mergeable past an archive commit (_is_archive, now shared with routine_commit). Pinned by test_an_archive_merge_updates_a_pr_that_changes_the_acceptance_matrix; test_a_release_commit_alone_still_merges_a_pr_that_changes_the_matrix keeps a release routine.

<!-- fr:journal kind=finding scope=debug id=f-962 created=2026-10-06T16:59:57+00:00 state=fixed -->
### f-962 · finding [fixed] · #962 fixed: a refused merge re-reads the head

batch_merge._merge: on a FORGE_ERRORS refusal, re-read pr_view; a head other than the one merged raises HeadMovedError (stop the train, re-plan), else the generic refusal. A failed re-read keeps the refusal. Pinned by test_a_head_that_moves_just_before_the_merge_is_a_moved_head / test_a_refusal_with_the_head_unmoved_stays_a_refusal.

<!-- fr:journal kind=finding scope=debug id=f-884 created=2026-10-06T17:02:04+00:00 state=fixed -->
### f-884 · finding [fixed] · #884 fixed: the group cap tests prove group behaviour

test_a_fifth_batch_is_held_by_four_in_flight_across_two_owners: 2+2 in flight across example-org/other-org, a fifth proposed under cap 4 -> held naming all four; control run at cap 5 dispatches it. test_a_dispatched_batch_in_one_repo_uses_the_cap_of_the_other now asserts the positive held line. Verified by mutation: per-repo and per-owner cap counting both turn the new test red; the shipped code keeps it green.

<!-- fr:journal kind=finding scope=debug id=f-1025-12 created=2026-10-06T17:05:18+00:00 state=fixed -->
### f-1025-12 · finding [fixed] · #1025 items 1-2 fixed: dispatch fetch and export writes

Item 1: dispatch_batch/_reservation take read_errors=True from the driver only; a failed _fresh_config raises ForgeReadError(code=2) as merge_ctx does, so the loop skips the pass; batch dispatch by hand still exits 2. Item 2: every git/forge write failure in _export/_export_merge goes through _export_failed (failed_write, reported once per wave+cause, retried next pass; --once exits 1); a separate _export_failures counter keeps the export owed rather than blocked. Tests in test_triage_batch_drive_disruption.py (gh#1025 sections).

<!-- fr:journal kind=finding scope=debug id=f-1025-3 created=2026-10-06T17:08:24+00:00 state=fixed -->
### f-1025-3 · finding [fixed] · #1025 item 3 fixed: a stale pre-recorded close-out is warned once

batch_drive._stale_closeout: a close-out event older than STALE_CLOSEOUT (15 min), whose item the runner does not hold live and that no archive PR is attributed to, is a once-said warn naming fr pickup --run/--branch. Only for batches in Snapshot.closeout_probed, which the command fills (yes mode only) and probes through _existing alongside the due ones, so plan mode never calls one stale. Tests: test_triage_batch_drive.py (gh#1025 (3)) and test_triage_batch_drive_disruption.py.

<!-- fr:journal kind=finding scope=debug id=f-1025-4 created=2026-10-06T17:11:28+00:00 state=fixed -->
### f-1025-4 · finding [fixed] · #1025 item 4 fixed: bulk gh lists get a page-scaled bound

gh._bound: a call carrying --limit N is bounded by list_timeout(N) = GH_TIMEOUT_SECONDS + 30s per 100-record page past the first, capped at GH_LIST_TIMEOUT_CAP_SECONDS (600s); every other call keeps 120s. Derived in _run_gh from the args so no call site or test fake changes. The gh#909 stall test now pins the cap. Tests: test_gh.py TestRunGhTimeout.

<!-- fr:journal kind=finding scope=debug id=f-985 created=2026-10-06T17:13:22+00:00 state=fixed -->
### f-985 · finding [fixed] · #985 fixed: a Partial column between Closing out and Done

Operator decision 2026-10-06: own column. kanban.column_of puts stage partial in the new partial column until closeout_state is archived, then Done with the partial pill; its fallback hint is the closing-out one. The board grid widens to one track per column, pinned by test_the_wide_grid_has_one_track_per_column. Tests: test_triage_kanban.py, test_triage_kanban_render.py.

<!-- fr:journal kind=review scope=debug id=784f6b5eeb21 created=2026-10-06T17:33:38+00:00 -->
### 784f6b5eeb21 · review · Independent review: two findings, both fixed

An independent read-only reviewer checked all eight claims. Confirmed: #937, #962, #884, #1025 items 2 and 4, #985. Findings: (1) medium: the stale-close-out probe went through _existing, whose preflight refusal _fails, so a refusing runner plus any batch whose archive PR has been open 15+ min would exit 2 every pass; fixed: _existing(soft=True) skips a runner that cannot load or refuses and reports only the items it asked, so closeout_probed holds only those (test_a_runner_that_refuses_the_stale_probe_does_not_stop_the_drive). (2) low-medium: dispatch_batch's ls-remote (remote_branch_exists) still _failed on a forge read; fixed: read_errors converts it to ForgeReadError(code=2) (test_a_failed_remote_branch_read_for_a_dispatch_does_not_end_the_loop). (3) cosmetic: build_board docstring said six columns; fixed. Noted, not changed: export failure dedupe keys on the message, so stderr that varies per attempt would repeat the line, unverified in practice.
