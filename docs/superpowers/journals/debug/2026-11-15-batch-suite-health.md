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

<!-- fr:journal kind=finding scope=debug id=ci-hygiene created=2026-11-15T07:24:46+00:00 state=fixed -->
### ci-hygiene · finding [fixed] · ci.yml: base_ref routed through env; every job bounded

change-fragment and docs-check read BASE_REF from env: instead of interpolating github.base_ref into run: (#1289). Ten jobs gained timeout-minutes, each 5x+ over its measured duration on run 43639946152 (#1288). Pinned by tests/unit/test_ci_workflow_hygiene.py (red before, green after).

<!-- fr:journal kind=ruled-out scope=debug id=a5654773c2d5 created=2026-11-15T07:29:10+00:00 -->
### a5654773c2d5 · ruled-out · #1428 is not scenario-test CPU contention skewing the split

Plan durations balance every py3.14 shard at 824s, yet actual sums ran 597-1104s (run 43639946152). Across three main runs the shard slowdown does not follow how many scenario seconds the shard held (shard 6, 167s planned scenarios: x1.34 in one run, x0.74 in another), and the non-scenario tests in a shard slow by exactly the shard's own factor. Shard time therefore tracks the runner's speed (x0.72 to x1.40), not the mix. The split is sound.

<!-- fr:journal kind=root-cause scope=debug id=ci-shard-tail created=2026-11-15T07:46:48+00:00 -->
### ci-shard-tail · root-cause · #1428: shard wall clock = runner speed x work, plus a late long-test tail

Per shard the pytest step is ~35 s of collection, then serial work / 4 workers, plus a tail where xdist's load scheduler hands a long scenario test out late and it runs alone (shard py3.14/2: last 8% of progress took 77 s; work/4 = 242 s, tests ran 293 s). Runner speed varies x0.72-x1.40 between runs and scales every test equally. LPT simulated on that run's durations reaches work/4 on every shard (saves 16-52 s). Fix: tests/_shard_order.py + conftest hooks order a --splits run longest-first with --maxschedchunk 1. Whether a 7th shard is still needed is decided from this PR's CI timings.

<!-- fr:journal kind=finding scope=debug id=auto-workers created=2026-11-15T07:49:18+00:00 state=fixed -->
### auto-workers · finding [fixed] · #1225: -n auto is load-aware outside CI; FR_PYTEST_WORKERS overrides

tests/_workers.py answers xdist's pytest_xdist_auto_num_workers: FR_PYTEST_WORKERS when set (a bad value is a UsageError), every CPU under CI, else CPUs minus round(load1), floor 2. Live: 6 of 12 at load ~6; 3 with FR_PYTEST_WORKERS=3. tmp_path_retention_policy = failed. Pinned by tests/unit/test_auto_workers.py. Not done: the host-wide suite lock (proposal 1). The macOS git shim (proposal 3) did not reproduce here: 50 calls through /usr/bin/git took 0.65 s against 0.59 s for the resolved binary.

<!-- fr:journal kind=root-cause scope=debug id=visual-real-clock created=2026-11-15T07:54:28+00:00 -->
### visual-real-clock · root-cause · #1280: test_run_evidence_visual mixes a synthetic transcript clock with the real mtime

The tests stamp transcript reads at the unit's open time + 1-2 s, but _fresh_shot leaves the screenshot's mtime at real now. fr.run.visual counts a read only from mtime - SLACK (1 s) on, so when more than ~3 s pass between _advance opening the unit and _fresh_shot writing the file, every read predates the write and the check refuses. Repro: a 4 s sleep at the top of _fresh_shot fails 6 tests (inline_implement_phase, named_script_that_was_run, dispatched_implement_phase, unclaimed_unit_owing_visual, review_reads, deliver_orchestrator_reads), the set #1280/#1296 saw under load.

<!-- fr:journal kind=finding scope=debug id=visual-clock created=2026-11-15T07:56:06+00:00 state=fixed -->
### visual-clock · finding [fixed] · test_run_evidence_visual: fresh shots stamped at the unit's open time

_advance records the opened stamp; _fresh_shot sets the file's mtime to it, so the file and the synthetic transcript share one clock. With the 4 s repro sleep still in _fresh_shot: 60 passed (6 failed before). Without it: 60 passed.

<!-- fr:journal kind=finding scope=debug id=stuck-lock-clock created=2026-11-15T07:57:26+00:00 state=fixed -->
### stuck-lock-clock · finding [fixed] · stuck index-lock test: the wait runs on a fake clock

Root cause: the test timed the whole commit_records call on the real clock, so the git calls before the wait counted against the 5 s bound. Repro: a 4 s delay before the first index_lock_held call fails it (6.27 s vs 5.0). Now fr.artifacts.commit.time is a fake clock (its only use is the wait loop): the test asserts the commit is refused, HEAD unchanged, and the time slept is in [_LOCK_WAIT_SECONDS, +2 polls). It passes with the 4 s repro delay.
