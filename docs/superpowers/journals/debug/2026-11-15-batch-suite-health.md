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

<!-- fr:journal kind=ruled-out scope=debug id=824263d00513 created=2026-11-15T07:57:46+00:00 -->
### 824263d00513 · ruled-out · #1280: test_install_atomic's bounds are not too tight

Its subprocess bounds are 120-180 s (INSTALL_BOUND_S = 180) around a stubbed install that takes seconds. Failing them needs a 20-50x slowdown: the load 100-300 of #1280's run (another session's suite in the other slot), which the load-aware -n auto now avoids. Left unchanged.

<!-- fr:journal kind=ruled-out scope=debug id=33c8f6e7d66d created=2026-11-15T10:04:11+00:00 -->
### 33c8f6e7d66d · ruled-out · #1428 fix 1 (longest-first shards) gave no wall-clock gain

Run 43691468025: overhead beyond work/4 fell from 50-87 s to 39-49 s, but scenario tests ran 1.36x their previous duration (other tests 1.03x): started together, they contend, and a module-scoped install repeats per worker. Max py3.14 shard pytest step 329 s before and after. Reverted.

<!-- fr:journal kind=finding scope=debug id=git-date-leak created=2026-11-15T10:04:14+00:00 state=fixed -->
### git-date-leak · finding [fixed] · GIT_COMMITTER_DATE leaked between tests

test_placement_merged's tick() writes os.environ directly; test_acceptance_amend_origin imports Product without the _home fixture, so the dates stayed set for the worker and test_run_ci_evidence read a fresh head as 14400 minutes old. Repro: run those two in one process (fails). Fix: autouse _no_git_date_carried_between_tests restores the session's values. Pinned by tests/unit/test_suite_isolation_git_dates.py (red, then green); the pair passes.

<!-- fr:journal kind=ruled-out scope=debug id=6c00104cf8f3 created=2026-11-15T10:04:16+00:00 -->
### 6c00104cf8f3 · ruled-out · tmp_path_retention_policy=failed breaks archive tests

Full local suite: 4 archive tests failed with 'rejected (fetch first)'. Deleting a passed test's tmp dir immediately lets the next same-prefix test reuse the path beside a leftover <tmp_path>.origin.git. test_archive_open_ends + test_archive_owed: 2 failed with the policy, 48 passed with -o tmp_path_retention_policy=all. Dropped; #1225's temp-size proposal is not done.

<!-- fr:journal kind=decision scope=debug id=9fd3bba64fab created=2026-11-15T10:04:25+00:00 -->
### 9fd3bba64fab · decision · #1428: 7 shards per ci.yml leg

Operator chose, in the session's question round after fix 1 failed: a 7th shard per leg in ci.yml (release.yml stays at 6), amending ci-speed R6's acceptance row.

<!-- fr:journal kind=finding scope=debug id=ci-seven-shards created=2026-11-15T10:39:09+00:00 state=fixed -->
### ci-seven-shards · finding [fixed] · #1428: ci.yml at 7 shards, 323 s on its first run

CI run on 91007c7: green, wall clock 323 s (budget 360), slowest shard job 288 s (py3.14/2) against 344-369 s on the last ten main runs. One run; runner speed varies x0.72-x1.40, so the budget watcher on main is the real check. ci-shards-complete reworded by amendment (feature legacy). Full local suite on 91007c7: 16013 passed, 120 skipped.

<!-- fr:journal kind=review scope=debug id=7ebecf953acd created=2026-11-15T10:39:13+00:00 -->
### 7ebecf953acd · review · Review of the batch diff

Self-review of origin/main...HEAD (no independent reviewer dispatched). Findings: (1) test_suite_isolation_git_dates relies on its two tests sharing a process; under xdist they may split and the second passes vacuously; it is a real check serially, where the leak was reproduced. Accepted, noted here. (2) The load-aware -n auto rule reads a one-minute load, so sessions starting together still each take every CPU; documented in AGENTS.md and the docstring, with FR_PYTEST_WORKERS as the exact bound. (3) #1225's host-wide suite lock and temp pruning are not done (pruning broke the archive tests); stated in the PR. No other findings.

<!-- fr:journal kind=finding scope=debug id=lock-double-hold created=2026-11-15T10:39:31+00:00 state=open -->
### lock-double-hold · finding [open] · #1463: worktree hook lock double-hold not reproduced

Both CI failures were real double-holds (OVERLAP logged; the create stub's rmdir found in-flight already removed). 120 loaded trials on macOS and 80 in ubuntu:24.04 under load reproduced none, and no two-process interleaving of the mkdir lock and its dead-holder reclaim double-holds by code read. Per the operator's decision it leaves this PR.

<!-- fr:journal kind=finding scope=debug id=lock-double-hold-resolved created=2026-11-15T10:40:09+00:00 state=open resolves=lock-double-hold tracked_by=derio-net/super-fr#1463 -->
### lock-double-hold-resolved · finding [deferred → derio-net/super-fr#1463] · resolves lock-double-hold: #1463: worktree hook lock double-hold not reproduced

Not reproduced (200 loaded trials, macOS and Linux); split out of batch suite-health. #1463 stays open.

<!-- fr:journal kind=finding scope=debug id=multi-root-cause-resolved created=2026-11-15T10:40:11+00:00 state=fixed resolves=multi-root-cause -->
### multi-root-cause-resolved · finding [fixed] · resolves multi-root-cause: The batch spans several independent root causes

Each cause fixed on its own with its own test, per the operator's decision 1313d85ab59b: ci.yml hygiene (#1289, #1288), load-aware -n auto (#1225), visual clock and fake-clock lock wait (#1280), 7 shards (#1428); #1463 deferred.
