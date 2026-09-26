# Journal: 2026-09-26-ci-time-budget

<!-- fr:journal kind=decision scope=plan id=plan-two-phases created=2026-09-26T15:14:33 -->
### plan-two-phases · decision · Two agentic phases, sharding (skeleton, proven live on the branch CI run) then the watcher

The watcher is inert until merge, so only the sharding can be proven live pre-merge; making it the skeleton puts the riskiest claim (under 240s) first. There is no manual phase, because the post-merge Test Plan is operator-driven.

<!-- fr:journal kind=discovery scope=plan id=pytest-split-store-durations-with-xdist created=2026-09-26T16:43:10 phase=1 -->
### pytest-split-store-durations-with-xdist · discovery · --store-durations works fine together with -n auto (phase 1)

Ran `uv run pytest -n auto --no-cov --store-durations` over the full suite. It completed cleanly and wrote a `.test_durations` with 6413 entries — one per collected test, matching the full collection size. No warning or degraded behavior observed from pytest-split (0.11.0) under xdist. No fallback to a serial run was needed.

<!-- fr:journal kind=discovery scope=plan id=ci-branch-run-wall-clock created=2026-09-26T16:43:10 phase=1 -->
### ci-branch-run-wall-clock · discovery · Branch CI run 36247922786: 4 green test shards + coverage, 155s wall clock (phase 1)

