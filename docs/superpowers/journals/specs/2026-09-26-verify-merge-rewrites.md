# Journal: 2026-09-26-verify-merge-rewrites

<!-- fr:journal kind=decision scope=spec id=d1-refs-both created=2026-09-26T15:07:02 -->
### d1-refs-both · decision · verify_merge checks origin/<branch> AND local

Operator: check fetched remote and local branch, as verify_merge_reaped does; unpushed local work still refuses.

<!-- fr:journal kind=decision scope=spec id=d2-fetch-fail-fallback created=2026-09-26T15:07:02 -->
### d2-fetch-fail-fallback · decision · Failed branch fetch falls back to local ref

Operator: a failed fetch is not a verdict; use the refs that resolve (GitHub deletes merged branches).

<!-- fr:journal kind=decision scope=spec id=d3-matrix-row created=2026-09-26T15:07:02 -->
### d3-matrix-row · decision · Add one acceptance matrix row

Operator: one new row, status ci once the test lands.

<!-- fr:journal kind=discovery scope=spec id=x1-blob-fallback created=2026-09-26T15:07:02 -->
### x1-blob-fallback · discovery · Fix A via blob equality against merge_base..base_ref

Per issue #598 option 1; existing whole-file and per-line checks run first, fallback only adds passes backed by base history.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T15:08:42 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Spec cites wrong line numbers for two helpers

local.py:259 and :1036, not :263/:1043.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T15:08:42 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Fix A fallback ambiguous for the early-return paths

Say whether the empty-added and path-absent returns reach the fallback.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T15:08:42 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Test Plan does not cover _reap_hazard gain

Widened pass loosens the reap guard; needs a test.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T15:08:42 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · State verify_merge raises when neither ref resolves

_branch_refs runs at repo_root and raises IsolationError; add to design and Test Plan.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-26T15:08:42 state=open review_scope=out -->
### s5 · finding [open] (reviewer: out of scope) · Blob equality misses concurrent-edit-then-rewrite

Known limit of #598 option 1; fails safe.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T15:08:42 -->
### spec-review · review · independent spec review: 5 findings (4 in, 1 out)

Reviewer a6c16f87ab38181f3 checked decisions d1-d3 and x1 against local.py; all named helpers verified.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T15:08:42 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Spec cites wrong line numbers for two helpers

Line numbers corrected.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T15:08:42 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Fix A fallback ambiguous for the early-return paths

Fallback runs on every False path where the branch still has the file; pure branch deletion stays STOP; test added to Test Plan.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T15:08:42 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Test Plan does not cover _reap_hazard gain

_reap_hazard test added to Test Plan.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T15:08:42 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: State verify_merge raises when neither ref resolves

Design line and Test Plan test added.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-26T15:08:42 state=open resolves=s5 out_of_scope=true -->
### s5-resolved · finding [out-of-scope] · resolves s5: Blob equality misses concurrent-edit-then-rewrite

Inherent to option 1 of #598, not caused by this change; recorded as a known limit in Non-goals; fails safe.

<!-- fr:journal kind=finding scope=spec id=opus-s1 created=2026-09-27T00:07:33 state=open review_scope=in -->
### opus-s1 · finding [open] (reviewer: in scope) · §C claimed archive never rewrites moved bytes; usage is re-captured first

archive.py _archive_usage -> upsert_capture replaces the host entry before git mv.

<!-- fr:journal kind=finding scope=spec id=opus-s2 created=2026-09-27T00:07:34 state=open review_scope=in -->
### opus-s2 · finding [open] (reviewer: in scope) · §C test passed on §A alone

The squash commit carries the branch blob at the original path; §C needed a test that fails without _archived_path.
