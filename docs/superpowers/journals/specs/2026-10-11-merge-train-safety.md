# Journal: 2026-10-11-merge-train-safety

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T17:13:48+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch merge-train-safety dispatch), verbatim

/fr-goal Merge train safety: required checks or a merge queue on main, recover red updated PRs

Batch `merge-train-safety` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1062: Merge race: require up-to-date/merge queue on main, release bot bypass via app token, driver enqueues where a merge queue is required
Confirmed: the only ruleset on main (`protect main`) enforces deletion + non_fast_forward; no required checks, no up-to-date rule, no merge queue. Two green PRs merged back to back broke main and a release on 2026-10-07.

## super-fr#1082: Driver: recover a batch PR that goes red after the train updates it (re-update on main moving, else hand back to the session)
A batch PR the train updated from a broken main stays red forever. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10) (batch `merge-train-recovery`).

## super-fr#1076: batch merge with no ids refuses every queued batch when one is held
Confirmed: `triage_batch_cmd.py:2184-2185` calls `_refuse_held` per queued batch before merging any, so one held batch refuses the whole default merge. Spec question whether to skip instead.

## super-fr#1129: Merge gate: draft→ready is the only human gate and agents share the operator's forge identity (driver merged a ~5,000-line PR unreviewed)
Confirmed at 1248d439: the batch dispatch brief (`batch_dispatch.py:143`) has no never-mark-ready rule, and `merge_ready` (now `batch_merge.py:387`, issue cites batch_drive.py:1055) merges any non-draft, green PR by an allowed author. One shared forge identity means an agent's `gh pr ready` is the operator's, so the driver merged ~5,000 lines unreviewed.
Note: Live risk for every running wave: the driver merges whatever a session readies.

## Why these belong together
Two green PRs broke main and a release; the train cannot recover a PR it updated from broken main. Taken over from the inactive scope s-c8805331 at the operator's request, 2026-10-10.

## Delivery rules
- Work on branch `feat/batch-merge-train-safety`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1062
  Closes derio-net/super-fr#1082
  Closes derio-net/super-fr#1076
  Closes derio-net/super-fr#1129
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-main-protection created=2026-10-11T17:13:48+00:00 -->
### d1-main-protection · decision · super-fr main requires ci-ok + up-to-date (no merge queue)

Operator (R1·Q1): required `ci-ok` with branches up to date; merge_group triggers added anyway so a queue can be enabled later.

<!-- fr:journal kind=decision scope=spec id=d2-agent-applies-forge created=2026-10-11T17:13:48+00:00 -->
### d2-agent-applies-forge · decision · The agent applies the forge changes via gh api

Operator (R1·Q2): agent applies the ruleset/variable changes post-merge; (R2·Q5) operator generates the App key in the UI and sets FR_AUTOMATION_APP_KEY, agent wires the rest, enabling the rule only after a release pushed as the app.

<!-- fr:journal kind=decision scope=spec id=d3-driver-queue-now created=2026-10-11T17:13:48+00:00 -->
### d3-driver-queue-now · decision · Build the driver's merge-queue path in this change

Operator (R1·Q3): detect merge_queue rule, enqueue, tolerate queued PRs, ejection → recovery; opt-in by detection; GitHub only.

<!-- fr:journal kind=decision scope=spec id=d4-label-gate created=2026-10-11T17:13:48+00:00 -->
### d4-label-gate · decision · The merge gate is an approved-fr repo label, not a signed approval

Operator (R1·Q4–Q6): a green `approved-fr` label, created transparently with a warning; signed approvals are a placeholder, not built; 'we need a proper design but … late for a redesign' — the label is the stop-gap.

<!-- fr:journal kind=decision scope=spec id=d5-no-bash-guard created=2026-10-11T17:13:48+00:00 -->
### d5-no-bash-guard · decision · No Bash guard for ready/merge

