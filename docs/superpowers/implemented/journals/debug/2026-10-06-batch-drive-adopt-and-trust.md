# Journal: 2026-10-06-batch-drive-adopt-and-trust

<!-- fr:journal kind=repro scope=debug id=77a8298c2a5d created=2026-10-06T16:09:01+00:00 -->
### 77a8298c2a5d · repro · Three driver defects reproduced by reading the pass (gh#990, gh#991, gh#1004)

gh#990: a merged wave-less batch with no close-out event, alongside any waved batch, is never adopted: `default_selection` drops it, and both the snapshot's archived read and drive_pass step 2 iterate `chosen` only.
gh#991: `fr triage batch drive --once` (no --yes) with an unreadable clone reports archived batches as `closeout start`: `_archived`/`_released`/`_ci_none` swallow TriageError outside --yes.
gh#1004: an archive PR retargeted off the default branch is merged by step 3/`_archive`: archive LivePrs never carry `base`.

<!-- fr:journal kind=root-cause scope=debug id=e11888cd2dd2 created=2026-10-06T16:09:02+00:00 -->
### e11888cd2dd2 · root-cause · Not one cause but three independent ones (operator chose: fix all three in one PR)

1. Adoption (bookkeeping) is scoped to the drive selection; it must read every landed batch without a close-out event (gh#990).
2. Plan-mode clone reads turn a read failure into a negative answer, silently (gh#991).
3. The archive-PR trust check omits the base branch the export path already checks via `_wrong_base` (gh#1004, p4-r15).
Investigation found three causes; the batch rule required stopping to ask, and the operator chose to fix all three in this PR.

<!-- fr:journal kind=finding scope=debug id=adopt-beyond-selection created=2026-10-06T16:20:44+00:00 state=fixed -->
### adopt-beyond-selection · finding [fixed] · gh#990: finished close-outs are adopted whatever the selection

drive_pass step 2 iterates every batch; archived/merged-hand adoption ignores the selection, starting or recording an open close-out does not. The snapshot reads archive evidence for every landed batch outside unread repos. Pinned by test_a_wave_less_finished_batch_is_adopted_but_only_the_selection_is_closed_out, test_a_wave_less_archived_batch_is_adopted_by_an_unnamed_drive, test_a_wave_less_batch_still_owed_is_not_closed_out_outside_the_selection. Reverses #922's review-added 'unselected batch gets no adopt' test (renamed ..._an_unselected_batch_is_adopted_too).

<!-- fr:journal kind=finding scope=debug id=plan-mode-unreadable-clone created=2026-10-06T16:20:44+00:00 state=fixed -->
### plan-mode-unreadable-clone · finding [fixed] · gh#991: plan mode reports an unreadable clone instead of planning phantom close-outs

_archived/_released return None in plan mode on a TriageError; the batch goes to Snapshot.unverified (no close-out, no adopt, still closing) and one warning per repo names the reason and the batches. _ci_none records its failure too. --yes behaviour unchanged (ForgeReadError). Pinned by test_plan_mode_with_an_unreadable_clone_says_so_and_plans_no_closeout and test_a_batch_whose_closeout_evidence_was_unreadable_is_neither_closed_out_nor_adopted.

<!-- fr:journal kind=finding scope=debug id=archive-pr-base created=2026-10-06T16:20:45+00:00 state=fixed -->
### archive-pr-base · finding [fixed] · gh#1004: archive PRs merge only into the default branch

_archive_prs reads base_ref fresh (pr_view) for open PRs attributed to the batch; step 3 merges only a ready PR whose base is the default branch (_wrong_base, shared with the export), else warns once (keyed on head) and counts the batch blocked. Snapshot.export_default renamed default_branch. Pinned by test_an_archive_pr_retargeted_off_the_default_branch_is_never_merged and ..._is_reported_and_never_merged.

<!-- fr:journal kind=review scope=debug id=3151512f1698 created=2026-10-06T16:28:46+00:00 -->
### 3151512f1698 · review · Independent review (read-only, separate context): no blocker; 3 medium, 3 low

(1) MEDIUM, in scope, fixed: a wrong-base archive PR counted blocked but the loop's 'only blocked batches remain ()' named nothing; it is now a 'blocked' action, named every pass (also removes the head-keyed warn dedupe, finding 5). (2) MEDIUM, in scope, accepted: wave-less landed batches still owed a close-out are now read every pass outside the selection (pr_view, fetch, list_prs_by_head); bounded by exactly the backlog gh#990 wants recorded, and archived ones cost nothing after adoption. (3) MEDIUM, in scope, fixed: an unreadable default branch read as '' blamed every archive PR's base; now it routes through the unreadable-clone warning and the batch waits (closing). (4) LOW, accepted: adopting an unselected batch can finish its wave, so the wave's export may fire under a named drive; that is the bookkeeping gh#990 asks for. (5) LOW, fixed by (1). (6) LOW, fixed: the warning no longer says 'archive/release checks' when only the ci/default read failed. Race between snapshot and _archive on a retarget is the same as the export path's: not addressed.
