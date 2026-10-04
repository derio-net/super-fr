# Journal: 2026-10-04-drive-release-behind

<!-- fr:journal kind=repro scope=debug id=8626b514bd5f created=2026-10-04T05:53:06+00:00 -->
### 8626b514bd5f · repro · Every move of main re-updates every ready PR

super-fr#927: on 2026-10-04 PRs #894 and #897 were each updated three times in one wave. Each driver merge moves main twice (the merge, then its `release: vX.Y.Z` commit that rewrites only version surfaces and deletes a .changes fragment), and close-out/archive merges move it again with docs/superpowers-only changes. Each move makes every other ready PR 'behind', so `merge_ready` updates it and it pays a full CI run before merging on a later pass. Repro at unit level: a ready PR whose head is not a descendant of origin/main, where the commits it lacks are a release commit or an archive merge, gets outcome 'updated' instead of 'merged'.

<!-- fr:journal kind=root-cause scope=debug id=83cb770f34dc created=2026-10-04T05:53:07+00:00 -->
### 83cb770f34dc · root-cause · _land's behind test counts every main commit, however routine

`fr.triage.batch_merge._land` sets `behind = not checkout.is_ancestor(origin/main, head)`: true the moment main gains any commit. Both `merge_ready` (drive) and `merge_one` (batch merge) then call `_update`, which merges main into the PR branch and pushes, restarting CI. Nothing distinguishes a commit that cannot change what the PR's CI proves (a version-only release commit, a docs/superpowers-only archive move) from a real code change. main has no branch protection here, so the forge does not require an up-to-date head to merge.

<!-- fr:journal kind=ruled-out scope=debug id=cfefe6c3022f created=2026-10-04T06:05:14+00:00 -->
### cfefe6c3022f · ruled-out · Trusting the release: subject line

Rejected per the operator's widened decision on #927: classify by files. A 'release:' commit that also adds a dependency is a real change; test_a_release_shaped_commit_that_changes_more_than_versions_still_updates pins it. Also rejected: PullRequest.files from facts for the overlap check (gh's files list caps per PR); a git ref...head diff is authoritative.

<!-- fr:journal kind=finding scope=debug id=09323c4316e7 created=2026-10-04T06:05:15+00:00 state=fixed -->
### 09323c4316e7 · finding [fixed] · _land skips the update when main is ahead only by routine commits

batch_merge._behind_only_routinely: every first-parent commit main has that the head lacks (Checkout.commits_behind) must be routine (routine_commit: all paths under docs/superpowers/, or .changes/ deletions plus only_versions_bumped files — one quoted version moved up, the same move everywhere) and touch no path the PR changed (Checkout.changed_paths, main...head). Otherwise the R4 update runs as before. Shared by drive's merge_ready and batch merge's merge_one. Pinned failing-first in tests/unit/test_triage_batch_merge_ready.py (release-only merges, archive-only merges, routine+code still updates, release+dependency still updates, overlap still updates) and against real git in tests/integration/test_triage_merge_routine_git.py.

<!-- fr:journal kind=review scope=debug id=5389b8eff7d2 created=2026-10-04T06:09:20+00:00 -->
### 5389b8eff7d2 · review · Independent adversarial review: 3 findings, 2 fixed, 1 filed

Verified the real release commit adfbac97 classifies as routine (one move 5.2.4 -> 5.2.5 across every manifest and uv.lock). Findings: (1) only_versions_bumped accepted any version-shaped edit with no fragment consumed (a workflow tool pin, a source constant) — fixed: a release must delete a .changes/ fragment. (2) a mode-only change (equal bytes, status M) slipped through — fixed: equal content is not routine. Both pinned in test_routine_commit_classifies_by_files. (3) an archive move can break a waiting PR's matrix refs by content, not path — the operator's docs-only rule, out of scope here: filed #937. Merge commits on main, -z parsing, version-block slots and merge_one checked fine.
