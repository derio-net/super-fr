<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-release-shard5-worktree-timeout

<!-- fr:journal kind=repro scope=debug id=9bf90ee02045 created=2026-11-22T20:36:53+00:00 -->
### 9bf90ee02045 · repro · Release shard 5/6 times out on test_two_concurrent_invocations_do_not_overlap, 3 runs in a row

Release run 45063126264 (8.3.0-rc.8, staged 331227f, base ffb03a7) and its two re-runs: shard 5/6, py3.11, -n auto, fails only tests/unit/test_hooks_worktree.py::test_two_concurrent_invocations_do_not_overlap with subprocess.TimeoutExpired after 60s in run_twice's communicate(). CI's 7-way shards on the same tree pass. On TimeoutExpired race_evidence never runs, so no lock trace is captured.

<!-- fr:journal kind=ruled-out scope=debug id=c7a9b9372ba1 created=2026-11-22T20:36:55+00:00 -->
### c7a9b9372ba1 · ruled-out · Not slowness: the test alone takes ~2.5s (macOS) and ~3.5s (Linux docker)

A 60s timeout is a hang, not an overrun.

<!-- fr:journal kind=ruled-out scope=debug id=d8f7ca8f9f39 created=2026-11-22T20:36:56+00:00 -->
### d8f7ca8f9f39 · ruled-out · Not a leaked FR_HARNESS_FR pin

Running the test with FR_HARNESS_FR set to the real venv fr still passes (conftest drops the pin).

<!-- fr:journal kind=ruled-out scope=debug id=d982011bfda9 created=2026-11-22T20:36:58+00:00 -->
### d982011bfda9 · ruled-out · Not reproduced by release shard 5 on macOS

The same shard (durations-plan.json, --splits 6 --group 5, -n 4, -m '') passes locally on macOS: 2881 passed. Linux-specific or runner-specific.

<!-- fr:journal kind=ruled-out scope=debug id=276e24ae2bdc created=2026-11-22T20:40:31+00:00 -->
### 276e24ae2bdc · ruled-out · Not reproduced on Linux either: the staged release commit's shard 5/6 in Docker passes the test

Cloned staged.bundle (331227f), origin/main pinned to ffb03a7, python 3.11 bookworm, 2 CPUs, -n 4, durations-plan.json: the target test passed (34 other failures are container gaps: no rsync, root user). So the hang needs something about the GitHub runner itself, not only Linux + test order. Also read: release.py strips only forge credentials from the env; the hook's EXIT trap is never replaced and nothing exec's past it.

<!-- fr:journal kind=hypothesis scope=debug id=1d695ea79a55 created=2026-11-22T20:48:04+00:00 -->
### 1d695ea79a55 · hypothesis · PR #1625 test_git_cache misses: a process-wide _UNKNOWN system-config memo poisons every later cached question on that worker

CI run 45065556107, py3.14 shard 4/7: three include tests on worker gw3 fail in _hit (the cached re-ask starts git config + git remote). fr.git_cache._SYSTEM_MEMO is process-global and memoises _UNKNOWN on purpose (l-errors-r2); with _UNKNOWN every scope declines ('git would not name its system config path'). Confirmed: seeding the memo with _UNKNOWN reproduces the exact failure shape on test_an_onbranch_include_flips_with_a_checkout. Open: which earlier test on the worker made the probe fail.

<!-- fr:journal kind=root-cause scope=debug id=rc-git-memo created=2026-11-22T20:57:46+00:00 -->
### rc-git-memo · root-cause · test_git_cache misses: _SYSTEM_MEMO outlives its test, so one failed probe poisons the xdist worker

fr.git_cache._SYSTEM_MEMO is the one process-global fr cache with no autouse reset in tests/conftest.py. A test that fakes git away while a scope is open memoises _UNKNOWN under the real git's key; every later scope on that worker declines ('git would not name its system config path'), and the hit tests count the extra git starts. Production impact: none (a CLI process is short-lived, a decline only loses caching).

<!-- fr:journal kind=finding scope=debug id=f-git-memo created=2026-11-22T20:57:48+00:00 state=fixed -->
### f-git-memo · finding [fixed] · conftest empties _SYSTEM_MEMO before every test

Failing test first: test_a_test_never_meets_a_previous_tests_system_config_answer (red, and with it test_a_decline_is_named_on_stderr_under_the_debug_variable and, under -n 4, four hit tests, exactly PR #1625's shape), seeded by test_a_failed_system_config_probe_is_remembered_for_the_process. Fix: autouse _fresh_git_system_config_memo in tests/conftest.py. 49/49 serially and on three -n 4 runs.

<!-- fr:journal kind=ruled-out scope=debug id=336fa4e7cb4f created=2026-11-22T20:59:03+00:00 -->
### 336fa4e7cb4f · ruled-out · Not (likely) a pipe-buffer deadlock in run_twice's one-at-a-time drain

Hypothesis: procs[1] wins the lock and blocks writing its unread xtrace (64 KiB Linux pipe) while procs[0] waits on the lock. Measured: the xtrace is ~187 KB BEFORE the lock (PATH walks, ~10 KB per PATH entry) and only ~10 KB under it, so an undrained hook blocks before it can take the lock and holds nothing. A forced 'second-drained wins the lock' run passes on macOS and on Linux (docker). It would need a pre-lock trace in a ~10 KB window below 64 KiB: too narrow for 3/3. Also: the diag-shard5 workflow (this branch's tests, release shard 5/6 args, durations-plan.json, 3 attempts on ubuntu-latest) passed all three, so what remains is what release.py itself adds: the staged commit, the nested uv run, its env.

<!-- fr:journal kind=root-cause scope=debug id=rc-race-drain created=2026-11-22T21:05:52+00:00 -->
### rc-race-drain · root-cause · run_twice drains the two hooks one at a time, so a lock holder whose unread stderr pipe fills deadlocks the race

Evidence (diag run 45069567075, the release's exact shard 5/6, 3/3 hung): in every run procs[1] held the lock (lock pid == procs[1]), its stub had finished (stub trace 'exit rmdir=0'), and it was alive in state S with no child, its stderr at 62,875-63,023 bytes: the next xtrace line does not fit the 64 KiB Linux pipe, so bash blocks on write(2) while holding the lock. procs[0] loops on the lock; Python sits in procs[0].communicate() and never reads procs[1]. The 'refutation' above was wrong: it measured a 35-entry macOS PATH (187 KB before the lock); the trace scales with PATH and tmp-path length, and under release.py's nested uv run the whole trace lands just past 64 KiB. Not a hook bug: the hook serialises correctly; the harness couples the test to pipe capacity.

<!-- fr:journal kind=finding scope=debug id=f-race-drain created=2026-11-22T21:08:43+00:00 state=fixed -->
### f-race-drain · finding [fixed] · run_twice drains both copies to files instead of pipes

Failing test first: test_the_race_drains_both_hooks_at_once (two copies each write 200 KB to stderr, then wait for both): hung at its 15 s deadline under the one-at-a-time pipe drain, on macOS too; passes in 0.5 s with stdout/stderr redirected to per-copy files. A hang now fails with the lock holder, the ps table and both full traces (kept from the diagnosis). The hook is unchanged: it serialised correctly in every captured run.