Operator (R1·Q7): gating on approved-fr is enough; agents may legitimately merge or mark ready. Briefs say never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=d6-skip-held created=2026-10-11T17:13:48+00:00 -->
### d6-skip-held · decision · Default batch merge skips held batches

Operator (R1·Q8): skip held, merge the rest; explicit ids still refuse.

<!-- fr:journal kind=decision scope=spec id=d7-verification created=2026-10-11T17:13:48+00:00 -->
### d7-verification · decision · candidate strategy plus live post-merge rows

Operator (R1·Q9): candidate walk over fake-forge scenarios; ruleset/release-identity rows are live post-merge.

<!-- fr:journal kind=decision scope=spec id=d8-label-head-bound created=2026-10-11T17:13:48+00:00 -->
### d8-label-head-bound · decision · The approval is bound to a head; driver updates are exempt

Operator (R2·Q1): first sighting records the approved head; a non-driver push voids it (label removed, re-label on Needs-you).

<!-- fr:journal kind=decision scope=spec id=d9-label-create-where created=2026-10-11T17:13:48+00:00 -->
### d9-label-create-where · decision · fr init scaffold and triage commands create the label

Operator (R2·Q2): collect, batch dispatch, batch merge, drive, fr init scaffold; no other fr command calls the forge for it.

<!-- fr:journal kind=decision scope=spec id=d10-label-alone created=2026-10-11T17:13:48+00:00 -->
### d10-label-alone · decision · The label alone suffices; the driver readies a labelled draft

Operator (R2·Q3): a green labelled draft is marked ready by fr and merged.

<!-- fr:journal kind=decision scope=spec id=d11-every-fr-merge-path created=2026-10-11T17:13:48+00:00 -->
### d11-every-fr-merge-path · decision · The label gate applies to every fr merge path

Operator (R2·Q4): driver, batch merge (with or without ids), and the queue enqueue.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-11T17:14:02+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 replaced the proposed signed-approval gate with an approved-fr label; the code check (no labels in PR facts, driver updates move the head, draft refused by merge_ready, batch merge shares merge_ready, App keys are UI-only) opened five decisions only that answer created.

<!-- fr:journal kind=finding scope=spec id=sr-r1-1 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-1 · finding [open] (reviewer: in scope) · batch merge does not go through merge_ready, so R1/R3 are not covered on that path

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-2 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-2 · finding [open] (reviewer: in scope) · _walk_train drops every draft, so the labelled-draft merge never reaches merge_ready

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-3 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-3 · finding [open] (reviewer: in scope) · Approval recording/voiding only runs in merge_ready, so first sighting and void removal are undecided for non-candidates

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-4 · finding [open] (reviewer: in scope) · red_decision inputs are not in Snapshot; hand-back target and budget unspecified

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-5 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-5 · finding [open] (reviewer: in scope) · R11 contradicts keeping warn, which the board turns into failing-ci

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-6 · finding [open] (reviewer: in scope) · Strict up-to-date livelocks the routine-commit skip

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-7 · finding [open] (reviewer: in scope) · --stage require's pushed-by-app check reads the commit identity

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-8 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-8 · finding [open] (reviewer: in scope) · New action kinds are not in ActionKind or kanban's phrase table

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-9 · finding [open] (reviewer: in scope) · How UpdateEvent is written from _update, and what base is, is undefined

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-10 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-10 · finding [open] (reviewer: in scope) · Ejection ignores auto-merge state; isInMergeQueue is not a gh pr view field

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-11 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-11 · finding [open] (reviewer: in scope) · Queue mode is silent on version-slot reservation

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-12 · finding [open] (reviewer: in scope) · rules/branches misses a queue from classic branch protection

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-13 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-13 · finding [open] (reviewer: in scope) · change-fragment merge_group equivalent is moot and wrong as written

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-14 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-14 · finding [open] (reviewer: in scope) · Candidate scenarios claim a fake forge that does not exist

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-15 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-15 · finding [open] (reviewer: in scope) · R16's script refusal logic has no test or row

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-16 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-16 · finding [open] (reviewer: in scope) · R4 per-pass vs per-process label creation disagree; tripwire would match operator prose

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=finding scope=spec id=sr-r1-17 created=2026-10-11T17:24:42+00:00 state=open review_scope=in -->
### sr-r1-17 · finding [open] (reviewer: in scope) · Line citations drifted

