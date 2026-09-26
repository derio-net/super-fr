# Journal: 2026-09-26-isolation-network-timeouts

<!-- fr:journal kind=decision scope=plan id=plan-two-phases created=2026-09-26T07:38:58 -->
### plan-two-phases · decision · Two phases, not one

self-review errors when the walking skeleton is the only agentic phase; phase 1 is the cwd-param skeleton, phase 2 the real routing plus matrix and version bump.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T07:40:06 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

single-line parameter addition, nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-26T07:41:24 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Phase 1 tests depend on GIT_SSH* being set in the environment (phase 1)

The recorder captured every runner call, and _network_env adds a git config probe when GIT_SSH_COMMAND/GIT_SSH are unset, so both tests failed in a clean env. Reproduced with env -u.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-26T07:41:24 phase=1 -->
### p1-review · review · independent review of phase 1: 1 finding (phase 1)

Independent reviewer confirmed the local.py change is correct and existing callers unchanged; raised p1-r1 (in scope), fixed by selecting recorded calls by argv.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-26T07:41:24 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Phase 1 tests depend on GIT_SSH* being set in the environment (phase 1)

The recorder now records only the git status call; both tests pass with and without GIT_SSH* set.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-26T07:54:47 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the 'Deliberately a SEPARATE branch' docstring wording is still true after the swap; three call-site swaps, nothing to consolidate

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-09-26T07:54:47 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

matrix move, version bump and gate only; no code to clean
