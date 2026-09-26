# Journal: 2026-09-26-verify-merge-rewrites

<!-- fr:journal kind=discovery scope=plan id=verify-merge-mypy-flake created=2026-09-26T15:46:38 phase=1 -->
### verify-merge-mypy-flake · discovery · full-workspace mypy crashed once with INTERNAL ERROR (phase 1)

The first full-workspace mypy run after the edit hit an INTERNAL ERROR (mypy 1.20.0, exit 2); rerunning packages/fr/src alone and the full set again passed, and the pre-change tree also passes. Treated as a cache flake, not a code defect.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:46:38 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Task 1 only adds failing tests; there was no production code to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-26T15:46:38 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Task 3 is a matrix status move, a change fragment and a verification run; nothing to refactor.

<!-- fr:journal kind=finding scope=plan id=r1 created=2026-09-26T15:52:41 phase=1 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · unresolvable-ref test passes on the old code too (phase 1)

test_verify_merge_unresolvable_ref_raises_naming_the_branch matched a branch name the old merge-base error also carried; assert _branch_refs' own wording.

<!-- fr:journal kind=finding scope=plan id=r2 created=2026-09-26T15:52:41 phase=1 state=open review_scope=in -->
### r2 · finding [open] (reviewer: in scope) · two verify_merge tests are guards, not red-before-fix (phase 1)

Unpushed-local and deleted-remote tests were probably green before; they guard the fail-safe.

<!-- fr:journal kind=finding scope=plan id=r3 created=2026-09-26T15:52:41 phase=1 state=open review_scope=out -->
### r3 · finding [open] (reviewer: out of scope) · A reverted merge still passes the blob fallback (phase 1)

Design-inherent to spec §A (positive evidence from base history); verify-merge still needs PR MERGED; reap keeps the branch ref.

<!-- fr:journal kind=finding scope=plan id=r4 created=2026-09-26T15:52:41 phase=1 state=open review_scope=out -->
### r4 · finding [open] (reviewer: out of scope) · diff --name-only without -z quotes special paths (phase 1)

Pre-existing; fails safe.

<!-- fr:journal kind=finding scope=plan id=r5 created=2026-09-26T15:52:41 phase=1 state=open review_scope=out -->
### r5 · finding [open] (reviewer: out of scope) · One rev-parse per commit touching the path (phase 1)

Spec accepts cost bounded to one path; early exit already present.

<!-- fr:journal kind=finding scope=plan id=r6 created=2026-09-26T15:52:41 phase=1 state=open review_scope=in -->
### r6 · finding [open] (reviewer: in scope) · No test for path with space/dash/glob or failed rev-list (phase 1)

Optional; code is safe by inspection.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-26T15:52:41 phase=1 -->
### review-phase-1 · review · independent review of phase 1: 6 findings (3 in, 3 out), no critical (phase 1)

Reviewer a6a03ceb06e10253d. Blob fallback cannot pass unlanded content except the accepted revert case; ref set matches spec B; scaffold.py/commit.py untouched (verified by diff --stat, 0 lines).

<!-- fr:journal kind=finding scope=plan id=r1-resolved created=2026-09-26T15:52:41 phase=1 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: unresolvable-ref test passes on the old code too (phase 1)

Assertion now matches 'cannot resolve branch ref' (_branch_refs' wording).

<!-- fr:journal kind=finding scope=plan id=r2-resolved created=2026-09-26T15:52:41 phase=1 state=refuted resolves=r2 -->
### r2-resolved · finding [refuted] · resolves r2: two verify_merge tests are guards, not red-before-fix (phase 1)

Spec Test Plan lists them as guards for the fail-safe; the PR body will not call them red-before-fix.

<!-- fr:journal kind=finding scope=plan id=r3-resolved created=2026-09-26T15:52:41 phase=1 state=open resolves=r3 out_of_scope=true -->
### r3-resolved · finding [out-of-scope] · resolves r3: A reverted merge still passes the blob fallback (phase 1)

Follows from spec §A, not a defect of this change; noted for the operator.

<!-- fr:journal kind=finding scope=plan id=r4-resolved created=2026-09-26T15:52:41 phase=1 state=open resolves=r4 out_of_scope=true -->
### r4-resolved · finding [out-of-scope] · resolves r4: diff --name-only without -z quotes special paths (phase 1)

Pre-existing behaviour, fails safe.

<!-- fr:journal kind=finding scope=plan id=r5-resolved created=2026-09-26T15:52:41 phase=1 state=open resolves=r5 out_of_scope=true -->
### r5-resolved · finding [out-of-scope] · resolves r5: One rev-parse per commit touching the path (phase 1)

Spec accepts the bounded cost; early exit already present.

<!-- fr:journal kind=finding scope=plan id=r6-resolved created=2026-09-26T15:52:41 phase=1 state=refuted resolves=r6 -->
### r6-resolved · finding [refuted] · resolves r6: No test for path with space/dash/glob or failed rev-list (phase 1)

Path is only passed after `--` and inside <rev>:<path>, never parsed as an option; pathspec magic can only widen candidates and the blob compare uses the literal path, so no false pass.

<!-- fr:journal kind=review scope=plan id=review-phase-1-fragment-addition created=2026-09-26T17:27:37 phase=1 -->
### review-phase-1-fragment-addition · review · independent review of the release-bot fragment-deletion addition: no in-scope findings (phase 1)

Reviewer aae94ddac742e9ad4 read commits 3780778c and 709b3ab7: tests reproduce the real shape (squash adds fragment+code, release: commit deletes fragment), red on the original code (proven by the executor by restoring origin/main's local.py), negative guards non-vacuous, no .changes special case needed. Out of scope: byte-identical same-slug fragment collision (noted in spec), stale line refs in spec (pre-fix numbers).

<!-- fr:journal kind=review scope=plan id=review-phase-1-archive-addition created=2026-09-26T17:44:23 phase=1 -->
### review-phase-1-archive-addition · review · independent review of the archive-move addition (#598): no in-scope findings (phase 1)

Reviewer aa314fc56063d9e54: _archived_path matches archive.py for all five kinds (plans dir, specs, journals with scope subdir, runs, usage); fallback is load-bearing (reap test where the original path never reached origin/main); dirty/unpushed/git-error paths still refuse; negative guards non-vacuous; spec claims true. Out of scope, recorded in spec Non-goals: boilerplate false-match against an older archived copy on a slug-reused re-run (extension of #387's accepted tradeoff).

<!-- fr:journal kind=finding scope=plan id=opus-c1-blob-scan-cost created=2026-09-27T00:07:40 phase=1 state=open review_scope=in -->
### opus-c1-blob-scan-cost · finding [open] (reviewer: in scope) · per-commit rev-parse scan is O(commits) per path (phase 1)

local.py _branch_blob_was_on_base, multiplied by refs, archive alternate and gc sweep.

<!-- fr:journal kind=finding scope=plan id=opus-c2-branch-fetch-ignored created=2026-09-27T00:07:41 phase=1 state=open review_scope=in -->
### opus-c2-branch-fetch-ignored · finding [open] (reviewer: in scope) · branch fetch result discarded, no explicit refspec (phase 1)

Single-branch clone or failed fetch left origin/<b> stale; verify_merge could pass over a post-merge push.