Raised by the independent spec reviewer; see the review entry spec-review-r1.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-11T17:24:42+00:00 -->
### spec-review-r1 · review · independent spec review: 17 findings, all in scope

fr-spec-reviewer raised sr-r1-1 … sr-r1-17, all in scope; decisions d1–d11 each restated in the requirements, none contradicted. All 17 fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-r1-1-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-1 -->
### sr-r1-1-resolved · finding [fixed] · resolves sr-r1-1: batch merge does not go through merge_ready, so R1/R3 are not covered on that path

Shared _approved_and_ready gate called by merge_ready and merge_one; batch merge filters unapproved before the plan prints, ids path exits 2; labels read live via pr_view (§A Merging).

<!-- fr:journal kind=finding scope=spec id=sr-r1-2-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-2 -->
### sr-r1-2-resolved · finding [fixed] · resolves sr-r1-2: _walk_train drops every draft, so the labelled-draft merge never reaches merge_ready

The walk admits a draft whose verdict is Approved/First; unapproved members go to Train.awaiting (§A The walk).

<!-- fr:journal kind=finding scope=spec id=sr-r1-3-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-3 -->
### sr-r1-3-resolved · finding [fixed] · resolves sr-r1-3: Approval recording/voiding only runs in merge_ready, so first sighting and void removal are undecided for non-candidates

settle_approvals runs every pass for every open batch PR whatever its checks, records First and executes Void with label removal; batch merge only under --yes; the residual one-pass window is stated in Out of scope.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-4 -->
### sr-r1-4-resolved · finding [fixed] · resolves sr-r1-4: red_decision inputs are not in Snapshot; hand-back target and budget unspecified

Decision moved into the command beside _conflict (pure red_decision, impure inputs); target = _hand_back's target; separate RED_HANDBACKS_PER_DISPATCH = 2; absent/done → Needs-you, with the reason (§C).

<!-- fr:journal kind=finding scope=spec id=sr-r1-5-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-5 -->
### sr-r1-5-resolved · finding [fixed] · resolves sr-r1-5: R11 contradicts keeping warn, which the board turns into failing-ci

needs_you suppresses failing-ci under a delivered red hand-back at the current head; red-pr raised from delivered:none; NEED_LABELS gains approve-pr, red-pr, queue-ejected.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-6 -->
### sr-r1-6-resolved · finding [fixed] · resolves sr-r1-6: Strict up-to-date livelocks the routine-commit skip

New R14 + base_rules.strict_checks (rulesets and classic protection); _land skips _behind_only_routinely when strict; new row merge-train-strict-up-to-date.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-7 -->
### sr-r1-7-resolved · finding [fixed] · resolves sr-r1-7: --stage require's pushed-by-app check reads the commit identity

The check reads the push-event Actions run on the release sha and its triggering_actor (a GITHUB_TOKEN push triggers none); Test Plan step 3 corrected.

<!-- fr:journal kind=finding scope=spec id=sr-r1-8-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-8 -->
### sr-r1-8-resolved · finding [fixed] · resolves sr-r1-8: New action kinds are not in ActionKind or kanban's phrase table

enqueue is a new ActionKind with a phrase; approval/void is the impure settle step, not an action; awaiting approval and in merge queue come from Train.awaiting / Train.in_merge_queue.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-9 -->
### sr-r1-9-resolved · finding [fixed] · resolves sr-r1-9: How UpdateEvent is written from _update, and what base is, is undefined

