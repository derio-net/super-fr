<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-landing-method

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-26T13:05:48+00:00 input=true -->
### operator-brief · discovery · Batch landing-method brief (super-fr#1705, #1702, #1603) and the operator's decisions

Batch `landing-method` of derio-net/super-fr: 3 issues, delivered as ONE pull request.
Batch title: Landing method: refuse squash/rebase under land: push on GitHub, configured merge_method beats the viewer default.

super-fr#1705 — Queue: a squash landing by push makes GitHub close the PR, not merge it (#1704).
Live 2026-11-25: the queue landed #1704 as a squash by push and force-pushed its head ref; GitHub recorded it closed, not merged, so its `Closes` never fired and release gating now reads a first-parent `(#1704)` the forge calls unmerged (RCs only). Squash/rebase cannot mark a GitHub PR merged by push.

super-fr#1702 — triage: the driver ignores the configured merge_method when GitHub reports a viewer default.
`choose_method` (batch_merge.py:92) returns the forge default before the configured `merge_method`, and under graphql the default is the viewer's `viewerDefaultMergeMethod` (real_ghclient.py:597-606), so `.fr/triage.yaml`'s `squash` is never reached and landings are merge commits.

super-fr#1603 — Rebase method breaks release.py's first-parent PR cross-check.
`choose_method` accepts `rebase`, whose branch-subject commits break release.py's first-parent `(#N)` cross-check; that fails safe to an RC, never a wrong final.

Delivery rules: branch feat/batch-landing-method; draft PR with one `Closes derio-net/super-fr#<n>` line per member; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

