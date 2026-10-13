<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-exit-gates

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-13T22:49:57+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch exit-gates (verbatim)

/fr-goal Declare each PR's exit: verification-kind label, quality gates, board lanes, install channels

Batch `exit-gates` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#1189: Route every batch PR to a declared exit: verification-kind label, quality gates, and no Closes over unfinished asks
Declare each PR's exit at decision time: a verification:<kind> label, routing by the manifest's driver (agent drives through, operator waits under Needs you now), named quality gates, and deliver refusing Closes over unmet asks. From the 2026-10-13 merged-batch audit (20 of 35 partial).

## super-fr#1155: explicit row verify: on a spec with no ## Verification section is never flagged though walk_owed still owes it
An explicit row `verify:` on a spec with no `## Verification` section is never flagged though walk_owed still owes it (spec-mandated exemption).

## super-fr#667: fr triage batch closeout: close a merged batch queue in one session instead of N competing fr pickup closeouts
N concurrent close-outs collide on archive. The driver now closes out per batch through its runner (skill text); whether the collision remains needs a re-read.

## Why these belong together
Operator priority after the 2026-10-13 audit. Re-created from exit-routing with #1086's design folded into #1189; #1155 (verify kind without a section) and #667 (one close-out for a merged queue) ride the same exit path.

## Delivery rules
- Work on branch `feat/batch-exit-gates`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1189
  Closes derio-net/super-fr#1155
  Closes derio-net/super-fr#667
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=q1-label-per-kind created=2026-10-13T22:49:57+00:00 -->
### q1-label-per-kind · decision · Q1: one verification:<kind> label per distinct kind

Operator chose one label per kind (not 'longest wait wins'). Spec R7.

<!-- fr:journal kind=decision scope=spec id=q2-gate-separate-from-kind created=2026-10-13T22:49:57+00:00 -->
### q2-gate-separate-from-kind · decision · Q2: the gate is declared separately from the verification kind

Operator: whether a kind is pre- or post-merge is repo-specific (one repo runs candidate in containers, another by hand), so verification and gate are not one-to-one; both are set, e.g. {verification: candidate, gate: tester} or {verification: library, gate: devops}. Spec R1-R6.

<!-- fr:journal kind=decision scope=spec id=q3-config-manifest-and-triage-yaml created=2026-10-13T22:49:57+00:00 -->
### q3-config-manifest-and-triage-yaml · decision · Q3: manifest gate: default + .fr/triage.yaml exit: remap

Operator chose the recommended option. Spec R3, R4.

<!-- fr:journal kind=decision scope=spec id=q4-premise-corrected created=2026-10-13T22:49:57+00:00 -->
### q4-premise-corrected · decision · Q4: asked on a wrong premise, re-asked in round 2

I claimed the unarchived-plans tripwire fails every PR; the operator questioned it and the code shows it only warns since 2026-09-26. Re-asked as round 2 Q1.

<!-- fr:journal kind=decision scope=spec id=q5-gate-pass-both created=2026-10-13T22:49:57+00:00 -->
### q5-gate-pass-both · decision · Q5: a gate passes by rows walked on main OR an explicit command

Operator chose both. Spec R14.

<!-- fr:journal kind=decision scope=spec id=q6-file-at-deliver-autonomous-closeout created=2026-10-13T22:49:57+00:00 -->
### q6-file-at-deliver-autonomous-closeout · decision · Q6: leftover issues are filed at deliver; close-out becomes fully autonomous

Operator: file at deliver, which makes the close-out fully autonomous; the driver may fix merge conflicts and repair tests once before asking the operator. Spec R9, R10, R15.

<!-- fr:journal kind=decision scope=spec id=q7-owner-vocabulary-and-narrowing created=2026-10-13T22:49:57+00:00 -->
### q7-owner-vocabulary-and-narrowing · decision · Q7: gate vocabulary + operator-answered narrowing rule; Security vocabulary only

Operator chose the recommended option. Spec R2, R11, R12.

