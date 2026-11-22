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
