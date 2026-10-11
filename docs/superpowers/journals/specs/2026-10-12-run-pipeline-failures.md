# Journal: 2026-10-12-run-pipeline-failures

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T22:04:16+00:00 input=true -->
### operator-brief · discovery · Batch run-pipeline brief (super-fr#1090, #1091, #1110), verbatim

/fr-goal Run pipeline failures at resolve and deliver; double phase claims

Batch `run-pipeline` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#1090: fr commit paths and acceptance check break when the repo gitignores the generated acceptance reports
`fr run resolve` puts gitignored reports in its commit set, so the commit fails in repos that gitignore them. Not re-read.

## super-fr#1091: deliver demands a candidate walk the repo cannot run; nothing flags it before deliver
A spec with only per-row `none` lines falls back to `candidate`, and deliver refuses at the last step. Not re-read.

## super-fr#1110: Driver reclaims an unresolved phase twice and writes duplicate claim commits
An unresolved phase is claimed twice; durable cursor shows two owners. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10).

## Why these belong together
Runs fail at their last step. #1110 taken over from the inactive scope s-c8805331 at the operator's request, 2026-10-10.

## Delivery rules
- Work on branch `feat/batch-run-pipeline`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1090
  Closes derio-net/super-fr#1091
  Closes derio-net/super-fr#1110
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

