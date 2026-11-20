<!-- fr:journal-schema=4 -->
# Journal: 2026-11-20-concurrent-hook-test-timeout

<!-- fr:journal kind=repro scope=debug id=62e0cc825dc5 created=2026-11-20T06:42:04+00:00 -->
### 62e0cc825dc5 · repro · test_two_concurrent_invocations_do_not_overlap times out at 60s in Release shards

Release runs 44629095391, 44633105801, 44683248617 (3 of 4 since #1573): subprocess.TimeoutExpired from run_twice's communicate(timeout=60) on bash -x fr-worktree-create.sh. PR CI (7 shards) passed. race_evidence never printed: the timeout raises before any assertion.
