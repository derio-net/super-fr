# Journal: 2026-09-27-revert-detection

<!-- fr:journal kind=repro scope=debug id=d01d6aec180f created=2026-09-27T19:28:50+00:00 -->
### d01d6aec180f · repro · #741: a --no-ff landing reverted with revert -m 1 still reads landed

Scratch repo: base report.md=head; feature adds foo, bar in two commits; main commits other.py; `git merge --no-ff feature`; `git revert -m 1 HEAD`. `git merge-base main feature` == feature tip (99fde50…), so `git diff --name-only mb feature` is empty and branch_changes_present returns changes_present=True with changed=[]. Pinned: strict xfail test_branch_changes_present_reverted_no_ff_merge_is_missing.

<!-- fr:journal kind=repro scope=debug id=7e291a77364c created=2026-09-27T19:28:53+00:00 -->
### 7e291a77364c · repro · #739: a revert applied after another edit to the path reads landed

Squash-land +foo into a..e; a later PR edits e->E (report now has foo); `git revert HEAD~1` removes foo, producing a,b,c,d,E — a blob the path never held. The #716 rule only un-lands when a post-landing commit writes a pre-landing ('held') blob, so the three-way result is never matched. Pinned: strict xfail test_branch_changes_present_three_way_revert_is_missing.

<!-- fr:journal kind=root-cause scope=debug id=9e52c689b768 created=2026-09-27T19:28:54+00:00 -->
### 9e52c689b768 · root-cause · Both: branch_changes_present infers 'reverted' only from whole-state evidence

#741: the fork point comes from `git merge-base base branch`, which for an ancestor branch is the branch tip itself — the diff of the branch's own changes is empty and every path check is skipped. The true fork point is merge-base(M^1, branch) where M is the landing merge: the oldest commit on base's first-parent line that descends from the tip (`git rev-list --first-parent --ancestry-path --reverse branch..base`, first line). For a fast-forward or an empty branch M^1 IS the tip, so this degenerates to today's behaviour. #739: _branch_blob_was_on_base recognises a revert only by the path returning to a whole blob it held before; a revert is also recognisable by its PATCH — it removes every non-blank line the branch added and adds nothing but lines the branch removed. The raw log already walks those commits, so adding -p to the same git call yields the patch. One mechanism, two evidence gaps in the same function — a single root cause as batched.
