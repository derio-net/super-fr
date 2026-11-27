<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-isolation-local-split

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T09:36:16+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke + fragment only, nothing to clean

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T09:41:44+00:00 phase=1 -->
### review-p1-1 · review · phase 1 review (runner.py move): no findings (phase 1)

Dispatched reviewer compared runner.py against local.py lines 50-171 at main: nine names unchanged, bodies identical, no import of fr.isolation.local, no re-export list, all callers migrated (incl. agent_worktrees.py and gitseam lazy import), forge-argv guard scans runner.py, budget 3100 for 3058 lines, fragment valid. Orchestrator confirmed with ruff check and 163 targeted tests (network_timeouts, module_budget, gc_routing, triage_collect, import_direction) passing.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-27T09:57:43+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · local.py budget set to 3000 but the plan's rule (round up to next 25, plus 25) on 2939 lines gives 2975 (phase 2)

tests/unit/test_tripwire_module_budget.py:27 at 02e587e64; P2.T1.S3 / P1.T2.S3 rule.

<!-- fr:journal kind=review scope=plan id=review-p2-1 created=2026-11-27T09:57:43+00:00 phase=2 -->
### review-p2-1 · review · phase 2 review (reap.py move): 1 finding (p2-r1) (phase 2)

Dispatched reviewer diffed the moved block byte-for-byte, checked reap.py's imports against the spec, every caller incl. lazy test imports, ReapRefused identity across modules, the guard entry; ruff/mypy clean, 163 targeted tests pass. Raised p2-r1 (budget slack), fixed in 93744980a.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-27T09:57:43+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: local.py budget set to 3000 but the plan's rule (round up to next 25, plus 25) on 2939 lines gives 2975 (phase 2)

Budget lowered to 2975 in 93744980a; module budget tripwire passes.
