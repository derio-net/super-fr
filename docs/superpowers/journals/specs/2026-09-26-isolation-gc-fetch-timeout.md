# Journal: 2026-09-26-isolation-gc-fetch-timeout

<!-- fr:journal kind=decision scope=spec id=timeout-helper created=2026-09-26T11:47:59 -->
### timeout-helper · decision · Bound the reap-hazard fetch

Route `_reap_hazard`'s default-branch fetch through `_run_network`, preserving the worktree cwd and failed-fetch hazard behavior. The regression test should assert the helper is used.

<!-- fr:journal kind=decision scope=spec id=post-merge-test-plan created=2026-09-26T11:47:59 -->
### post-merge-test-plan · decision · Verify targeted and full suites after merge

The operator accepts running the targeted isolation network-timeout tests and the full test suite after merge.
