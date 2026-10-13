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