First push (run 36247574806) failed `lint` (ruff format --check) on the newly-added tests/unit/test_ci_shards.py — a formatting miss from writing it outside `ruff format`. Fixed and re-pushed; the resulting run, 36247922786, is fully green: lint, typecheck, `test (1..4)`, `coverage`, validate-artifacts, opencode-plugin-test, version-sync (change-fragment skipped, correctly, as this is a push not a PR). Wall clock = max(completedAt) - min(startedAt) over non-skipped jobs = 2026-09-26T14:18:40Z (coverage's completedAt) minus 2026-09-26T14:16:05Z (the earliest job start) = 155s, well under the 240s budget (spec §3.A predicted ~150-180s).

<!-- fr:journal kind=discovery scope=plan id=ci-coverage-total-before-after-source-move created=2026-09-26T16:43:10 phase=1 -->
### ci-coverage-total-before-after-source-move · discovery · Coverage TOTAL unchanged by moving --cov=<pkg> into [tool.coverage.run] source (phase 1)

Before (main, commit 7f50d74c, CI job log): TOTAL 21824 stmts, 1542 miss, `Total coverage: 92.93%`. After (this branch, local full-suite run with the coverage-source move applied, ci.yml not yet sharded): TOTAL 21753 stmts, 1527 miss, `Total coverage: 92.98%`. The statement-count difference (21824 vs 21753) is expected — different commits, different code — not a sign of divergence: both runs measure exactly the same 5-package source list (fr, fr_dispatch, fr_vk, fr_cncd, fr_herdr) and both gate at 75%, confirming the move from CLI `--cov=<pkg>` flags in addopts to `[tool.coverage.run] source = [...]` is behaviorally inert locally, as spec §3.A intends.

<!-- fr:journal kind=finding scope=plan id=flaky-index-lock-test-under-host-contention created=2026-09-26T16:43:10 phase=1 state=refuted review_scope=out -->
### flaky-index-lock-test-under-host-contention · finding [refuted] (reviewer: out of scope) · test_records_commit.py::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly failed once under heavy host load, unrelated to this phase (phase 1)

During the first full-suite run today (26m24s wall clock — the host had 5+ other fr worktrees running their own full suites concurrently, vs. AGENTS.md's ~150s baseline), this test failed once: it asserts `1.0 <= elapsed < 5.0` seconds for a retry-on-stuck-lock code path, which is exactly the wall-clock-tight shape AGENTS.md already warns about for `-n auto`. A second full-suite run (17m24s, same host, still contended) passed it cleanly, with no code changes in between. Not caused by this phase's changes (pyproject.toml / ci.yml / new test file never touch fr.records_commit), and not reproducible on retry — recorded for visibility, not as a regression to fix here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T16:43:10 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

Task 2 (GREEN) has no dedicated refactor step of its own; the cleanup (ci.yml comment tidy, AGENTS.md refresh-command doc, fr acceptance set-status) was done in P1.T3.S1, the phase's explicit REFACTOR task.

<!-- fr:journal kind=finding scope=plan id=r1-partition-test-cost created=2026-09-26T16:58:25 phase=1 state=open review_scope=in -->
### r1-partition-test-cost · finding [open] (reviewer: in scope) · The partition test ran five full-suite --collect-only subprocesses (30-90s) inside a CI-time PR (phase 1)

tests/unit/test_ci_shards.py: .test_durations recorded the node at 31s, and it took about 90s locally, one lumpy indivisible unit that fights least_duration balancing. Fix: call pytest_split.algorithms.LeastDurationAlgorithm in-process over the .test_durations ids plus unknown ids.

<!-- fr:journal kind=finding scope=plan id=r1-dead-recursion-guard created=2026-09-26T16:58:25 phase=1 state=open review_scope=in -->
### r1-dead-recursion-guard · finding [open] (reviewer: in scope) · The PYTEST_SPLIT_INNER recursion guard was dead code (subprocesses were --collect-only) (phase 1)

tests/unit/test_ci_shards.py:125-131.

<!-- fr:journal kind=finding scope=plan id=r1-skipped-jobs-have-timestamps created=2026-09-26T16:58:25 phase=2 state=open review_scope=in -->
### r1-skipped-jobs-have-timestamps · finding [open] (reviewer: in scope) · GitHub stamps skipped jobs, so wall_clock must drop jobs by conclusion == skipped, not by null timestamps (phase 2)

Orchestrator observation on run 36247922786: change-fragment (skipped) has startedAt 14:16:03Z and completedAt 14:16:02Z. Spec §3.B and §7.2 assumed null timestamps; both are corrected. Phase 2's wall_clock and its fixture test must filter by conclusion.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-26T16:58:25 phase=1 -->
### review-phase-1 · review · Code review of phase 1 (sharding + coverage combine) (phase 1)

Dispatched reviewer (separate context). It verified the pytest-cov addopts accumulation fix, bare --cov with [tool.coverage.run] source being equivalent, include-hidden-files on upload, that a missing shard skips coverage rather than gating on 3 of 4 (needs semantics), and the live run 36247922786 (155s, TOTAL 93%). Findings: r1-partition-test-cost (in, fixed), r1-dead-recursion-guard (in, fixed). The orchestrator added r1-skipped-jobs-have-timestamps (in, filed against phase 2).

<!-- fr:journal kind=finding scope=plan id=r1-partition-test-cost-resolved created=2026-09-26T16:58:25 phase=1 state=fixed resolves=r1-partition-test-cost -->
### r1-partition-test-cost-resolved · finding [fixed] · resolves r1-partition-test-cost: The partition test ran five full-suite --collect-only subprocesses (30-90s) inside a CI-time PR (phase 1)

The in-process LeastDurationAlgorithm check takes 0.36s (was 30-90s). The .test_durations entry was updated from 31.05s to 0.36s, and spec §7.1 was reworded to match.

<!-- fr:journal kind=finding scope=plan id=r1-dead-recursion-guard-resolved created=2026-09-26T16:58:25 phase=1 state=fixed resolves=r1-dead-recursion-guard -->
### r1-dead-recursion-guard-resolved · finding [fixed] · resolves r1-dead-recursion-guard: The PYTEST_SPLIT_INNER recursion guard was dead code (subprocesses were --collect-only) (phase 1)

Removed together with the subprocesses; no nested pytest invocation remains.

<!-- fr:journal kind=discovery scope=plan id=ci-budget-skipped-job-fixture-proves-155-vs-157 created=2026-09-26T17:26:28 phase=2 -->
### ci-budget-skipped-job-fixture-proves-155-vs-157 · discovery · Captured fixture (run 36247922786) proves the 155s/157s skipped-job distinction (phase 2)

tests/fixtures/ci_budget/jobs_sharded.json's `change-fragment` job (skipped, started_at 14:16:03Z, completed_at 14:16:02Z) is 2s earlier than the earliest real job's start (lint, 14:16:05Z). `wall_clock` filtering by `conclusion == "skipped"` gives 155s; a naive filter that included it (flipped to `success` in a test-only copy) gives exactly 157s, matching the orchestrator's finding precisely. Both figures are asserted directly in test_wall_clock_sharded_run_excludes_the_skipped_job_by_conclusion.

<!-- fr:journal kind=discovery scope=plan id=ci-budget-pinned-clis-name-is-not-its-filename created=2026-09-26T17:26:28 phase=2 -->
### ci-budget-pinned-clis-name-is-not-its-filename · discovery · pinned-clis.yml's own `name:` is "Pinned CLIs", not "pinned-clis" (phase 2)

workflow_run.workflows matches on a workflow's `name:` field, not its filename. The plan step's prose lists the watch set loosely by filename-ish shorthand ("pinned-clis"); the real file's `name:` is "Pinned CLIs", which is what ci-budget.yml's watch list and check_watch_list's names_by_file both use. Verified by test_counted_pinned_clis_counts_every_event and the real-repo watch-list tripwire test passing.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4-t5 created=2026-09-26T17:26:28 phase=2 -->
### no-refactor-p2-t4-t5 · discovery · no-refactor-because P2.T4, P2.T5 (phase 2)

Tasks 4 (gh adapter + dedup + CLI) and 5 (workflow/config/tripwire) have no dedicated refactor step of their own; their cleanup (the one dead constant found, WORKFLOWS_DIR, plus the AGENTS.md doc note) was done in P2.T6.S1, the phase's explicit REFACTOR task.

<!-- fr:journal kind=finding scope=plan id=r1-skipped-jobs-have-timestamps-resolved created=2026-09-26T17:26:28 phase=2 state=fixed resolves=r1-skipped-jobs-have-timestamps -->
### r1-skipped-jobs-have-timestamps-resolved · finding [fixed] · resolves r1-skipped-jobs-have-timestamps: GitHub stamps skipped jobs, so wall_clock must drop jobs by conclusion == skipped, not by null timestamps (phase 2)

scripts/ci_budget.py's `wall_clock`/`slowest_job` filter jobs by `conclusion == "skipped"` (see `_ran`), never by missing timestamps — GitHub does stamp skipped jobs, as the finding observed. Fixture test test_wall_clock_sharded_run_excludes_the_skipped_job_by_conclusion asserts both figures against the real captured fixture (run 36247922786): 155s with the fix, 157s if the skipped job were wrongly included.
