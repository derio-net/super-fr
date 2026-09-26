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
