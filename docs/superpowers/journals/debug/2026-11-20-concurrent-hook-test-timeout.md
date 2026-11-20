<!-- fr:journal-schema=4 -->
# Journal: 2026-11-20-concurrent-hook-test-timeout

<!-- fr:journal kind=repro scope=debug id=62e0cc825dc5 created=2026-11-20T06:42:04+00:00 -->
### 62e0cc825dc5 · repro · test_two_concurrent_invocations_do_not_overlap times out at 60s in Release shards

Release runs 44629095391, 44633105801, 44683248617 (3 of 4 since #1573): subprocess.TimeoutExpired from run_twice's communicate(timeout=60) on bash -x fr-worktree-create.sh. PR CI (7 shards) passed. race_evidence never printed: the timeout raises before any assertion.

<!-- fr:journal kind=hypothesis scope=debug id=5dc59517daa6 created=2026-11-20T06:42:06+00:00 -->
### 5dc59517daa6 · hypothesis · run_twice drains the two hooks sequentially; hook 1 holding the lock blocks on a full stderr pipe

communicate() on proc 0 never reads proc 1's pipes. Both run under bash -x. If proc 1 wins the mkdir lock and writes >64KB of xtrace it blocks in write(2) holding the lock; proc 0 waits on the lock until the 60s timeout. Depends on who wins the lock (about half the runs) and on PATH length (xtrace expands PATH walks).

<!-- fr:journal kind=root-cause scope=debug id=34765ce58e70 created=2026-11-20T06:42:08+00:00 -->
### 34765ce58e70 · root-cause · Sequential pipe drain in run_twice deadlocks once the hook's xtrace exceeds the pipe buffer; #1573 tripled the trace

Measured locally with a 35-entry PATH and PS4='+ ': hook xtrace was 47376 B before #1573 and 150739 B after (fr_jq's _fr_first_candidate PATH walks, ~1570 traced lines). 150KB > 64KB Linux pipe buffer; the old 47KB sat under it. Test harness defect, not a hook defect: the hook and its lock behave correctly. The sibling removals test shares run_twice and is exposed the same way.
