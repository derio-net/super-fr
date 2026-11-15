<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-suite-health

<!-- fr:journal kind=repro scope=debug id=7145eae76da2 created=2026-11-15T07:19:35+00:00 -->
### 7145eae76da2 · repro · Batch suite-health: member symptoms and repro attempts

#1463: CI logs show both concurrency failures are real double-holds of the hook lock, not timeouts. Remove test (PR #1458 shard py3.11/3): stub log holds two 'isolation down' lines plus OVERLAP. Create test (v7.0.0 release shard 3): the stub's trailing rmdir of in-flight failed, so 'fr isolation up failed' — meaning the other copy had removed in-flight, also an overlap. Stress repro of the remove hook pair: 120 trials on macOS under 24 CPU burners, 80 trials in an ubuntu:24.04 container under load — 0 overlaps. #1280/#1463 test files (test_install_atomic, test_run_evidence_visual, test_records_commit, test_hooks_worktree): 115 passed at host load ~11 with -n 4.

<!-- fr:journal kind=hypothesis scope=debug id=a947635ae581 created=2026-11-15T07:19:37+00:00 -->
### a947635ae581 · hypothesis · #1463 is a race in the mkdir lock's stale-holder reclaim

Hypothesis: the dead-holder reclaim (cat pid; kill -0 fails; rm -rf lock) can delete a live lock. Code read of fr-worktree-create.sh:116-126 and fr-worktree-remove.sh:28-38: with only two contenders every interleaving examined leaves one holder (the reclaim needs a third actor to delete a fresh lock). Not confirmed, and not reproduced locally or on Linux. Open.

<!-- fr:journal kind=finding scope=debug id=multi-root-cause created=2026-11-15T07:19:39+00:00 state=open -->
### multi-root-cause · finding [open] · The batch spans several independent root causes

#1289 (base_ref interpolated into run:) and #1288 (jobs with no timeout-minutes) are CI-workflow hygiene. #1428 is shard wall clock against the ci.yml budget. #1225 is cross-session host saturation (-n auto x N sessions, macOS git shim). #1280 is wall-clock-tight assertions failing under that load. #1463 is a double-hold of the worktree hook lock seen on CI. These do not share one cause; per the batch's rules, stop and ask before fixing any.

<!-- fr:journal kind=decision scope=debug id=1313d85ab59b created=2026-11-15T07:23:28+00:00 decided_by=operator -->
### 1313d85ab59b · decision · One PR, one fix per root cause

Operator chose: keep the single batch PR but fix each cause on its own with its own test. #1463's lock is tightened only if it can be reproduced first; otherwise split it out.
