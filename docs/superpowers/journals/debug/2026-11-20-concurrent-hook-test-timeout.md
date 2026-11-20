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

<!-- fr:journal kind=root-cause scope=debug id=8b4fb1f742f6 created=2026-11-20T06:45:10+00:00 -->
### 8b4fb1f742f6 · root-cause · Second, older cause: the hooks' mkdir lock is entered twice on Linux CI (exit-1 / OVERLAP variant)

PR #1584 attempt 1 (py3.11 shard 3): both hooks' 'mkdir <lock>' succeeded 2 ms apart (.268119 and .270165), no cat/kill/rm/sleep between mkdir and trap, both wrote pid files, both stubs ran (OVERLAP) and hook 0's stub exited 1 on its rmdir. Same signature as #1463's instrumented recurrence on #1536 (66 us apart, before #1573). So it predates #1573; #1573 only moved how often it is seen. The hooks' exclusion rests on an external mkdir being atomic; the runner is ubuntu-26.04. Mechanism of mkdir succeeding twice is unverified (not reproducible on macOS: 480x2 passes in #1463). Decision: acquire the lock with bash's own noclobber redirect (open O_EXCL in the shell, no external binary), so the exclusion no longer depends on what mkdir does.
