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

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-27T10:10:48+00:00 phase=4 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · fr docs check stale: docs/reference/dispatch-lifecycle.md covers fr_herdr/runner.py (edited at :118) but its reviewed stamp is not bumped (phase 4)

Belongs to phase 4: plan step P4.T2.S2 moves the reviewed stamp of every covered page the branch edits (spec R8). Filed against phase 4 so its review gates it.

<!-- fr:journal kind=review scope=plan id=review-p3-1 created=2026-11-27T10:10:48+00:00 phase=3 -->
### review-p3-1 · review · phase 3 review (branchrefs.py move): 1 finding (p3-r1, filed against phase 4) (phase 3)

Dispatched reviewer confirmed byte-identical bodies, imports (no fr.isolation.local), all callers migrated incl. gitseam lazy import and fr_herdr/runner.py, no monkeypatch left patching nothing, guard entry and budget 2650 for 2614 lines; ruff/mypy clean, 123 targeted tests pass.

<!-- fr:journal kind=discovery scope=plan id=p4-d1 created=2026-11-27T10:19:44+00:00 phase=4 -->
### p4-d1 · discovery · reviewed stamps cannot hold a colon (phase 4)

A `reviewed:` value containing `still true: ...` is unreadable YAML (fr docs check reports bad-page); the stamps use `still true, ...`. fr docs check also reads committed pages only, so stamps must be committed before it re-runs.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-27T10:19:44+00:00 phase=4 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: fr docs check stale: docs/reference/dispatch-lifecycle.md covers fr_herdr/runner.py (edited at :118) but its reviewed stamp is not bumped (phase 4)

docs/reference/dispatch-lifecycle.md (covers fr_herdr/runner.py) carries a 2026-11-27 reviewed stamp; fr docs check --base origin/main exits 0.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-27T10:19:44+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

budget and stamps only, nothing to clean

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-27T10:24:06+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · R2 AST guard (test_isolation_network_timeouts.py:281-302) misses relative imports (`from .local import X`, `from . import local`) (phase 4)

fr/isolation already uses relative imports (agent_worktrees.py:44-45); the guard compared node.module only.

<!-- fr:journal kind=review scope=plan id=review-p4-1 created=2026-11-27T10:24:06+00:00 phase=4 -->
### review-p4-1 · review · phase 4 review (landing.py move + whole feature): 1 finding (p4-r1) (phase 4)

Dispatched reviewer confirmed byte-identical bodies, landing.py imports per R2, only LocalWorktreeDevcontainerTarget/IsolationError/_git_common_dir still imported from local (own use), the branch_changes_present string patch still effective (58 tests), R7 class untouched across the feature, budget 2125 for 2084 lines, seven stamps with fr docs check exit 0; judged the comma in the stamp note correct (a colon is invalid YAML). Raised p4-r1, fixed in ded94bed5.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-27T10:24:06+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: R2 AST guard (test_isolation_network_timeouts.py:281-302) misses relative imports (`from .local import X`, `from . import local`) (phase 4)

ded94bed5: `_local_imports` resolves relative imports against fr.isolation; planted tests cover absolute, aliased, relative, parent-relative and lazy forms plus a negative sibling case; 27 passed.