<!-- fr:journal kind=decision scope=spec id=q8-collected-closeout created=2026-10-13T22:49:57+00:00 -->
### q8-collected-closeout · decision · Q8: one close-out session for the merged queue, flipped ready once clean

Operator chose #667's collected close-out; since close-outs carry no decisions, they are collected and the PR is flipped ready once it has no conflicts and no test errors; the driver tries once to reconcile before turning to the operator. Spec R15.

<!-- fr:journal kind=decision scope=spec id=q9-rc-commit-and-tag created=2026-10-13T22:49:57+00:00 -->
### q9-rc-commit-and-tag · decision · Q9: an RC is a release commit with RC versions plus a tag

Operator chose the recommended option. Spec R20.

<!-- fr:journal kind=decision scope=spec id=q10-final-automatic-when-clear created=2026-10-13T22:49:57+00:00 -->
### q10-final-automatic-when-clear · decision · Q10: the final release is cut automatically when nothing awaits a gate

Operator chose the recommended option. Spec R20, R21.

<!-- fr:journal kind=decision scope=spec id=q11-channel-in-bootstrap created=2026-10-13T22:49:57+00:00 -->
### q11-channel-in-bootstrap · decision · Q11: the install channel lives in bootstrap.sh; install.sh installs its checkout

Operator chose the recommended option, keeping the driver's post_merge install of main unchanged. Spec R22, R23.

<!-- fr:journal kind=decision scope=spec id=q12-all-row-checks created=2026-10-13T22:49:57+00:00 -->
### q12-all-row-checks · decision · Q12 (#1155): every row check runs on a row's own verify: without a section

Operator chose the recommended option. Spec R24.

<!-- fr:journal kind=decision scope=spec id=q13-candidate-plus-live created=2026-10-13T22:49:57+00:00 -->
### q13-candidate-plus-live · decision · Q13: run-level candidate, live rows for real forge/driver/release behaviour

Operator chose the recommended option. Spec ## Verification.

<!-- fr:journal kind=decision scope=spec id=r2q1-held-out-of-closeout created=2026-10-13T22:49:57+00:00 -->
### r2q1-held-out-of-closeout · decision · Round 2 Q1: a held batch is kept out of close-out until its gate passes

Operator chose the recommended option. Spec R13, R16.

<!-- fr:journal kind=decision scope=spec id=r2q2-spec-gate-line created=2026-10-13T22:49:57+00:00 -->
### r2q2-spec-gate-line · decision · Round 2 Q2: a spec gate: line (and per-row gate=) overrides the repo mapping

Operator chose the recommended option. Spec R5, R8.

<!-- fr:journal kind=decision scope=spec id=r2q3-pr-labels-ledger created=2026-10-13T22:49:57+00:00 -->
### r2q3-pr-labels-ledger · decision · Round 2 Q3: the merged PR's gate labels are the gate ledger

Operator chose the recommended option. Spec R14, R20, R21.

<!-- fr:journal kind=decision scope=spec id=r2q4-closeout-no-approval created=2026-10-13T22:49:57+00:00 -->
### r2q4-closeout-no-approval · decision · Round 2 Q4: the collected close-out PR merges without approved-fr

Operator chose the recommended option. Spec R15.

<!-- fr:journal kind=decision scope=spec id=closes-vs-refs-delivery-rule created=2026-10-13T22:49:57+00:00 -->
### closes-vs-refs-delivery-rule · decision · Rows carry no issues: refs so the operator's Closes delivery rule holds

The batch's delivery rules require Closes for all three members, while this feature's own rule is Refs for an issue held by a post-merge gate. Followed the operator's explicit delivery rule; no acceptance row cites a member issue. Raised in the PR body.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-13T22:50:32+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 split the gate from the verification kind (Q2) and chose a collected, autonomous close-out (Q6/Q8); the cross-examination found the unarchived-plans tripwire only warns (Q4 was asked on a wrong premise), that triage reads labels only on open PRs and keeps state off main, so the hold point, the per-run gate override, the gate ledger and the close-out merge rule needed a second round.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · R19 (never plan merge for a CONFLICTING PR) removes the trigger of the conflict hand-back it says is unchanged, and stops version-file auto-resolution

