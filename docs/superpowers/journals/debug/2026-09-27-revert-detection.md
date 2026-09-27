# Journal: 2026-09-27-revert-detection

<!-- fr:journal kind=repro scope=debug id=d01d6aec180f created=2026-09-27T19:28:50+00:00 -->
### d01d6aec180f · repro · #741: a --no-ff landing reverted with revert -m 1 still reads landed

Scratch repo: base report.md=head; feature adds foo, bar in two commits; main commits other.py; `git merge --no-ff feature`; `git revert -m 1 HEAD`. `git merge-base main feature` == feature tip (99fde50…), so `git diff --name-only mb feature` is empty and branch_changes_present returns changes_present=True with changed=[]. Pinned: strict xfail test_branch_changes_present_reverted_no_ff_merge_is_missing.
