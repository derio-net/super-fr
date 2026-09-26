# Journal: 2026-09-26-isolation-gc-fetch-timeout

<!-- fr:journal kind=decision scope=plan id=P1-use-network-timeout-on-reap-hazard-fetch created=2026-09-26T12:08:44 phase=1 -->
### P1-use-network-timeout-on-reap-hazard-fetch · decision · Route _reap_hazard's origin fetch through _run_network for bounded execution (phase 1)

The fetch in `_reap_hazard` (line 1164 in packages/fr/src/fr/isolation/local.py)
now calls `self._run_network(["git", "fetch", "origin", default], cwd=state.worktree)`
instead of `self.run(...)`. This applies the 60-second network timeout defined by
`_NETWORK_TIMEOUT_S` and maintains the existing fail-closed behavior: a timeout
(exit code 124) is read as `unverifiable`, deferring the reap rather than treating
network failure as safe to proceed. The local-first checks (git status) and
no-origin handling remain unchanged.

<!-- fr:journal kind=discovery scope=plan id=P1-regression-test-coverage created=2026-09-26T12:08:44 phase=1 -->
### P1-regression-test-coverage · discovery · Regression test added to verify _reap_hazard fetch is bounded and timeout-safe (phase 1)

Added `test_reap_hazard_fetch_is_bounded_and_timeout_is_unverifiable` to
tests/unit/test_isolation_network_timeouts.py. The test verifies that:
1. The fetch call to `origin/<default>` uses `_run_network` (evidenced by
   the timeout kwarg in the runner call)
2. The call is made with the worktree as cwd (where the branch exists)
3. A fetch timeout (exit 124) returns an `unverifiable` hazard, deferring gc

All 9 tests in test_isolation_network_timeouts.py pass. All 19 gc-related
isolation tests pass (test_isolation_gc_*.py). No regressions detected in
lint, format, or type checking.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T12:08:44 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

No cleanup needed: the fetch routing change is minimal and requires no refactoring

<!-- fr:journal kind=review scope=plan id=phase-1-code-review created=2026-09-26T12:10:29 phase=1 -->
### phase-1-code-review · review · Independent review of isolation gc fetch timeout (phase 1)

Reviewer ses_f22cf8e9affeOpmMoMwBAkBn27 reviewed the spec, plan and diff. No findings. Confirmed the `_run_network` call preserves `cwd=state.worktree`, nonzero results remain `unverifiable`, GC skips the hazard, and the regression test covers timeout, cwd and failure behavior. Targeted network timeout tests: 9 passed.
