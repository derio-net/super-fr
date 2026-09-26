# Journal: 2026-09-26-ci-time-budget

<!-- fr:journal kind=decision scope=spec id=scope-repo-local created=2026-09-26T15:02:10 -->
### scope-repo-local · decision · The watcher is repo-local (workflow + scripts/ci_budget.py), with no fr verb

Operator chose A. With agent filing dropped, nothing outside super-fr's own CI needs to call it.

<!-- fr:journal kind=decision scope=spec id=sharding-pytest-split-4 created=2026-09-26T15:02:10 -->
### sharding-pytest-split-4 · decision · pytest-split with 4 duration-balanced shards, plus a coverage-combine job gating at 75

Recommended option. Measured: 6,408 tests, largest file 13% of test time, unit/ 84%. A directory split would stay unbalanced.

<!-- fr:journal kind=decision scope=spec id=measure-run-wall-clock created=2026-09-26T15:02:10 -->
### measure-run-wall-clock · decision · Budget measures one run's wall clock, first job start to last job end, excluding queue

Recommended option.

<!-- fr:journal kind=decision scope=spec id=trigger-main-unless-pr-differs created=2026-09-26T15:02:10 -->
### trigger-main-unless-pr-differs · decision · Count main-push runs, and other events only for workflows that never run on a push to main

Operator: "if PR and Main have the same slow CI jobs, then Main is enough. If not, add PR to the mix". Checked against the on: blocks. ci.yml and acceptance-report.yml match (change-fragment runs only on PRs, ~8s, parallel). _pr_spec_status.yml and pinned-clis.yml never run on a push to main, so they are counted on their own events.

<!-- fr:journal kind=decision scope=spec id=close-after-3-green created=2026-09-26T15:02:10 -->
### close-after-3-green · decision · Auto-close after 3 consecutive under-budget successful runs; a regression opens a new issue linking the old one

Recommended option.

<!-- fr:journal kind=decision scope=spec id=agent-filing-dropped created=2026-09-26T15:02:10 -->
### agent-filing-dropped · decision · Agents filing or enriching tickets is dropped

Operator: "drop this requirement, I think the mechanical gate is enough".

<!-- fr:journal kind=decision scope=spec id=budget-240-override created=2026-09-26T15:02:10 -->
### budget-240-override · decision · 240s default, with a per-file override or exclusion in .github/ci-budget.yaml

Recommended option.

<!-- fr:journal kind=decision scope=spec id=test-plan-observe-forced-breach created=2026-09-26T15:02:10 -->
### test-plan-observe-forced-breach · decision · Post-merge Test Plan: observe the next main run, then force a breach via workflow_dispatch to check dedup

Recommended option.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-09-26T15:02:11 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. One logical round of 8 questions, sent as two AskUserQuestion calls in parallel instead of consecutively. The second dialog overwrote the first in the UI, so the first 4 came back unanswered (the operator asked to clarify). The operator asked about it, and the lost 4 were re-asked in a second call. One of those answers was itself a clarification, so the scope question was settled in prose (A, repo-local). No third question call was made.

<!-- fr:journal kind=finding scope=spec id=sr-cov-report-noop created=2026-09-26T15:12:41 state=open review_scope=in -->
### sr-cov-report-noop · finding [open] (reviewer: in scope) · --cov-report= on the shard CLI does not suppress addopts' term-missing report

pyproject.toml:53 addopts `--cov-report=term-missing`; pytest_cov/plugin.py:72-75 StoreReport accumulates into a dict and 240-243 clears only when `''` is the sole key. A CLI `--cov-report=` therefore cannot cancel addopts, and every shard prints a whole-codebase table.

<!-- fr:journal kind=finding scope=spec id=sr-watchlist-unclassified-files created=2026-09-26T15:12:41 state=open review_scope=in -->
### sr-watchlist-unclassified-files · finding [open] (reviewer: in scope) · release.yml and pages.yml are never classified as watched or excluded

The spec's own tripwire (§7.3) would fail on day one: release.yml:1-24 and pages.yml:1-6 are live workflows that the spec never mentions.

<!-- fr:journal kind=finding scope=spec id=sr-testplan-missing-override-case created=2026-09-26T15:12:41 state=open review_scope=in -->
### sr-testplan-missing-override-case · finding [open] (reviewer: in scope) · The Test Plan never exercises budget_for's per-file numeric override, only exclusion

Decision budget-240-override requires a per-file override, but §7 tests only exclusion and staleness.

<!-- fr:journal kind=finding scope=spec id=sr-concurrency-group-workflow-dispatch created=2026-09-26T15:12:41 state=open review_scope=in -->
### sr-concurrency-group-workflow-dispatch · finding [open] (reviewer: in scope) · The ci-budget-<file> concurrency group is unspecified for the workflow_dispatch trigger

github.event.workflow_run.path is null under workflow_dispatch, and the concurrency expression is evaluated before any step can look the run up.

<!-- fr:journal kind=finding scope=spec id=sr-acceptance-matrix-not-addressed created=2026-09-26T15:12:41 state=open review_scope=in -->
### sr-acceptance-matrix-not-addressed · finding [open] (reviewer: in scope) · The spec never addresses the repo's acceptance-matrix rule for its new Test Plan

