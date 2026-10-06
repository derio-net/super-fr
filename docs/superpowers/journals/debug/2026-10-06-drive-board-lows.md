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
