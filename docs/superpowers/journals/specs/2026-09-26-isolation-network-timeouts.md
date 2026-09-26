# Journal: 2026-09-26-isolation-network-timeouts

<!-- fr:journal kind=decision scope=spec id=d1-forge-lookup-via-run-network created=2026-09-26T07:36:31 -->
### d1-forge-lookup-via-run-network · decision · Forge-CLI default-branch lookup goes through _run_network

Per gh#618. A timeout (exit 124) already falls through to main.

<!-- fr:journal kind=decision scope=spec id=d2-verify-merge-fetches-via-run-network created=2026-09-26T07:36:31 -->
### d2-verify-merge-fetches-via-run-network · decision · verify-merge's two fetches go through _run_network (cwd param added)

Per the batch note. _verdict fetches from the worktree, so _run_network gains an optional cwd.

<!-- fr:journal kind=finding scope=spec id=f1-reap-hazard-fetch-untimed created=2026-09-26T07:36:31 state=open review_scope=out -->
### f1-reap-hazard-fetch-untimed · finding [open] (reviewer: out of scope) · _reap_hazard's git fetch (gc) is also untimed

Same defect class, not named in the batch; gc's unlanded-content check fetches with self.run. Filed out of scope, to be tracked separately.

<!-- fr:journal kind=finding scope=spec id=f1-reap-hazard-fetch-untimed-resolved created=2026-09-26T07:36:31 state=open resolves=f1-reap-hazard-fetch-untimed out_of_scope=true -->
### f1-reap-hazard-fetch-untimed-resolved · finding [out-of-scope] · resolves f1-reap-hazard-fetch-untimed: _reap_hazard's git fetch (gc) is also untimed

Not caused by this change and not in the batch's scope; the batch names the default-branch lookup and verify-merge only.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T07:36:31 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Dispatched from a triage batch (isolation-timeouts, gh#618): the brief fixes scope (default-branch lookup + verify-merge fetch), branch, version 4.23.2, model and PR rules; the fix is mechanical (route through the existing _run_network) and no operator-owned decision remained.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T07:37:59 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Test Plan item 2 conflates the two fetches' effect on fetched

Only _verdict's fetch feeds fetched; _branch_refs' is discarded. Split the case.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T07:37:59 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · _run_network adds a hidden git config call

Extra local git config call precedes every _run_network call; tests must select by argv.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T07:37:59 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Spec omits matrix and version obligations

Cite the acceptance row and the 4.23.2 bump.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T07:37:59 -->
### spec-review · review · independent spec review: 3 findings

fr-spec-reviewer verified every file:line claim in the spec; raised s1-s3, all in scope, all fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T07:37:59 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Test Plan item 2 conflates the two fetches' effect on fetched

§3.C and Test Plan 2 now separate the two fetches.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T07:37:59 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: _run_network adds a hidden git config call

§3.B states the extra git config call; Test Plan 3 selects by argv.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T07:37:59 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Spec omits matrix and version obligations

New §4 Obligations names the matrix row and the 4.23.2 bump.