Evidence: batch_merge.py:611-634 (_update raises MergeConflictError, resolves version/lock files); triage_batch_cmd.py:4897-4900, 5046-5048.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · R1 builds the gate set from rows alone, so a DevOps gate with no row or a run-level gate: on a run with no rows can never be declared

Evidence: spec R1, R5, R14.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · Release tooling cannot read an RC version once one is on main: the next final crashes, and the version-sync check reports drift

Evidence: release.py:245-285, 529-533; changes.py:139-150; bump-version.py:27-101; floors.py:43-44.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · §G's 'nothing new merged since the newest tag → no-op' blocks the final that R20, q10 and Test Plan step 4 promise after a gate pass

Evidence: decisions q10, r2q3; spec R14, R20, §G, Test Plan 4.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · Tag channels fail on any tag whose install.sh predates R23, including the default channel right after this PR

Evidence: install.sh:439-447; bootstrap.sh:77-90.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · An RC install (X.Y.ZrcN) does not satisfy fr_version floors that name the predicted final

Evidence: version_floor.py:33-43; AGENTS.md floor convention.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · R10/§C misdescribe the archive filer: --issues files follow-up issues, fr:owed is the separate owed-entry path, and --no-issues still files

Evidence: archive_followups.py:60, 236-271, 489-518; archive_cmd.py:405-406, 555, 578-609.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · The collected close-out leaves out Test Plan outcomes, so fr archive holds every plan whose spec has a Test Plan

Evidence: archive.py:815-844 outcome_hold; archive_cmd.py:720-722.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · attributed does not compare the PR head with event.archive, so a shared close-out branch is not attributed

Evidence: batch_drive.py:684-707, 65, 513-530.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · 'Existing hand-back machinery with a budget of one' for the collected close-out PR is undefined

Evidence: batch_drive.py:554-653, 1298-1337.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · §C's claim that 'held by a post-merge gate' is a superset of 'post-merge' is false under remaps, which weakens the existing Closes guard

Evidence: pr_body.py:488-522.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · PR label sync and gate-pass comments have no adapter method for MRs

Evidence: ghclient.py:185-239; real_glabclient.py:212-227; closeout.py:350-358.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · Adding gate: to StrategyManifest is not free: extra=forbid with schema Literal[1]

Evidence: verification/model.py:59-73; resolve.py:1-14.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · The per-row gate= token makes an older fr raise SectionError on the spec

Evidence: spec_section.py:35-38, 109-115; registry.py:494-497.

<!-- fr:journal kind=finding scope=spec id=sr-15 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-15 · finding [open] (reviewer: in scope) · §C leaves the record-kind stamp to plan time, but the rule already decides it

Evidence: record/model.py:95-138; registry.py:515-546.

<!-- fr:journal kind=finding scope=spec id=sr-16 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-16 · finding [open] (reviewer: in scope) · R11/R12's 'answered by the operator' has no mechanism for a decision entry, and narrows= encoding is unspecified

Evidence: journal/model.py:222-226, 321-331.

<!-- fr:journal kind=finding scope=spec id=sr-17 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-17 · finding [open] (reviewer: in scope) · R9's 'deferred item' is accounted by definition; owed entries and rows tracked by issues: are not addressed

Evidence: journal/model.py:122-184, 619-635.

<!-- fr:journal kind=finding scope=spec id=sr-18 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-18 · finding [open] (reviewer: in scope) · R15 does not say which Refs issues a close-out closes; issues R11 kept as Refs (narrowed) would be closed

Evidence: spec R11, R15, R16.

<!-- fr:journal kind=finding scope=spec id=sr-19 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-19 · finding [open] (reviewer: in scope) · R24 widens the brainstorm warning to all four row checks, but it only ran the install check; the reason-check fix changes other rows

Evidence: run_cmd.py:6780-6796; plan_ops.py:1677-1678; effective.py:31-40.

