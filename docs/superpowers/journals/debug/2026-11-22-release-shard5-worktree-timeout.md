<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-release-shard5-worktree-timeout

<!-- fr:journal kind=repro scope=debug id=9bf90ee02045 created=2026-11-22T20:36:53+00:00 -->
### 9bf90ee02045 · repro · Release shard 5/6 times out on test_two_concurrent_invocations_do_not_overlap, 3 runs in a row

Release run 45063126264 (8.3.0-rc.8, staged 331227f, base ffb03a7) and its two re-runs: shard 5/6, py3.11, -n auto, fails only tests/unit/test_hooks_worktree.py::test_two_concurrent_invocations_do_not_overlap with subprocess.TimeoutExpired after 60s in run_twice's communicate(). CI's 7-way shards on the same tree pass. On TimeoutExpired race_evidence never runs, so no lock trace is captured.
