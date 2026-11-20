<!-- fr:journal-schema=4 -->
# Journal: 2026-11-20-concurrent-hook-test-timeout

<!-- fr:journal kind=repro scope=debug id=62e0cc825dc5 created=2026-11-20T06:42:04+00:00 -->
### 62e0cc825dc5 · repro · test_two_concurrent_invocations_do_not_overlap times out at 60s in Release shards

Release runs 44629095391, 44633105801, 44683248617 (3 of 4 since #1573): subprocess.TimeoutExpired from run_twice's communicate(timeout=60) on bash -x fr-worktree-create.sh. PR CI (7 shards) passed. race_evidence never printed: the timeout raises before any assertion.

<!-- fr:journal kind=hypothesis scope=debug id=5dc59517daa6 created=2026-11-20T06:42:06+00:00 -->
### 5dc59517daa6 · hypothesis · run_twice drains the two hooks sequentially; hook 1 holding the lock blocks on a full stderr pipe

communicate() on proc 0 never reads proc 1's pipes. Both run under bash -x. If proc 1 wins the mkdir lock and writes >64KB of xtrace it blocks in write(2) holding the lock; proc 0 waits on the lock until the 60s timeout. Depends on who wins the lock (about half the runs) and on PATH length (xtrace expands PATH walks).
