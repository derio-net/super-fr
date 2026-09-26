# Journal: 2026-09-26-isolation-gc-fetch-timeout

<!-- fr:journal kind=decision scope=spec id=timeout-helper created=2026-09-26T11:47:59 -->
### timeout-helper · decision · Bound the reap-hazard fetch

Route `_reap_hazard`'s default-branch fetch through `_run_network`, preserving the worktree cwd and failed-fetch hazard behavior. The regression test should assert the helper is used.

<!-- fr:journal kind=decision scope=spec id=post-merge-test-plan created=2026-09-26T11:47:59 -->
### post-merge-test-plan · decision · Verify targeted and full suites after merge

The operator accepts running the targeted isolation network-timeout tests and the full test suite after merge.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T11:49:34 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Test Plan omits the acceptance-matrix update

The Test Plan now requires linking the regression test in the acceptance matrix and moving its row to ci when the test lands.

<!-- fr:journal kind=review scope=spec id=spec-review-2026-09-26 created=2026-09-26T11:49:34 -->
### spec-review-2026-09-26 · review · Independent spec review: one finding

Reviewer ses_f22e295adffe6EvKDfQc0OLF4z verified `_reap_hazard`'s fetch and failure handling at local.py:1161-1175, `_run_network`'s timeout and cwd at local.py:2024-2031, and gc's fail-closed hazard handling at local.py:1540-1564. The in-scope Test Plan finding was fixed by adding the acceptance-matrix update.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T11:49:34 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Test Plan omits the acceptance-matrix update

Added the acceptance-matrix update to the spec Test Plan.

<!-- fr:journal kind=decision scope=spec id=skeleton-override-2026-09-26-isolation-gc-fetch-timeout created=2026-09-26T12:02:11 -->
### skeleton-override-2026-09-26-isolation-gc-fetch-timeout · decision · No separate walking-skeleton phase

This narrowly scoped change is a single fetch call and a regression test proving bounded execution and fail-closed handling. A separate trivial CI-smoke phase would not reduce delivery risk; the regression and implementation are an inseparable unit.