<!-- fr:journal kind=finding scope=spec id=sr-20 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-20 · finding [open] (reviewer: in scope) · 'held' already names three other states in the driver, and 'gate' already names the workflow step gate: operator

Evidence: batch_drive.py:59, 557, 1211-1223; workflow/model.py:54.

<!-- fr:journal kind=finding scope=spec id=sr-21 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-21 · finding [open] (reviewer: in scope) · Background says the board does not read mergeable/mergeStateStatus, but the triage page and kanban already do, with a different conflict test

Evidence: render.py:609-610; kanban_render.py:235; kanban.py:177.

<!-- fr:journal kind=finding scope=spec id=sr-22 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-22 · finding [open] (reviewer: in scope) · TriageConfig.exit also moves FACTS_SCHEMA, and an older fr refuses a .fr/triage.yaml that sets it

Evidence: triage/model.py:39-63, 471.

<!-- fr:journal kind=finding scope=spec id=sr-23 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-23 · finding [open] (reviewer: in scope) · An operator-approved narrowing still allows Closes with no follow-up (the audit's first pattern)

Evidence: spec Background, R9, R11; decision q7.

<!-- fr:journal kind=finding scope=spec id=sr-24 created=2026-10-13T23:03:12+00:00 state=open review_scope=in -->
### sr-24 · finding [open] (reviewer: in scope) · The new release group's migration-gate status and fr verification set's insert behaviour are unspecified

Evidence: trigger.py:82-94; spec R8, R21.

<!-- fr:journal kind=finding scope=spec id=sr-25 created=2026-10-13T23:03:12+00:00 state=open review_scope=out -->
### sr-25 · finding [open] (reviewer: out of scope) · The triage page counts mergeStateStatus BLOCKED as a conflict

Evidence: render.py:610. BLOCKED is branch protection, the normal state of every unapproved batch PR.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-13T23:03:12+00:00 -->
### spec-review · review · independent spec review: 25 findings (24 in, 1 out)

Reviewer checked the spec against all 18 operator decisions, the codebase claims (file:line for each named helper), and internal consistency incl. the Verification section and Test Plan against the ten exit-gates-* rows. Most serious: sr-1 (R19 would kill the conflict hand-back), sr-3..sr-6 (RC versions vs release tooling, floors, bootstrap), sr-7/sr-8 (archive filer and Test Plan hold vs the collected close-out), sr-9 (attributed), sr-12 (no PR label adapter). All 24 in-scope findings fixed in the spec; sr-25 out of scope.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: R19 (never plan merge for a CONFLICTING PR) removes the trigger of the conflict hand-back it says is unchanged, and stops version-file auto-resolution

Spec rewritten: R19 now keeps the train planning the merge; only the card hint and needs_you use the conflicting() predicate.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: R1 builds the gate set from rows alone, so a DevOps gate with no row or a run-level gate: on a run with no rows can never be declared

Spec rewritten: R1 adds a run-level gate (run gate: line > remap > manifest > none) into gates; R14's explicit pass covers a gate with no row.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: Release tooling cannot read an RC version once one is on main: the next final crashes, and the version-sync check reports drift

Spec rewritten: New R25 + §G: final-only tag match, RC arithmetic based on the last final, write_version writes both spellings, --check normalizes.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: §G's 'nothing new merged since the newest tag → no-op' blocks the final that R20, q10 and Test Plan step 4 promise after a gate pass

Spec rewritten: R20 rewritten: only a second RC with nothing new is a no-op; a final is due whenever nothing waits and HEAD is an RC or fragments are pending.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: Tag channels fail on any tag whose install.sh predates R23, including the default channel right after this PR

Spec rewritten: R22: a tag is installable only when its install.sh carries the channel marker; default falls back to origin/main while none exists; main uses checkout -B main origin/main.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: An RC install (X.Y.ZrcN) does not satisfy fr_version floors that name the predicted final

Spec rewritten: New R26: floors admit an RC of X.Y.Z wherever they admit X.Y.Z (§G version_floor.admits).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: R10/§C misdescribe the archive filer: --issues files follow-up issues, fr:owed is the separate owed-entry path, and --no-issues still files

Spec rewritten: Background, R9, R10 and R15 now name file_open_ends (follow-up) and file_owed_ends (fr:owed, filed_as) correctly; the close-out's archive still files owed entries it creates, which needs no decision.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: The collected close-out leaves out Test Plan outcomes, so fr archive holds every plan whose spec has a Test Plan

Spec rewritten: R15 step 2 records each Test Plan step's outcome (--ran, gate-pass comment as evidence) for a passed gated batch; a batch whose archive holds moves nothing, gets no close-out event and becomes a Needs-you row.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: attributed does not compare the PR head with event.archive, so a shared close-out branch is not attributed

Spec rewritten: §D: attributed also accepts pr.head_ref == event.archive for a trusted author.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: 'Existing hand-back machinery with a budget of one' for the collected close-out PR is undefined

Spec rewritten: New R27 + §D step 3: closeout_handback event on each member keyed by close-out item and head, budget counted per item, detection from live checks and the conflicting() predicate; judgements schema moves.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: §C's claim that 'held by a post-merge gate' is a superset of 'post-merge' is false under remaps, which weakens the existing Closes guard

Spec rewritten: R11/§C: keep holds_open_for_run's test and OR in 'gated by a post-merge gate'.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: PR label sync and gate-pass comments have no adapter method for MRs

Spec rewritten: R7/§B: new edit_pr_labels/comment_pr adapter methods (GitHub implemented, GitLab/Gitea raise UnsupportedForgeOperation → warning, not refusal); tracking none syncs nothing; label creation via ensure_labels.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: Adding gate: to StrategyManifest is not free: extra=forbid with schema Literal[1]

Spec rewritten: R3/§A: gate: only at schema 2; absent = none; only live moves to schema 2; each fr reads its own wheel copy before the marketplace.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: The per-row gate= token makes an older fr raise SectionError on the spec

Spec rewritten: R5: gates move to `gate:` lines (`gate: <g>` and `gate: <row>=<g>`), which released parsers ignore; no spec-kind stamp move.

<!-- fr:journal kind=finding scope=spec id=sr-15-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-15 -->
### sr-15-resolved · finding [fixed] · resolves sr-15: §C leaves the record-kind stamp to plan time, but the rule already decides it

Spec rewritten: §C states the record kind moves 9 → 10 with migration and validator in this PR.

<!-- fr:journal kind=finding scope=spec id=sr-16-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-16 -->
### sr-16-resolved · finding [fixed] · resolves sr-16: R11/R12's 'answered by the operator' has no mechanism for a decision entry, and narrows= encoding is unspecified

Spec rewritten: R12: answered_by=operator token on a decision, written only by the brainstorm record's resolve or a transcript-verified fr journal add --answered-by operator; narrows= is comma-separated.

<!-- fr:journal kind=finding scope=spec id=sr-17-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-17 -->
### sr-17-resolved · finding [fixed] · resolves sr-17: R9's 'deferred item' is accounted by definition; owed entries and rows tracked by issues: are not addressed

Spec rewritten: R9 now lists four item kinds (out-of-scope finding, owed entry, owed row, narrowing decision) with accounted predicates matching §C's printed fixes, incl. a row's issues:.

<!-- fr:journal kind=finding scope=spec id=sr-18-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-18 -->
### sr-18-resolved · finding [fixed] · resolves sr-18: R15 does not say which Refs issues a close-out closes; issues R11 kept as Refs (narrowed) would be closed

Spec rewritten: R15 step 4: close only issues cited by rows a passed gate gated, never an issue a narrowing decision names.

<!-- fr:journal kind=finding scope=spec id=sr-19-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-19 -->
### sr-19-resolved · finding [fixed] · resolves sr-19: R24 widens the brainstorm warning to all four row checks, but it only ran the install check; the reason-check fix changes other rows

Spec rewritten: R24/§H: one row_verification_issues function called by both, widening the warning deliberately; the message warns that a new section changes other rows' effective strategy.

<!-- fr:journal kind=finding scope=spec id=sr-20-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-20 -->
### sr-20-resolved · finding [fixed] · resolves sr-20: 'held' already names three other states in the driver, and 'gate' already names the workflow step gate: operator

Spec rewritten: Spec now says 'gated' for a batch awaiting a post-merge gate and 'step gate' for gate: operator (Background, R2, R6, R13, R17).

<!-- fr:journal kind=finding scope=spec id=sr-21-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-21 -->
### sr-21-resolved · finding [fixed] · resolves sr-21: Background says the board does not read mergeable/mergeStateStatus, but the triage page and kanban already do, with a different conflict test

Spec rewritten: Background corrected; R19 names one conflicting() predicate in triage/mergeability.py for the card and needs_you; the page's BLOCKED test is sr-25 (out of scope).

<!-- fr:journal kind=finding scope=spec id=sr-22-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-22 -->
### sr-22-resolved · finding [fixed] · resolves sr-22: TriageConfig.exit also moves FACTS_SCHEMA, and an older fr refuses a .fr/triage.yaml that sets it

Spec rewritten: §A/§D: the FACTS_SCHEMA move cites both fields; minimum fr documented; this repo sets no exit: in this PR.

<!-- fr:journal kind=finding scope=spec id=sr-23-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-23 -->
### sr-23-resolved · finding [fixed] · resolves sr-23: An operator-approved narrowing still allows Closes with no follow-up (the audit's first pattern)

Spec rewritten: R9: a narrowing decision is a leftover until it carries tracked_by= (fr journal file files the follow-up), operator-answered or not; R11 still decides Closes vs Refs.

<!-- fr:journal kind=finding scope=spec id=sr-24-resolved created=2026-10-13T23:03:12+00:00 state=fixed resolves=sr-24 -->
### sr-24-resolved · finding [fixed] · resolves sr-24: The new release group's migration-gate status and fr verification set's insert behaviour are unspecified

Spec rewritten: R21: release joins READ_ONLY_COMMANDS; R8: set inserts or rewrites the line and refuses a spec with no section, naming how to add one.

<!-- fr:journal kind=finding scope=spec id=sr-25-resolved created=2026-10-13T23:03:12+00:00 state=open resolves=sr-25 out_of_scope=true -->
### sr-25-resolved · finding [out-of-scope] · resolves sr-25: The triage page counts mergeStateStatus BLOCKED as a conflict

Pre-existing in the triage page's open-PR row; this change does not touch render.py's conflict test and introduces its own predicate for the card and needs_you. Listed under the spec's Non-goals.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p2 created=2026-10-13T23:05:59+00:00 -->
### phase-split-2026-10-14-exit-gates-p2 · decision · ask: PR labels and fr verification set (R7, R8) are reviewable on their own over phase 1's exit

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p3 created=2026-10-13T23:06:03+00:00 -->
### phase-split-2026-10-14-exit-gates-p3 · decision · ask: deliver's leftover accounting, fr journal file and the narrowing Closes guard (R9-R12)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p4 created=2026-10-13T23:06:05+00:00 -->
### phase-split-2026-10-14-exit-gates-p4 · decision · ask: driver routing of gated batches and the gate ledger (R13, R14)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p5 created=2026-10-13T23:06:08+00:00 -->
### phase-split-2026-10-14-exit-gates-p5 · decision · ask: the board's Needs-you lanes and the conflicting predicate (R17-R19)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p6 created=2026-10-13T23:06:11+00:00 -->
### phase-split-2026-10-14-exit-gates-p6 · decision · ask: the collected close-out of #667 (R15, R16, R27)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p7 created=2026-10-13T23:06:14+00:00 -->
### phase-split-2026-10-14-exit-gates-p7 · decision · ask: release gating and RC versions (R20, R21, R25, R26)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-exit-gates-p8 created=2026-10-13T23:06:17+00:00 -->
### phase-split-2026-10-14-exit-gates-p8 · decision · ask: install channels in bootstrap.sh/install.sh (R22, R23)
