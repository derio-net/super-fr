# Journal: 2026-09-26-container-git-ownership

<!-- fr:journal kind=decision scope=spec id=trust-scope created=2026-09-26T15:02:21 -->
### trust-scope · decision · safe.directory trust scope in POST_CREATE

Operator chose the workspace path via $PWD, not a wildcard.

<!-- fr:journal kind=decision scope=spec id=call-scope created=2026-09-26T15:02:21 -->
### call-scope · decision · Which fr git calls carry -c safe.directory

Operator chose all calls through fr.git.git_answer plus the raw update-index restore in commit.py.

<!-- fr:journal kind=decision scope=spec id=test-plan-and-models created=2026-09-26T15:02:21 -->
### test-plan-and-models · decision · No post-merge test plan; all tiers claude-sonnet-5

Operator confirmed both.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T15:03:59 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · §3.A subdirectory-root claim is wrong: safe.directory=<cwd> does not cover a toplevel above cwd

git matches safe.directory against the worktree toplevel, so git_context's first rev-parse from a subdirectory root is refused. Evidence: commit.py:291,303; git.py:107-124.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T15:03:59 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · record/apply.py _is_tracked and _short_head bypass the seam

Raw git -C calls at record/apply.py:742-759 degrade silently in a foreign-owned tree (misclassify tracked records, drop sha).

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T15:03:59 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Override in shared git_answer contradicts the stated non-goal

Non-goal wording needed a precise definition of the trust boundary, and a note that -c appends to user config.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T15:03:59 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Test Plan lacks a subdirectory-root case; scaffold.py line ref off

workspaceMount is at scaffold.py:512-513, not 510.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-26T15:03:59 state=open review_scope=out -->
### s5 · finding [open] (reviewer: out of scope) · Brainstorm record path did not exist when reviewer looked

Process note about dispatch timing, not a spec defect.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T15:03:59 -->
### spec-review · review · independent spec review: 5 findings (4 in scope, 1 out of scope)

Reviewer verified git.py:107, commit.py:57/264/291/303/683-691, scaffold.py:426/497-513, records_commit.py:40 against the spec.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T15:03:59 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: §3.A subdirectory-root claim is wrong: safe.directory=<cwd> does not cover a toplevel above cwd

§3.A now walks up to the nearest .git ancestor (safe_directory_args) and Test Plan 2 covers a subdirectory root.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T15:03:59 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: record/apply.py _is_tracked and _short_head bypass the seam

§3.A lists record/apply.py _is_tracked/_short_head as call sites; Test Plan 3.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T15:03:59 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Override in shared git_answer contradicts the stated non-goal

§1 non-goal and §3.A state the trust boundary precisely.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T15:03:59 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Test Plan lacks a subdirectory-root case; scaffold.py line ref off

Test Plan rewritten; line refs corrected.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-26T15:03:59 state=open resolves=s5 out_of_scope=true -->
### s5-resolved · finding [out-of-scope] · resolves s5: Brainstorm record path did not exist when reviewer looked

Process timing of the brainstorm record; this change did not cause it.
