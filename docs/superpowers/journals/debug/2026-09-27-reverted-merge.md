# Journal: 2026-09-27-reverted-merge

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T09:31:24+00:00 -->
### repro · repro · A squash merge later reverted still reads as landed

Branch modifies an existing file; squash-merged to main; then `git revert` of the squash. branch_changes_present(branch, main): containment fails (the added lines are gone), then _branch_blob_was_on_base finds the squash commit's raw line whose new blob == the branch blob and returns True. Result: changes_present=True, so verify-merge (with PR MERGED) verifies and down/gc reap the worktree of a branch whose change is no longer on main. super-fr#716, from #696 phase-1 review r3.
