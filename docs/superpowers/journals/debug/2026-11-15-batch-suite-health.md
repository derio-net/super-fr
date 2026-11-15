<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-suite-health

<!-- fr:journal kind=repro scope=debug id=7145eae76da2 created=2026-11-15T07:19:35+00:00 -->
### 7145eae76da2 · repro · Batch suite-health: member symptoms and repro attempts

#1463: CI logs show both concurrency failures are real double-holds of the hook lock, not timeouts. Remove test (PR #1458 shard py3.11/3): stub log holds two 'isolation down' lines plus OVERLAP. Create test (v7.0.0 release shard 3): the stub's trailing rmdir of in-flight failed, so 'fr isolation up failed' — meaning the other copy had removed in-flight, also an overlap. Stress repro of the remove hook pair: 120 trials on macOS under 24 CPU burners, 80 trials in an ubuntu:24.04 container under load — 0 overlaps. #1280/#1463 test files (test_install_atomic, test_run_evidence_visual, test_records_commit, test_hooks_worktree): 115 passed at host load ~11 with -n 4.
