> [!WARNING]
> **Not ready yet.** This moves to ready only when all three hold: CI is green, the operator has explicitly OK'd a review, and nothing but fr's own `chore(fr):` record commits has landed since that OK.

## Summary

This brings CI under a **4-minute** wall clock and makes CI slowness visible from now on.

1. **Sharded `test` job.** `ci.yml`'s `test` job is now 4 [pytest-split](https://github.com/jerry-git/pytest-split) shards, balanced by a committed `.test_durations`, with `-n auto` inside each shard. A new `coverage` job combines the shard data files and keeps the **75%** gate. The branch's CI run [36247922786](https://github.com/derio-net/super-fr/actions/runs/36247922786) took **155s** of wall clock, against about **435s** on `main` before this change.
2. **Budget watcher.** `.github/workflows/ci-budget.yml` runs `scripts/ci_budget.py` on every completed run of every watched workflow. It measures the run's wall clock (first job start to last job end, excluding queue) against `.github/ci-budget.yaml` (240s by default, with per-file overrides and exclusions).
   - It keeps **one open `ci-budget` issue per CI file**, found through a label list plus a body marker. It never uses `gh search`, whose results can lag behind a fresh issue and cause duplicates.
   - Later breaches rewrite that issue's table instead of commenting.
   - The issue auto-closes after 3 consecutive successful runs under budget. A later regression opens a new issue that links the old one.
   - A tripwire test fails CI if a workflow file is neither watched nor excluded.

- Spec: `docs/superpowers/specs/2026-09-26-ci-time-budget-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-ci-time-budget/`

## Decisions (operator, 2026-09-26)

- **Scope:** repo-local (a workflow and a script), no `fr` verb.
- **Sharding:** pytest-split with 4 shards and a coverage-combine job.
- **Measure:** one run's wall clock, excluding queue time.
- **Which runs count:** main-push runs. A workflow that never runs on a push to `main` is counted on its own events.
- **Closing:** auto-close after 3 green runs.
- **Budget:** 240s by default, with per-file overrides.
- **Agents filing tickets:** dropped.

## Operator gates

```
brainstorm: operator gate answered by the operator
```

The brainstorm was **one logical round of 8 questions**. I sent its two 4-question dialogs in parallel, and the second overwrote the first in the UI. The lost 4 were re-asked, and the scope answer came in prose. The record declares `rounds: 2, trigger: operator-request` with that reason, because fr counts question calls in the transcript and would otherwise refuse a mismatch.

## Out-of-scope findings to file (for the merge touchpoint)

- `sr-job-name-branch-protection-claim`: the `test` status contexts are now `test (1)`…`test (4)` plus `coverage`. This only matters if `main` ever gets a required-checks rule. **Suggest: don't file**; the spec and AGENTS.md already state it.
- `r2-actions-pinned-by-tag`: every workflow pins third-party actions by tag, and three of them hold `issues: write`. **Suggest: file** a repo-wide SHA-pinning issue, because it's a real hardening gap that this PR didn't introduce.

## Manual phases

None.

## Test Plan (post-merge, operator-driven)

1. The next `CI` run on main takes under 4 minutes of wall clock (read it with `gh run view <id> --json jobs`).
2. Run `gh workflow run ci-budget.yml -f run_id=<that run> -f budget_seconds=30`. Exactly one `ci-budget` issue appears for `ci.yml`. Run the same command again: the same issue is updated, with two rows and no duplicate.
3. Close that issue by hand. It was a forced breach.

## Acceptance

- **Debt:** `ci: 225, not-implemented: 9, scheduled: 1, skipped: 25`. That is unchanged apart from the rows below. The warnings are about other specs having been archived, not this PR.
- **Rows added since `origin/main`:**
  - **`ci-under-time-budget`** is now `skipped`. It pins the headline claim, a CI run under 4 minutes with the 75% gate intact. The shard layout and partition are unit-pinned (`tests/unit/test_ci_shards.py`). The wall clock can only be shown by a real GitHub run: it is proven on this branch's run, and the post-merge observation on `main` is still owed.
  - **`ci-budget-ticket-dedup`** is now `ci`. It pins the operator's "no duplicate issues per CI file" requirement and auto-close, through the state machine and a `gh` fake that records every argv (`tests/unit/test_ci_budget.py`).
  - **`ci-budget-watch-list-complete`** is now `ci`. A new workflow can't escape the budget unnoticed. This is a structural invariant, enforced as a tripwire in the same test file.

## Proportionality justification

The flagged 8.1× is **6,415 lines of generated data in `.test_durations`**, pytest-split's timing file. Without it the change is about 1,700 lines, **1.7× the estimate**, and that is mostly `scripts/ci_budget.py` and its tests.

## Other notes

- **Change fragment:** none needed. No path on the fragment list changed (`.github/**`, `tests/**`, the root `pyproject.toml`, and `scripts/` other than the install/validate scripts are all exempt).
- **Explainers:** no explainer describes CI, so none needs an update.
- **Evidence:** full suite run locally for `deliver`: 6354 passed, 97 skipped, 92.98% coverage.
- **Refreshing `.test_durations`:** documented in AGENTS.md. A stale file only unbalances the shards, and the watcher is what notices when that starts to cost time.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-09-26-feat-ci-time-budget; edit above this line only -->

## Findings

- `sr-cov-report-noop` (spec) — --cov-report= on the shard CLI does not suppress addopts' term-missing report — **fixed**
- `sr-watchlist-unclassified-files` (spec) — release.yml and pages.yml are never classified as watched or excluded — **fixed**
- `sr-testplan-missing-override-case` (spec) — The Test Plan never exercises budget_for's per-file numeric override, only exclusion — **fixed**
- `sr-concurrency-group-workflow-dispatch` (spec) — The ci-budget-<file> concurrency group is unspecified for the workflow_dispatch trigger — **fixed**
- `sr-acceptance-matrix-not-addressed` (spec) — The spec never addresses the repo's acceptance-matrix rule for its new Test Plan — **fixed**
- `flaky-index-lock-test-under-host-contention` (plan, phase 1) — test_records_commit.py::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly failed once under heavy host load, unrelated to this phase — **refuted**
- `r1-partition-test-cost` (plan, phase 1) — The partition test ran five full-suite --collect-only subprocesses (30-90s) inside a CI-time PR — **fixed**
- `r1-dead-recursion-guard` (plan, phase 1) — The PYTEST_SPLIT_INNER recursion guard was dead code (subprocesses were --collect-only) — **fixed**
- `r1-skipped-jobs-have-timestamps` (plan, phase 2) — GitHub stamps skipped jobs, so wall_clock must drop jobs by conclusion == skipped, not by null timestamps — **fixed**
- `r2-budget-re-mismatch` (plan, phase 2) — BUDGET_RE never matched render_body's heading, so a non-default budget parsed back as 240s — **fixed**
- `r2-run-step-injection` (plan, phase 2) — ci-budget.yml interpolated ${{ inputs.* }} into run:, the script-injection shape, on an issues:write token — **fixed**
- `r2-wasted-uv-sync` (plan, phase 2) — The watcher ran uv sync before a --no-project invocation — **fixed**
- `r2-jobs-not-paginated` (plan, phase 2) — fetch_jobs did not paginate, so past 30 jobs wall_clock would truncate silently — **fixed**
- `r2-run-id-unvalidated` (plan, phase 2) — --run-id was not validated as numeric — **fixed**

## Out-of-scope findings

- `sr-job-name-branch-protection-claim` (spec) — The claim that keeping the job name `test` preserves branch protection is inaccurate once `test` is a matrix — **out-of-scope**
- `r2-actions-pinned-by-tag` (plan, phase 2) — Third-party actions pinned by tag rather than SHA (flagged by a background security scan) — **out-of-scope**

## Proportionality

```text
proportionality: merge-base eddb7b9052c1ab2f1e9d7cae1f64602ebae0cebf

## Unreferenced new files

none.

## Out-of-plan touches

none.

## Size

8141 lines changed (+8132 -9; fr artifacts excluded) against an estimate of 1010 (8.1×).
FLAG: above 2× the estimate — add a justification line to the PR body.
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 31 | — |
| spec-review | — | — |
| plan | — | — |
| plan-review | — | — |
| implement | — | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 1 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.
