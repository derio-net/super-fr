# Journal: 2026-09-26-release-scripts-hardening

<!-- fr:journal kind=decision scope=plan id=p-one-phase created=2026-09-26T12:10:27 -->
### p-one-phase · decision · One agentic phase, tier standard

Small change per brief; no skeleton marker, no tracking_issue.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T12:20:09 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

RED-only task: it adds tests, no production code exists yet to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T12:20:09 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

Each fix is a minimal, single-purpose edit; the refactor pass is P1.T3.S1 (helper tidied, ruff clean).

<!-- fr:journal kind=finding scope=plan id=r1 created=2026-09-26T12:24:15 phase=1 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · Scoping tests pass on old code (project first in fixtures) (phase 1)

Only 2 of the new TOML tests were red before the fix.

<!-- fr:journal kind=finding scope=plan id=r2 created=2026-09-26T12:24:15 phase=1 state=open review_scope=in -->
### r2 · finding [open] (reviewer: in scope) · Column-0 array element matches table header regex (phase 1)

Fails closed but the boundary regex can misread.

<!-- fr:journal kind=finding scope=plan id=r3 created=2026-09-26T12:24:15 phase=1 state=open review_scope=in -->
### r3 · finding [open] (reviewer: in scope) · Atomicity docstring overclaims (phase 1)

Only pyproject rewrites are precomputed.

<!-- fr:journal kind=finding scope=plan id=r4 created=2026-09-26T12:24:15 phase=1 state=open review_scope=out -->
### r4 · finding [open] (reviewer: out of scope) · Only a literal [project] table is recognised (phase 1)

Fail-closed; dotted-key/spaced variants are not in this repo and not introduced by this change.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-26T12:24:15 phase=1 -->
### review-phase-1 · review · independent code review of phase 1: 4 findings (3 in scope, 1 out) (phase 1)

Dispatched reviewer verified the rewrite against every real pyproject in a temp copy, the three test files, ci.yml and requires_bump edge cases; no blocking bugs.

<!-- fr:journal kind=finding scope=plan id=r1-resolved created=2026-09-26T12:24:15 phase=1 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: Scoping tests pass on old code (project first in fixtures) (phase 1)

Every scoping fixture now has a decoy [tool.y] version ahead of [project]; all 7 new tests confirmed red on origin/main's version_surfaces.py.

<!-- fr:journal kind=finding scope=plan id=r2-resolved created=2026-09-26T12:24:15 phase=1 state=fixed resolves=r2 -->
### r2-resolved · finding [fixed] · resolves r2: Column-0 array element matches table header regex (phase 1)

Added a post-rewrite tomllib parse check (only project.version may differ) plus a test; the misread boundary now refuses.

<!-- fr:journal kind=finding scope=plan id=r3-resolved created=2026-09-26T12:24:15 phase=1 state=fixed resolves=r3 -->
### r3-resolved · finding [fixed] · resolves r3: Atomicity docstring overclaims (phase 1)

Docstring now says the guarantee covers the pyproject rewrites.

<!-- fr:journal kind=finding scope=plan id=r4-resolved created=2026-09-26T12:24:15 phase=1 state=open resolves=r4 out_of_scope=true -->
### r4-resolved · finding [out-of-scope] · resolves r4: Only a literal [project] table is recognised (phase 1)

Pre-existing fail-closed limitation of the [project] literal; no such file exists in the repo.