.claude/rules/acceptance-matrix.md requires rows for a new Test Plan. §3.C reasons through the fragment gate but not the matrix, and §4 never mentions it.

<!-- fr:journal kind=finding scope=spec id=sr-job-name-branch-protection-claim created=2026-09-26T15:12:41 state=open review_scope=out -->
### sr-job-name-branch-protection-claim · finding [open] (reviewer: out of scope) · The claim that keeping the job name `test` preserves branch protection is inaccurate once `test` is a matrix

The status-check contexts become `test (1)`…`test (4)`. This is harmless today because main's ruleset requires no status checks (AGENTS.md, Release).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-26T15:12:41 -->
### spec-review-1 · review · Spec review of 2026-09-26-ci-time-budget-design: 6 findings (5 in scope, 1 out of scope)

Dispatched fr-spec-reviewer (read-only, separate context). Verified ci.yml:2,22-35; acceptance-report.yml:15-21; _pr_spec_status.yml:1-4; pinned-clis.yml:1-13; fr-spec-status.yml:1-3; check-change-fragment.py:60-65; pyproject.toml:29-37,51-53; test_tripwire_unarchived_plans.py:5,26; PyYAML parsing the `on` key as True. Findings: sr-cov-report-noop, sr-watchlist-unclassified-files, sr-testplan-missing-override-case, sr-concurrency-group-workflow-dispatch, sr-acceptance-matrix-not-addressed (in); sr-job-name-branch-protection-claim (out).

<!-- fr:journal kind=finding scope=spec id=sr-cov-report-noop-resolved created=2026-09-26T15:12:41 state=fixed resolves=sr-cov-report-noop -->
### sr-cov-report-noop-resolved · finding [fixed] · resolves sr-cov-report-noop: --cov-report= on the shard CLI does not suppress addopts' term-missing report

§3.A: the shard clears addopts with `-o addopts="--strict-markers --cov"` and passes `--cov-report=`. The coverage sources move to [tool.coverage.run] source. §7.8 pins the override.

<!-- fr:journal kind=finding scope=spec id=sr-watchlist-unclassified-files-resolved created=2026-09-26T15:12:41 state=fixed resolves=sr-watchlist-unclassified-files -->
### sr-watchlist-unclassified-files-resolved · finding [fixed] · resolves sr-watchlist-unclassified-files: release.yml and pages.yml are never classified as watched or excluded

§3.B lists every workflow watched at launch, including Release (release.yml) and Deploy explainers to Pages (pages.yml), counted on push@main.

<!-- fr:journal kind=finding scope=spec id=sr-testplan-missing-override-case-resolved created=2026-09-26T15:12:41 state=fixed resolves=sr-testplan-missing-override-case -->
### sr-testplan-missing-override-case-resolved · finding [fixed] · resolves sr-testplan-missing-override-case: The Test Plan never exercises budget_for's per-file numeric override, only exclusion

§7.5 adds the numeric-override case: 300s is under a 360s override but over the default, and an excluded file is never decided.

<!-- fr:journal kind=finding scope=spec id=sr-concurrency-group-workflow-dispatch-resolved created=2026-09-26T15:12:41 state=fixed resolves=sr-concurrency-group-workflow-dispatch -->
### sr-concurrency-group-workflow-dispatch-resolved · finding [fixed] · resolves sr-concurrency-group-workflow-dispatch: The ci-budget-<file> concurrency group is unspecified for the workflow_dispatch trigger

§3.B: the group is `ci-budget-${{ github.event.workflow_run.path || 'dispatch' }}`, and the reason dispatch is serialized separately is stated.

<!-- fr:journal kind=finding scope=spec id=sr-acceptance-matrix-not-addressed-resolved created=2026-09-26T15:12:41 state=fixed resolves=sr-acceptance-matrix-not-addressed -->
### sr-acceptance-matrix-not-addressed-resolved · finding [fixed] · resolves sr-acceptance-matrix-not-addressed: The spec never addresses the repo's acceptance-matrix rule for its new Test Plan

§4 names the three rows added at brainstorm and how each moves with fr acceptance set-status.

<!-- fr:journal kind=finding scope=spec id=sr-job-name-branch-protection-claim-resolved created=2026-09-26T15:12:41 state=open resolves=sr-job-name-branch-protection-claim out_of_scope=true -->
### sr-job-name-branch-protection-claim-resolved · finding [out-of-scope] · resolves sr-job-name-branch-protection-claim: The claim that keeping the job name `test` preserves branch protection is inaccurate once `test` is a matrix

The lack of required status checks predates this change. The spec sentence was reworded to state the real contexts rather than claim branch-protection compatibility.

<!-- fr:journal kind=finding scope=spec id=sr-job-name-branch-protection-claim-resolved-2 created=2026-09-27T00:00:32 state=open resolves=sr-job-name-branch-protection-claim tracked_by=#706 -->
### sr-job-name-branch-protection-claim-resolved-2 · finding [deferred → #706] · resolves sr-job-name-branch-protection-claim: The claim that keeping the job name `test` preserves branch protection is inaccurate once `test` is a matrix

Filed at closeout as #706.
