# Journal: 2026-10-04-drive-release-behind

<!-- fr:journal kind=repro scope=debug id=8626b514bd5f created=2026-10-04T05:53:06+00:00 -->
### 8626b514bd5f · repro · Every move of main re-updates every ready PR

super-fr#927: on 2026-10-04 PRs #894 and #897 were each updated three times in one wave. Each driver merge moves main twice (the merge, then its `release: vX.Y.Z` commit that rewrites only version surfaces and deletes a .changes fragment), and close-out/archive merges move it again with docs/superpowers-only changes. Each move makes every other ready PR 'behind', so `merge_ready` updates it and it pays a full CI run before merging on a later pass. Repro at unit level: a ready PR whose head is not a descendant of origin/main, where the commits it lacks are a release commit or an archive merge, gets outcome 'updated' instead of 'merged'.
