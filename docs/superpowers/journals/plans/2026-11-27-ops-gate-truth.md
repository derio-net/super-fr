<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-ops-gate-truth

<!-- fr:journal kind=decision scope=plan id=p1-reopen-before-merge created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-reopen-before-merge · decision · the refresh reopens changed ops (and forgets stages >= 4) before the merge, not after it (phase 1)

§A orders it merge -> push -> reopen. A merge that conflicts is aborted and the operator
merges by hand (R3); on the rerun the workspace already matches the default branch, so
drift is empty and nothing would reopen: the changed op's old closure would still close
it, which is gh#1617's defect again. So `refresh` sets the reopened set (and calls
`forget(4)` past stage 4) right after the confirmation and the records commit, before
`merge_commit`. A declined confirmation still changes nothing (R2); `Restart` is raised
only after a clean merge, push and trust.

<!-- fr:journal kind=decision scope=plan id=p1-restart-bounded created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-restart-bounded · decision · run() goes back to the first unrecorded stage on Restart, at most twice per invocation (phase 1)

A refresh merges the default branch, so the next comparison is equal; a third Restart in
one invocation can only mean the branch keeps moving, and the stage fails asking for a
re-run (MAX_RESTARTS = 2 in fr.ops.gate).

<!-- fr:journal kind=discovery scope=plan id=p1-merge-already-contained created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-merge-already-contained · discovery · merge_commit of a commit the ops branch already holds commits nothing (phase 1)

Drift can differ while the default branch adds nothing new (the workspace's own ops.yaml
was edited). `git merge --no-ff --no-commit` then leaves no MERGE_HEAD and a commit would
fail; `OpsWorkspace.merge_commit` returns the current head instead.

<!-- fr:journal kind=discovery scope=plan id=p1-label-passed-stage-6 created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-label-passed-stage-6 · discovery · a Restart from stage 7 forgets stage 6, but stage 6 stays done while the PR carries gate:devops-passed (phase 1)

`_passed` reads stage 6 done from the host state OR the forge label. After a refresh at
stage 7 that reopened an op, stage 4 and 5 rerun but stage 6 is skipped when the label
is already on the PR. Stage 4 still re-applies the reopened op; the gate pass is not
re-checked. Left as is (R6 names stage 4, which runs).

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-cost created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-fast-tier-cost · discovery · the --fr-scope fast tier selects thousands of tests on this branch (spec/plan docs pull in every own_artifacts test) (phase 1)

The T1 run of the fast tier was still at ~6% after ~15 minutes on a loaded host (load ~20);
the per-task runs used the touched test files and their neighbours instead, and the fast
tier ran once, last.

<!-- fr:journal kind=finding scope=plan id=p1-sec-r1 created=2026-11-27T23:19:34+00:00 phase=1 state=fixed review_scope=in -->
### p1-sec-r1 · finding [fixed] (reviewer: in scope) · refresh diffed origin/<default>, then merge_commit fetched and merged the ref again (TOCTOU) (phase 1)

If the default branch moved between the comparison and the merge, the merged content
differed from what the operator confirmed and the reopened set came from a stale diff.
Fixed: `refresh` resolves `origin/<default>` once (`rev_parse`, `valid_sha`),
materialises and diffs that sha, names its first 12 characters in the question and passes
the sha to `merge_commit`; `OpsWorkspace.merge_commit` refuses a non-sha and a non-commit
(`cat-file -e <sha>^{commit}`) and merges exactly that sha (its fetch only brings objects).
Tests: test_ops_gate.py::test_the_refresh_merges_the_sha_it_diffed_though_the_default_branch_moved,
test_a_default_tip_that_is_no_sha_is_refused_before_any_diff; test_ops_gate_cmd.py::
test_merge_commit_merges_the_pinned_sha_not_a_moved_tip,
test_merge_commit_refuses_anything_but_a_commit_sha.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

drift is three small readers and one comparison; nothing repeated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

merge_commit reuses gitseam's Worktree.merge/abort_merge; the commit is one git call, so no new gitseam helper was needed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the exclusion set shared by _unclosed and apply_phase was written once (_excluded over refresh.closure_exclusions) in the green step itself

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A restart reaching stage 6 skips it when gate:devops-passed is already on the PR (phase 1)

The pass label stood in for stage 6 after a restart (gate.py), so the pass stood against reopened ops and a changed Test Plan; R6 not met.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Entry ids are snapshotted before the merge, so merged-in default-branch entries can close a reopened op (phase 1)

refresh.py took `before` ahead of the merge; journal entries brought in by merging origin/<default> then counted as closures recorded here.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · A Test Plan-only refresh at stage 6/7 does not send the run back to stage 5 (phase 1)

refresh.py forgot stages only on reopened ops, leaving new devops steps unwalked after the pass.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Missing tests for MAX_RESTARTS, a skipped-stage-6 restart, push failure after merge, and stage 6/7 refresh (phase 1)

tests/unit/test_ops_refresh.py and test_ops_gate.py covered the stage 4/5 paths only.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · A no-op merge whose ops still differ re-prompts every stage and storms restarts to MAX_RESTARTS (phase 1)

Tagged out by the reviewer. Fixed anyway in this PR, because the refresh loop this phase added is what storms.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-28T00:23:13+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 review (stale ops refresh), five findings, all fixed (phase 1)

Independent review of the phase-1 diff (ops/refresh.py, ops/gate.py, commands/ops_gate_cmd.py, tests, docs) against spec R1-R6.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A restart reaching stage 6 skips it when gate:devops-passed is already on the PR (phase 1)

406786085: the label stands in for stage 6 only when no op is reopened and 6 was not forgotten; otherwise stage 6 checks devops_blockers on the refreshed tree and fails naming them; fr never removes the label.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Entry ids are snapshotted before the merge, so merged-in default-branch entries can close a reopened op (phase 1)

406786085: `before` is unioned with the entry ids read after the merge, so merged-in entries never count.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: A Test Plan-only refresh at stage 6/7 does not send the run back to stage 5 (phase 1)

406786085 + 031ec0309: a Test Plan-only drift at stage 6/7 forgets stages 5+ and restarts; docs updated.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Missing tests for MAX_RESTARTS, a skipped-stage-6 restart, push failure after merge, and stage 6/7 refresh (phase 1)

406786085: tests for the MAX_RESTARTS bound, a failed push and its rerun, refresh at stages 6 and 7, and is_ancestor on real git.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: A no-op merge whose ops still differ re-prompts every stage and storms restarts to MAX_RESTARTS (phase 1)

dca2c3ada + 406786085: a pinned sha already in the ops branch with drift persisting fails the stage before the prompt, naming what differs.