MergeContext.on_update callback; base = rev_parse(ctx.main) via a new CheckoutSeam.rev_parse; a re-slot-only update records the fetched base (§B).

<!-- fr:journal kind=finding scope=spec id=sr-r1-10-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-10 -->
### sr-r1-10-resolved · finding [fixed] · resolves sr-r1-10: Ejection ignores auto-merge state; isInMergeQueue is not a gh pr view field

pr_queue_state via gh api graphql (isInMergeQueue, autoMergeRequest), REST auto_merge; ejected requires auto-merge cleared (verified: gh pr view --json rejects isInMergeQueue).

<!-- fr:journal kind=finding scope=spec id=sr-r1-11-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-11 -->
### sr-r1-11-resolved · finding [fixed] · resolves sr-r1-11: Queue mode is silent on version-slot reservation

A queue-required repo with a version: block is held with a warning.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-12 -->
### sr-r1-12-resolved · finding [fixed] · resolves sr-r1-12: rules/branches misses a queue from classic branch protection

Stated as a limit in R12 and Out of scope.

<!-- fr:journal kind=finding scope=spec id=sr-r1-13-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-13 -->
### sr-r1-13-resolved · finding [fixed] · resolves sr-r1-13: change-fragment merge_group equivalent is moot and wrong as written

change-fragment stays pull-request-only and is skipped on merge_group; ci-ok passes a skip; a unit test pins it (R15).

<!-- fr:journal kind=finding scope=spec id=sr-r1-14-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-14 -->
### sr-r1-14-resolved · finding [fixed] · resolves sr-r1-14: Candidate scenarios claim a fake forge that does not exist

Named the existing shell-level pattern (tests/scenarios/fixtures/<name>/bin/gh, REST routes, FR_FORGE_API=rest, bare remote via insteadOf); the queue row's GraphQL path is unit-tested, stated in Verification.

<!-- fr:journal kind=finding scope=spec id=sr-r1-15-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-15 -->
### sr-r1-15-resolved · finding [fixed] · resolves sr-r1-15: R16's script refusal logic has no test or row

tests/unit/test_configure_main_protection.py with a stub gh; new row main-protection-script citing R17.

<!-- fr:journal kind=finding scope=spec id=sr-r1-16-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-16 -->
### sr-r1-16-resolved · finding [fixed] · resolves sr-r1-16: R4 per-pass vs per-process label creation disagree; tripwire would match operator prose

Once per repo per pass or command (seen set); the tripwire exempts sentences naming never/do not/don't/operator.

<!-- fr:journal kind=finding scope=spec id=sr-r1-17-resolved created=2026-10-11T17:24:42+00:00 state=fixed resolves=sr-r1-17 -->
### sr-r1-17-resolved · finding [fixed] · resolves sr-r1-17: Line citations drifted

Re-cited triage_batch_cmd.py:2220-2221 and views.py:182-193; §E now partitions the shared loop before the one-repo check.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-11-merge-train-safety-p2 created=2026-10-11T17:27:20+00:00 -->
### phase-split-2026-10-11-merge-train-safety-p2 · decision · ask: red-PR recovery, strict up-to-date and skip-held (#1082, #1076) are their own asks

ask: red-PR recovery, strict up-to-date and skip-held (#1082, #1076) are their own asks

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-11-merge-train-safety-p3 created=2026-10-11T17:27:29+00:00 -->
### phase-split-2026-10-11-merge-train-safety-p3 · decision · ask: driver merge-queue support and merge_group CI (#1062 piece 3)

ask: driver merge-queue support and merge_group CI (#1062 piece 3)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-11-merge-train-safety-p4 created=2026-10-11T17:27:40+00:00 -->
### phase-split-2026-10-11-merge-train-safety-p4 · decision · ask: release identity, protection script and runbook (#1062 pieces 1-2)

ask: release identity, protection script and runbook (#1062 pieces 1-2)
