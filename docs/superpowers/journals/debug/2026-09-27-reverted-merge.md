# Journal: 2026-09-27-reverted-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T09:31:24+00:00 -->
### repro · repro · A squash merge later reverted still reads as landed

Branch modifies an existing file; squash-merged to main; then `git revert` of the squash. branch_changes_present(branch, main): containment fails (the added lines are gone), then _branch_blob_was_on_base finds the squash commit's raw line whose new blob == the branch blob and returns True. Result: changes_present=True, so verify-merge (with PR MERGED) verifies and down/gc reap the worktree of a branch whose change is no longer on main. super-fr#716, from #696 phase-1 review r3.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-27T09:33:48+00:00 -->
### root-cause · root-cause · The blob fallback asks only whether the branch blob was ever written, never what the path became afterwards

_branch_blob_was_on_base scans `git log --raw -m merge_base..base_ref -- path` and returns True on the first raw line whose NEW blob equals the branch blob. A revert leaves that landing commit in history, so the scan still finds it. Nothing downstream re-checks: branch_changes_present takes the True, verify_merge (PR MERGED + changes present) verifies, and _reap_hazard reports no unlanded content, so down/gc reap. The distinguishing evidence is also in that same log: after the landing, a revert writes the path back to a blob it held BEFORE the landing. Rejected alternative: checking only the base's CURRENT blob — misses a revert followed by any later edit (routine on generated reports). Deliberate limit: absence (the null blob) is not treated as a restored state, because an added file that later disappears is exactly the consumed .changes fragment and the pinned test_branch_changes_present_file_deleted_from_base_later_counts_as_landed; so a revert of a branch that ONLY added files stays indistinguishable by content, as before.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-27T09:42:31+00:00 state=fixed -->
### fix · finding [fixed] · Blob fallback un-lands a path the base later wrote back to a pre-landing blob

packages/fr/src/fr/isolation/local.py _branch_blob_was_on_base: same single git log, now --topo-order --reverse; tracks every non-null blob the path held before/at the landing; a later write of one of them un-lands, a later write of the branch blob re-lands. Pinned red-first by six tests in tests/unit/test_isolation.py (reverted squash; revert then later edit; revert after the branch synced with another PR's change; rebase merge reverted; revert after the release consumed the fragment; verify_merge not verified) plus a green guard (revert of the revert re-lands). Full suite: 6561 passed, 115 skipped. Also: _squash_merge test helper now passes a committer identity to git merge --squash (a real 3-way squash needs one in the container).

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-09-27T10:01:56+00:00 -->
### review-1 · review · Independent Opus review: 3 findings + test notes

f1 MAJOR in: --topo-order puts a later-merged side branch (merge-commit PR forked before the landing) after the landing; a side commit writing a pre-landing blob falsely un-lands (proven in scratch repos). Fixed: --first-parent, guard test side_branch_merged_later_does_not_unland (red on the pre-fix code). f2 MAJOR: a three-way revert (another PR edits the path between landing and revert) still reads as landed — needs patch-level detection, a different design; filed super-fr#739, pinned as strict xfail. f3 MINOR: a later PR removing exactly the branch lines reads as reverted — safe refusal, documented. Test note: revert_of_the_revert is a guard, not red-first (by design).

<!-- fr:journal kind=hypothesis scope=debug id=second-root-cause created=2026-09-27T10:04:26+00:00 -->
### second-root-cause · hypothesis · Second root cause: a reverted --no-ff merge never reaches the blob fallback

Found writing a --no-ff + revert -m 1 test for the review. After a merge-commit landing the branch tip is an ancestor of the base, so merge-base == branch, _diff_names(merge_base, branch) is empty, and branch_changes_present returns changes_present=True before any per-file check. Independent of _branch_blob_was_on_base. Per the batch rules (one root cause per batch), NOT fixed here: pinned as strict xfail, pending the operator.
