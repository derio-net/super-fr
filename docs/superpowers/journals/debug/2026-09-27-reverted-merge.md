# Journal: 2026-09-27-reverted-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T09:31:24+00:00 -->
### repro · repro · A squash merge later reverted still reads as landed

Branch modifies an existing file; squash-merged to main; then `git revert` of the squash. branch_changes_present(branch, main): containment fails (the added lines are gone), then _branch_blob_was_on_base finds the squash commit's raw line whose new blob == the branch blob and returns True. Result: changes_present=True, so verify-merge (with PR MERGED) verifies and down/gc reap the worktree of a branch whose change is no longer on main. super-fr#716, from #696 phase-1 review r3.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-27T09:33:48+00:00 -->
### root-cause · root-cause · The blob fallback asks only whether the branch blob was ever written, never what the path became afterwards

_branch_blob_was_on_base scans `git log --raw -m merge_base..base_ref -- path` and returns True on the first raw line whose NEW blob equals the branch blob. A revert leaves that landing commit in history, so the scan still finds it. Nothing downstream re-checks: branch_changes_present takes the True, verify_merge (PR MERGED + changes present) verifies, and _reap_hazard reports no unlanded content, so down/gc reap. The distinguishing evidence is also in that same log: after the landing, a revert writes the path back to a blob it held BEFORE the landing. Rejected alternative: checking only the base's CURRENT blob — misses a revert followed by any later edit (routine on generated reports). Deliberate limit: absence (the null blob) is not treated as a restored state, because an added file that later disappears is exactly the consumed .changes fragment and the pinned test_branch_changes_present_file_deleted_from_base_later_counts_as_landed; so a revert of a branch that ONLY added files stays indistinguishable by content, as before.
