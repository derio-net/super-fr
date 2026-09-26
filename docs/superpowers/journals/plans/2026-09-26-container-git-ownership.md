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