(Issue bodies read in full via gh at brainstorm; the spec's Background restates them.)

<!-- fr:journal kind=decision scope=spec id=overnight-brief-recommendations created=2026-10-11T22:04:16+00:00 -->
### overnight-brief-recommendations · decision · All five question-round choices taken by the triage session under the overnight brief, not ruled by the operator

The derio-net triage session's overnight standing instruction (operator asleep until 06:00 CEST) told this run to take the recommended option for every question and continue to the draft PR. The five choices below are those recommendations; the operator can revise any of them at PR review. Also standing: targeted tests only locally, heavy suites via ~/.cache/fr/coord/testslot.sh, prefer `tests: ci`, PR stays draft.

<!-- fr:journal kind=decision scope=spec id=q1-report-mode-gitignore created=2026-10-11T22:04:16+00:00 -->
### q1-report-mode-gitignore · decision · #1090: a report the repo gitignores (and does not track) counts as CI-built — detected by git check-ignore, no config knob

Recommended option, taken by the triage session (overnight brief). Rejected: config knob only; both.

<!-- fr:journal kind=decision scope=spec id=q2-filter-at-writers created=2026-10-11T22:04:16+00:00 -->
### q2-filter-at-writers · decision · #1090: ignored reports are dropped at the report writers via one helper, not generically in commit_paths

Recommended option, taken by the triage session (overnight brief). Keeps an ignored cursor/journal failing loudly.

<!-- fr:journal kind=decision scope=spec id=q3-default-filter-and-early-flag created=2026-10-11T22:04:16+00:00 -->
### q3-default-filter-and-early-flag · decision · #1091: an unrunnable shape default no longer applies; explicit unrunnable strategies flagged at brainstorm resolve (warning) and plan self-review (error); malformed strategy: error shows the accepted form

Recommended option, taken by the triage session (overnight brief). Rejected: early flag only; default fix only.

<!-- fr:journal kind=decision scope=spec id=q4-first-claim-wins created=2026-10-11T22:04:16+00:00 -->
### q4-first-claim-wins · decision · #1110: a same-agent re-claim never overwrites recorded harness/model/agent_type; differing values warn, exit 0, no write; no schema change

Recommended option, taken by the triage session (overnight brief). Rejected: audited replacement attempt (run schema bump); refuse with exit 2.

<!-- fr:journal kind=decision scope=spec id=q5-verification-none created=2026-10-11T22:04:16+00:00 -->
### q5-verification-none · decision · Verification: strategy none with a per-row reason; CI runs the targeted tests

Recommended option, taken by the triage session (overnight brief). Rejected: candidate walk with per-row scenarios.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-10-11T22:04:22+00:00 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

The question round (5 questions, recommended option first) was asked, then answered by the derio-net triage session's overnight standing instruction (operator asleep until 06:00 CEST): take the recommended option for every question. No operator ruled; the choices are journalled as triage-session decisions for revision at PR review.

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · R4 misses a third place the shape default is bound: fr/run/visual.py _verification

visual.py:344 binds workflow_for_plan(plan, repo_root).verification into SpecVerification on its own; R4 says the default is filtered everywhere it is bound.

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · runnable() re-derives the install-program rule walk.py _contract already implements

walk.py:354-370 already decides executability; two definitions can drift. Also reconcile 'no install'.

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · R5's brainstorm-resolve check has no entry point: _verification_issues takes a Plan

At brainstorm resolve there is no plan; define a plan-free function and say which inputs each caller checks.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · Filtering in rows.shape_default lets StrategyError escape into callers that do not catch it

rows.py:84-87 and pr_body.py:473-477/537-541 catch neither StrategyError; say what happens on an unresolvable default.

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · First-claim-wins also blocks the FIRST claim from refining advance-recorded harness/model

advance pre-fills harness (always) and model (orchestrator work); the keep rule must apply only once the attempt carries an agent.

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · resolve's no-agent branch in _close_on_resolve still overwrites harness/model

run_cmd.py:4049-4057 updates harness/model without _claimed_identity; route it through the same rule.

<!-- fr:journal kind=finding scope=spec id=sr-r7 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r7 · finding [open] (reviewer: in scope) · The mismatch warning fires on OpenCode's routine double claim and gives the wrong remedy

claim.ts:109-111 claims with the child's model; the orchestrator re-claims with the tier binding. Compare by model_family and word the warning for attribution; test the sequence.

<!-- fr:journal kind=finding scope=spec id=sr-r8 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r8 · finding [open] (reviewer: in scope) · No Test Plan: R1-R7 have no named tests

Map tests to requirements and rows.

<!-- fr:journal kind=finding scope=spec id=sr-r9 created=2026-10-11T22:11:42+00:00 state=open review_scope=in -->
### sr-r9 · finding [open] (reviewer: in scope) · R2 does not say what report --check --out <ignored path> does

acceptance_cmd.py:171-176 narrows --check to one explicit file; state and test the choice.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-11T22:11:42+00:00 -->
### spec-review-1 · review · independent spec review: 9 findings (all in scope)

Dispatched fr-spec-reviewer (read-only) over the spec and spec journal. Decisions q1..q5 and the overnight-brief record are honoured; every REPORT_SET/render_committed_set caller is covered by §A; one shape-default binding was missed. Findings: sr-r1, sr-r2, sr-r3, sr-r4, sr-r5, sr-r6, sr-r7, sr-r8, sr-r9. All fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: R4 misses a third place the shape default is bound: fr/run/visual.py _verification

§B R4: one effective_shape_default helper called by rows.shape_default, plan_ops _verification_issues AND visual.py:344.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: runnable() re-derives the install-program rule walk.py _contract already implements

§B: install_problem() is the one rule; _contract calls it for the program check and keeps only its walk-specific 'no install' refusal; no-install is explicitly not a problem for owing.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: R5's brainstorm-resolve check has no entry point: _verification_issues takes a Plan

§B R5: plan-free unrunnable_strategies(repo_root, section, rows) in verification/rows.py; self-review passes rows citing the spec (error), brainstorm resolve reads the spec section + matrix rows after apply (warning), shape default never consulted.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: Filtering in rows.shape_default lets StrategyError escape into callers that do not catch it

§B: effective_shape_default returns an unresolvable default UNFILTERED, so no StrategyError reaches rows.py/pr_body.py and the deliver gate keeps refusing it by name; tested.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: First-claim-wins also blocks the FIRST claim from refining advance-recorded harness/model

R7 + §C: the keep rule applies only once the attempt carries an agent; the first claim sets fields as today; R8 tests it.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: resolve's no-agent branch in _close_on_resolve still overwrites harness/model

§C: _close_on_resolve's no-agent branch goes through the same merge function; R8 covers resolve --model without --agent.

<!-- fr:journal kind=finding scope=spec id=sr-r7-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r7 -->
### sr-r7-resolved · finding [fixed] · resolves sr-r7: The mismatch warning fires on OpenCode's routine double claim and gives the wrong remedy

R7/§C: model compared by model_family; warning reworded for attribution (first claim stands, resolve records observed model, abandon only if really replaced); R8 tests the plugin-then-orchestrator sequence.

<!-- fr:journal kind=finding scope=spec id=sr-r8-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r8 -->
### sr-r8-resolved · finding [fixed] · resolves sr-r8: No Test Plan: R1-R7 have no named tests

Added ## Tests mapping tests to R1-R8 and the three rows. Not a '## Test Plan': in fr-goal that header holds post-merge rows only, and this spec has none. The rows already exist (brainstorm record) and the plan links them on its phases.

<!-- fr:journal kind=finding scope=spec id=sr-r9-resolved created=2026-10-11T22:11:42+00:00 state=fixed resolves=sr-r9 -->
### sr-r9-resolved · finding [fixed] · resolves sr-r9: R2 does not say what report --check --out <ignored path> does

R2 + §A: an explicit --out is compared regardless; tested.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-12-run-pipeline-failures-p2 created=2026-10-11T22:13:31+00:00 -->
### phase-split-2026-10-12-run-pipeline-failures-p2 · decision · ask: phase 2 serves its own member issue (#1091, R4-R6)

Independently reviewable ask; separate files and tests from the other phases.
