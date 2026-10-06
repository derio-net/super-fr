# Journal: 2026-10-06-drive-board-lows

<!-- fr:journal kind=repro scope=debug id=9ac26f61e94c created=2026-10-06T16:58:17+00:00 -->
### 9ac26f61e94c · repro · Five members, five root causes

Batch drive-board-lows was dispatched as one root cause. Checked on origin/main fa99a3aa (after #1031): #937 routine overlap compares paths only (batch_merge._behind_only_routinely); #962 a pr_merge head-SHA refusal is caught as a generic FORGE_ERRORS refusal (_merge); #884 a test-only gap; #985 kanban.py maps partial -> done; #1025 four degraded-forge exits. Operator decision 2026-10-06: fix all in one PR; #985 gets its own column; #937 treats docs/acceptance/** as overlapping every archive commit.

<!-- fr:journal kind=repro scope=debug id=a52540135e27 created=2026-10-06T16:58:18+00:00 -->
### a52540135e27 · repro · #937: an archive merge lets a matrix-only PR merge unupdated

test_an_archive_merge_updates_a_pr_that_changes_the_acceptance_matrix: main ahead by one archive commit (moves plans/X -> implemented/plans/X), PR changes only docs/acceptance/matrix.yaml -> merge_ready returns merged, expected updated.