Operator decisions (session message, verbatim in substance):
(1) On GitHub under queue land: push, only a merge commit makes GitHub mark the PR merged; a squash or rebase force-push closes it unmerged (#1705, what happened to #1704). So under land: push on GitHub, refuse squash and rebase with a reason that names the fix, never land them.
(2) A configured merge_method in .fr/triage.yaml wins over the forge's viewer default (#1702); the viewer default is only a fallback when nothing is configured.
(3) Set this repo's .fr/triage.yaml merge_method to merge in this PR.
(4) #1603: rebase stays refused for any repo whose release reads first-parent (#N); warn or refuse, author's call in the spec.
(5) Say what release.py should do about a first-parent (#N) whose PR is closed unmerged but whose content landed (ff14a97ae, #1704): it currently makes the gate state unknown, so RCs only. Propose the fix in the spec, or file a follow-up if it does not fit.
The driver is stopped; the operator hand-merges this PR as a merge commit, so do not wait for the driver.

<!-- fr:journal kind=decision scope=spec id=d1-push-merge-only created=2026-11-26T13:05:48+00:00 -->
### d1-push-merge-only · decision · Under queue.land: push, squash and rebase are refused (held with the fix named), never landed

Operator decision (1). Spec R2, R3, R5. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-configured-beats-default created=2026-11-26T13:05:48+00:00 -->
### d2-configured-beats-default · decision · A configured merge_method wins over the forge's viewer default; the default is only a fallback

Operator decision (2). Spec R1. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-repo-merge-method-merge created=2026-11-26T13:05:48+00:00 -->
### d3-repo-merge-method-merge · decision · This repo's .fr/triage.yaml sets merge_method: merge in this PR

Operator decision (3). Spec R6. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-rebase-warn-under-land-merge created=2026-11-26T13:05:48+00:00 -->
### d4-rebase-warn-under-land-merge · decision · Rebase: refused under land: push (by R2); under land: merge it lands with a once-per-process warning

Operator decision (4) left warn-vs-refuse to the author. fr cannot know whether a repo's release reads first-parent (#N), so refusing rebase everywhere would remove a method other repos may rely on; this repo is protected by R2 + R6. A warning names the consequence. Spec R4. decider: author (delegated by operator).

<!-- fr:journal kind=decision scope=spec id=d5-release-closed-unmerged-counts created=2026-11-26T13:05:48+00:00 -->
### d5-release-closed-unmerged-counts · decision · release.py counts a first-parent PR the forge reports CLOSED-unmerged as landed, dated by its commit

Operator decision (5) asked for a proposal or a follow-up; it fits (one read per missed PR in waiting_prs), so it is in the spec as R7. Gate labels still decide; an OPEN PR or a failed read stays unknown. decider: author (delegated by operator).

<!-- fr:journal kind=decision scope=spec id=d6-verification-none-ci created=2026-11-26T13:05:48+00:00 -->
### d6-verification-none-ci · decision · Verification: strategy none, every row proven by unit tests in this PR's CI; gate developer

The change is pure decision logic plus a script read, all drivable with fakes; no behaviour needs an installed candidate or a released build. The operator hand-merges as a merge commit. decider: author.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-11-26T13:05:49+00:00 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

The operator stated every operator-owned decision in the session's second message (decisions 1-5 below) and asked that they be recorded instead of asked; the two calls left to the author (warn vs refuse for rebase under land: merge, the verification strategy) are recorded as author decisions.

<!-- fr:journal kind=finding scope=spec id=spr-r1 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r1 · finding [open] (reviewer: in scope) · The design never says how the existing squash-by-push fixtures are migrated; R2/R3 turn them into holds

target: spec. tests/unit/fakes.py:499-501; tests/unit/test_triage_batch_drive_cmd.py:212-213 + autouse _queue_stub :561-571; tests/integration/test_queue_land.py:79-226; test_queue_errors.py:47-74; test_queue_resume.py:58; test_queue_drive_cmd.py:150. Fixtures must move to merge keeping each R10 proof.

<!-- fr:journal kind=finding scope=spec id=spr-r2 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r2 · finding [open] (reviewer: in scope) · The plan looks for land_push tests in the wrong files; files: omits the integration tests and fakes

target: plan. land_push tests live in tests/integration/test_queue_{land,errors,resume,drive_cmd}.py; files: lists none of tests/integration/*, tests/unit/fakes.py, tests/integration/queue_git.py.

<!-- fr:journal kind=finding scope=spec id=spr-r3 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r3 · finding [open] (reviewer: in scope) · R3 contradicts merged row wave-queue-land-methods and its cited test; the spec amends neither

target: spec. docs/acceptance/features/2026-11-19-wave-merge-queue.yaml:39-60 says push landing works for squash; it cites the parametrised squash/rebase test_queue_land.py test. Amend wave-merge-queue R10 and the rows.

<!-- fr:journal kind=finding scope=spec id=spr-r4 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r4 · finding [open] (reviewer: in scope) · _queue_refusal cannot just call _ctx_or_hold: ConfigError/ForgeReadError escape, and its first use is a new fetch and forge read

target: spec. triage_batch_cmd.py:4466-4477 catches only DefaultBranchUnknown; merge_ctx raises at :4429-4432, :4449-4450; _queue_refusal callers :7082 (resume), :7116 (reads), :7316. State the behaviour on each error; correct 'no new forge read'.

<!-- fr:journal kind=finding scope=spec id=spr-r5 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r5 · finding [open] (reviewer: in scope) · R3 checks the current method, not the one a stored combination was built in

target: spec. QueueBuiltEvent (model.py:1175-1189) records no method; _land passes the current p.method (queue_exec.py:1450-1476). A squash-built combination landed after the method becomes merge closes PRs unmerged. Guard structurally: each landing commit must be a merge whose second parent is x.head.

<!-- fr:journal kind=finding scope=spec id=spr-r6 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r6 · finding [open] (reviewer: in scope) · R2's fix merge_method: merge fails when the repo does not allow merge commits

target: spec. batch_merge.py:115-121 refuses a disallowed configured method; squash-only repos exist (test_triage_batch_drive_cmd.py:212-213). Word the fix from the allowed set.

<!-- fr:journal kind=finding scope=spec id=spr-r7 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r7 · finding [open] (reviewer: in scope) · The resume path skips a landing-refused repo, so an already-pushed landing is not recorded

target: spec. triage_batch_cmd.py:7081-7083 skips any repo _queue_refusal refuses; resume (queue_exec.py:1050-1063, :1101-1109) only records. Keep the landing rule out of resume.

<!-- fr:journal kind=finding scope=spec id=spr-r8 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r8 · finding [open] (reviewer: in scope) · The plan says the existing choose_method test needs no change, but one case encodes the old order

target: plan. tests/unit/test_triage_batch_merge.py:346-347 '# The forge's own default still wins where it names one'.

<!-- fr:journal kind=finding scope=spec id=spr-r9 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r9 · finding [open] (reviewer: in scope) · R8 and files: miss pages and AGENTS.md text covering or describing the changed paths

target: spec. docs/explainers/fr-exit-gates.md:15, docs/exit-gates-release-walk.md:7, docs/explainers/index.md:40 cover scripts/release.py; docs/explainers/fr-triage.md:15 covers triage/**; docs/merge-protection.md:215-221; AGENTS.md Release gating.

<!-- fr:journal kind=finding scope=spec id=spr-r10 created=2026-11-26T13:17:42+00:00 state=open review_scope=in -->
### spr-r10 · finding [open] (reviewer: in scope) · R5's 'or leaves it at its default' would fail doctor for a repo with no queue block

target: spec. queue_exec.py:758-763; triage_batch_cmd.py:7049-7051: a repo with no queue: block lands nothing by any path.

<!-- fr:journal kind=review scope=spec id=spec-plan-review-1 created=2026-11-26T13:17:42+00:00 -->
### spec-plan-review-1 · review · independent spec+plan review: 10 findings

Reviewer checked decisions d1-d6 (all honoured), every named file/function/test with file:line, the spec against itself and the plan against the spec. Findings spr-r1..spr-r10, all in scope, all fixed in the spec and plan before resolve. fr release status --from-json verified tolerant of R7's facts (release_cmd.py:53-65, :112-131).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-26T13:17:42+00:00 lens=tests step=spec-plan-review -->
### lens-tests-1 · lens · A large fixture migration across unit and integration drive and land tests must keep every R10 proof

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-26T13:17:42+00:00 lens=errors step=spec-plan-review -->
### lens-errors-1 · lens · The queue gate now builds a merge context whose exceptions must not escape dry runs, snapshot reads or resume

<!-- fr:journal kind=finding scope=spec id=spr-r1-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r1 -->
### spr-r1-resolved · finding [fixed] · resolves spr-r1: The design never says how the existing squash-by-push fixtures are migrated; R2/R3 turn them into holds

R9 + Design 'Fixtures (R9)' name every fixture and say they move to merge keeping each R10 proof; plan P1.T2.S3.

<!-- fr:journal kind=finding scope=spec id=spr-r2-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r2 -->
### spr-r2-resolved · finding [fixed] · resolves spr-r2: The plan looks for land_push tests in the wrong files; files: omits the integration tests and fakes

Plan T2.S1/S3 point at tests/integration/test_queue_*.py; files: adds tests/integration/*, tests/unit/fakes.py, queue_git.py, test_queue_build.py; integration runs use -m "".

<!-- fr:journal kind=finding scope=spec id=spr-r3-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r3 -->
### spr-r3-resolved · finding [fixed] · resolves spr-r3: R3 contradicts merged row wave-queue-land-methods and its cited test; the spec amends neither

New R9 amends wave-merge-queue R10 and the wave-queue-land-methods row (reword) plus level amendments for renamed tests; plan P1.T5.S3 runs the amend ops.

<!-- fr:journal kind=finding scope=spec id=spr-r4-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r4 -->
### spr-r4-resolved · finding [fixed] · resolves spr-r4: _queue_refusal cannot just call _ctx_or_hold: ConfigError/ForgeReadError escape, and its first use is a new fetch and forge read

Design moves the check to a new _landing_hold called only from _queue_gate; it catches DefaultBranchUnknown, ConfigError and ForgeReadError into hold reasons (R2 states each); the forge-read sentence is corrected; plan T2.S4 tests a dry run and a failed read.

<!-- fr:journal kind=finding scope=spec id=spr-r5-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r5 -->
### spr-r5-resolved · finding [fixed] · resolves spr-r5: R3 checks the current method, not the one a stored combination was built in

R3 now requires every landing commit to be a merge whose second parent is the PR head (checkout parents seam, gitseam.py:1092); plan T2.S1 tests a squash-built combination landed with method=merge.

<!-- fr:journal kind=finding scope=spec id=spr-r6-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r6 -->
### spr-r6-resolved · finding [fixed] · resolves spr-r6: R2's fix merge_method: merge fails when the repo does not allow merge commits

landing_refusal takes the allowed set; R2's fix names allowing merge commits when merge is not allowed; plan T2.S1/T2.S4 test squash-only.

<!-- fr:journal kind=finding scope=spec id=spr-r7-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r7 -->
### spr-r7-resolved · finding [fixed] · resolves spr-r7: The resume path skips a landing-refused repo, so an already-pushed landing is not recorded

R2 says the resume pass still runs; the check lives in _queue_gate only and _queue_refusal is unchanged; plan T2.S4 tests resume recording for a landing-refused repo.

<!-- fr:journal kind=finding scope=spec id=spr-r8-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r8 -->
### spr-r8-resolved · finding [fixed] · resolves spr-r8: The plan says the existing choose_method test needs no change, but one case encodes the old order

Plan T1.S1 rewrites the :346-347 case to expect squash as the first #1702 assertion and renames the test.

<!-- fr:journal kind=finding scope=spec id=spr-r9-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r9 -->
### spr-r9-resolved · finding [fixed] · resolves spr-r9: R8 and files: miss pages and AGENTS.md text covering or describing the changed paths

R8 now names merge-protection.md and AGENTS.md's Release gating paragraph and every other covering page (stamp or fix); plan T5.S2 and files: include them.

<!-- fr:journal kind=finding scope=spec id=spr-r10-resolved created=2026-11-26T13:17:42+00:00 state=fixed resolves=spr-r10 -->
### spr-r10-resolved · finding [fixed] · resolves spr-r10: R5's 'or leaves it at its default' would fail doctor for a repo with no queue block

R5 fails only when a queue: block exists (land push or unset); no queue: block keeps today's check; plan T3.S1 tests all three.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-26T13:17:44+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  landing-method-order: none
  landing-method-push-merge-only: none
  landing-method-rebase-warning: none
  release-closed-unmerged-landing: none
row_kinds:
  landing-method-order: none
  landing-method-push-merge-only: none
  landing-method-rebase-warning: none
  release-closed-unmerged-landing: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-26T17:17:20+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: pre-merge — CI: `choose_method` returns the configured method over a forge default, the default when nothing is configured, the single allowed method last, and refuses a disallowed explicit or configured method (row `landing-method-order`).

Evidence: CI ci-ok green on PR #1708's final head 3a7f2e9 (run 45865158880), merged as 714686c9d: tests/unit/test_triage_batch_merge.py choose_method order tests (row landing-method-order)

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-2 created=2026-11-26T17:17:24+00:00 -->
### test-plan-step-2 · discovery · Test Plan step 2: ran

Step: pre-merge — CI: under `land: push` a `squash` or `rebase` method from each source holds the queue with a reason naming the method, its source and the fix (`merge_method: merge` when merge is allowed, allowing merge commits when it is not); `merge` does not; an unchoosable method or a failed merge-methods read holds the queue for the pass without raising, also under a dry run; the resume pass still records a landing already pushed; `land_push` with a non-merge method, or with a merge-method call whose combination commit is not a merge of its parent and the PR's head, pushes nothing; `fr cloud doctor` fails the check when a `queue:` block lands by push and passes when there is no `queue:` block (row `landing-method-push-merge-only`).

Evidence: CI ci-ok green on PR #1708's final head 3a7f2e9 (run 45865158880), merged as 714686c9d: push-landing hold tests in test_triage_batch_drive_cmd.py, test_queue_exec.py, tests/integration/test_queue_land.py and test_cloud_remedy.py (row landing-method-push-merge-only)

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-3 created=2026-11-26T17:17:26+00:00 -->
### test-plan-step-3 · discovery · Test Plan step 3: ran

Step: pre-merge — CI: under `land: merge` a `rebase` method prints the warning once per repo per process (row `landing-method-rebase-warning`).

Evidence: CI ci-ok green on PR #1708's final head 3a7f2e9 (run 45865158880), merged as 714686c9d: rebase-under-land-merge warning test in test_triage_batch_drive_cmd.py (row landing-method-rebase-warning)

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-4 created=2026-11-26T17:17:28+00:00 -->
### test-plan-step-4 · discovery · Test Plan step 4: ran

Step: pre-merge — CI: `waiting_prs` counts a first-parent PR the forge reports `CLOSED` and unmerged with the commit's date and its labels, and stays unknown for an `OPEN` PR or a failed read (row `release-closed-unmerged-landing`).

Evidence: CI ci-ok green on PR #1708's final head 3a7f2e9 (run 45865158880), merged as 714686c9d: waiting_prs closed-unmerged tests in tests/unit/test_release_script.py (row release-closed-unmerged-landing)
