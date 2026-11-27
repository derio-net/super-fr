<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-isolation-local-split

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T09:36:16+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke + fragment only, nothing to clean

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T09:41:44+00:00 phase=1 -->
### review-p1-1 · review · phase 1 review (runner.py move): no findings (phase 1)

Dispatched reviewer compared runner.py against local.py lines 50-171 at main: nine names unchanged, bodies identical, no import of fr.isolation.local, no re-export list, all callers migrated (incl. agent_worktrees.py and gitseam lazy import), forge-argv guard scans runner.py, budget 3100 for 3058 lines, fragment valid. Orchestrator confirmed with ruff check and 163 targeted tests (network_timeouts, module_budget, gc_routing, triage_collect, import_direction) passing.
