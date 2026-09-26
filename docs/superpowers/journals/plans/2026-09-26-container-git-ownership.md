# Journal: 2026-09-26-container-git-ownership

<!-- fr:journal kind=discovery scope=plan id=p1-red-dubious-ownership created=2026-09-26T15:53:10 phase=1 -->
### p1-red-dubious-ownership · discovery · Red confirmed under GIT_TEST_ASSUME_DIFFERENT_OWNER=1 with an empty global config (phase 1)

On the unfixed code commit_paths from the linked-worktree toplevel and from sub/deep both refused with "fatal: detected dubious ownership in repository at <worktree>"; _is_tracked and _short_head misanswered. Fixed by fr.git.safe_directory_args and fr.git.git_argv (single argv construction shared by git_answer, the update-index restore and record/apply).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:53:10 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

test-only task; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-26T15:53:10 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

one-line constant change plus regenerated profile strings; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-26T15:53:10 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

acceptance rows and a change fragment; nothing to clean

<!-- fr:journal kind=finding scope=plan id=r1-profile-parity created=2026-09-26T15:55:37 phase=1 state=open review_scope=in -->
### r1-profile-parity · finding [open] (reviewer: in scope) · No test compares committed dev/admin profiles to POST_CREATE (phase 1)

Spec Test Plan 5 was unguarded (tests/unit/test_container_git_ownership.py).

<!-- fr:journal kind=finding scope=plan id=r2-restore-untested created=2026-09-26T15:55:37 phase=1 state=open review_scope=in -->
### r2-restore-untested · finding [open] (reviewer: in scope) · update-index restore path carries the override but is untested (phase 1)

_restore_index runs only on refusal; argv not asserted (commit.py:685).

<!-- fr:journal kind=finding scope=plan id=r3-home-leak created=2026-09-26T15:55:37 phase=1 state=open review_scope=in -->
### r3-home-leak · finding [open] (reviewer: in scope) · test_scaffold_host_cli_snippet runs real git config --global with no HOME (phase 1)

Could write the developer's real ~/.gitconfig if HOME leaked.

<!-- fr:journal kind=finding scope=plan id=r4-shared-seam-trust created=2026-09-26T15:55:37 phase=1 state=open review_scope=out -->
### r4-shared-seam-trust · finding [open] (reviewer: out of scope) · git_answer trusts enclosing repo for every caller; walk-up trusts any ancestor .git (phase 1)

By design per spec §3 trust boundary; per-process only.

<!-- fr:journal kind=finding scope=plan id=r5-tmp-in-repo created=2026-09-26T15:55:37 phase=1 state=open review_scope=out -->
### r5-tmp-in-repo · finding [open] (reviewer: out of scope) · outside-any-repo test assumes TMPDIR is not inside a repo; _run_git unchanged (phase 1)

Both pre-existing/spec-excluded.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-26T15:55:37 phase=1 -->
### review-p1 · review · phase 1 code review: 5 findings (3 in scope, 2 out) (phase 1)

Independent reviewer verified spec conformance of git.py, commit.py, record/apply.py, scaffold.py, both profiles, and the fragment; test non-vacuity confirmed.

<!-- fr:journal kind=finding scope=plan id=r1-profile-parity-resolved created=2026-09-26T15:55:37 phase=1 state=fixed resolves=r1-profile-parity -->
### r1-profile-parity-resolved · finding [fixed] · resolves r1-profile-parity: No test compares committed dev/admin profiles to POST_CREATE (phase 1)

Added test_committed_profiles_carry_the_scaffold_post_create.

<!-- fr:journal kind=finding scope=plan id=r2-restore-untested-resolved created=2026-09-26T15:55:37 phase=1 state=fixed resolves=r2-restore-untested -->
### r2-restore-untested-resolved · finding [fixed] · resolves r2-restore-untested: update-index restore path carries the override but is untested (phase 1)

Added test_index_restore_carries_the_override_before_the_subcommand.

<!-- fr:journal kind=finding scope=plan id=r3-home-leak-resolved created=2026-09-26T15:55:37 phase=1 state=fixed resolves=r3-home-leak -->
### r3-home-leak-resolved · finding [fixed] · resolves r3-home-leak: test_scaffold_host_cli_snippet runs real git config --global with no HOME (phase 1)

_run now sets an isolated HOME under tmp_path.

<!-- fr:journal kind=finding scope=plan id=r4-shared-seam-trust-resolved created=2026-09-26T15:55:37 phase=1 state=open resolves=r4-shared-seam-trust out_of_scope=true -->
### r4-shared-seam-trust-resolved · finding [out-of-scope] · resolves r4-shared-seam-trust: git_answer trusts enclosing repo for every caller; walk-up trusts any ancestor .git (phase 1)

Stated design of the spec, not a defect introduced here.

<!-- fr:journal kind=finding scope=plan id=r5-tmp-in-repo-resolved created=2026-09-26T15:55:37 phase=1 state=open resolves=r5-tmp-in-repo out_of_scope=true -->
### r5-tmp-in-repo-resolved · finding [out-of-scope] · resolves r5-tmp-in-repo: outside-any-repo test assumes TMPDIR is not inside a repo; _run_git unchanged (phase 1)

Test assumption is pre-existing style; _run_git excluded by spec.
