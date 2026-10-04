# Journal: 2026-10-04-drive-release-behind

<!-- fr:journal kind=repro scope=debug id=8626b514bd5f created=2026-10-04T05:53:06+00:00 -->
### 8626b514bd5f · repro · Every move of main re-updates every ready PR

super-fr#927: on 2026-10-04 PRs #894 and #897 were each updated three times in one wave. Each driver merge moves main twice (the merge, then its `release: vX.Y.Z` commit that rewrites only version surfaces and deletes a .changes fragment), and close-out/archive merges move it again with docs/superpowers-only changes. Each move makes every other ready PR 'behind', so `merge_ready` updates it and it pays a full CI run before merging on a later pass. Repro at unit level: a ready PR whose head is not a descendant of origin/main, where the commits it lacks are a release commit or an archive merge, gets outcome 'updated' instead of 'merged'.

<!-- fr:journal kind=root-cause scope=debug id=83cb770f34dc created=2026-10-04T05:53:07+00:00 -->
### 83cb770f34dc · root-cause · _land's behind test counts every main commit, however routine

`fr.triage.batch_merge._land` sets `behind = not checkout.is_ancestor(origin/main, head)`: true the moment main gains any commit. Both `merge_ready` (drive) and `merge_one` (batch merge) then call `_update`, which merges main into the PR branch and pushes, restarting CI. Nothing distinguishes a commit that cannot change what the PR's CI proves (a version-only release commit, a docs/superpowers-only archive move) from a real code change. main has no branch protection here, so the forge does not require an up-to-date head to merge.
