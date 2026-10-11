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
