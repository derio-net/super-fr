# Journal: 2026-10-06-verification-strategies

<!-- fr:journal kind=discovery scope=spec id=brief-batch-verification-kinds created=2026-10-06T11:05:13+00:00 input=true -->
### brief-batch-verification-kinds · discovery · Operator brief — batch verification-kinds (#818,

/fr-goal Verification before merge: candidate walks for software repos, issues closed on live evidence, and merge conflicts handed back to the batch session

Batch `verification-kinds` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#818: Verification kinds: a pre-merge candidate walk for software repos, instead of live walks after release
For software repos a live walk after merge means the first real test happens on main; 18 of 105 recent issues were first defects of shipped features. Proposes a pre-merge candidate walk as a verification kind.
Note: Design issue; #817 is its evidence (six closed fixes failed or partly failed live).

## super-fr#822: Close an issue whose promise is run behaviour on live evidence: deliver refuses Closes #n while its matrix row awaits a live walk
Proposed rule: deliver refuses Closes #n while a matrix row citing #n awaits a live walk; the live walk names harness and model; waiting issues are kept out of the ranked backlog. Interim until #818.
Note: After the talk; pairs with #821 (same deliver PR-body gate).

## super-fr#959: triage drive: hand real merge conflicts back to the batch's session
A real merge conflict stops the train with `stopped again at <head>` until the operator nudges the batch session. Hand-delivered twice on 2026-10-05 (#922, #951).
Note: Seen live 2026-10-05.

## Why these belong together
Wave 7 (operator 2026-10-06). #818: a pre-merge candidate walk replaces post-merge Test Plans for libraries and CLIs, gating deliver; live stays for infrastructure. #822: an issue whose promise is run behaviour closes on its live evidence (same deliver gate). #959: a real merge conflict goes back to the batch's session instead of stalling the train (handed back by hand 6 times on 2026-10-05/06). Starts with a brainstorm: #818's four open questions are the operator's.

## Delivery rules
- Work on branch `feat/batch-verification-kinds`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#818
  Closes derio-net/super-fr#822
  Closes derio-net/super-fr#959
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-strategy-home created=2026-10-06T11:05:13+00:00 -->
### q1-strategy-home · decision · Verification is per issue with a shape default, extensible like workflows

Operator: not repo-specific; a default dependent on shape is acceptable; each issue decides its own; per-row override is the right scoping; pre-merge ideal, other sanctioned strategies (client-live without a release, staging rc) when not possible; post-merge live walk is the last resort; client repos can author their own strategies. → R1, R4–R7.

<!-- fr:journal kind=decision scope=spec id=q2-gate-form created=2026-10-06T11:05:13+00:00 -->
### q2-gate-form · decision · A pre-merge agent walk gates deliver as evidence

Deliver evidence `walk`, verified like `tests`; status vocabulary unchanged. → R11.

<!-- fr:journal kind=decision scope=spec id=q3-scenarios created=2026-10-06T11:05:13+00:00 -->
### q3-scenarios · decision · Run's rows plus a baseline smoke

Every walk runs the smoke; then the scenario of each row the run's spec cites. → R9.

<!-- fr:journal kind=decision scope=spec id=q4-prerelease created=2026-10-06T11:05:13+00:00 -->
### q4-prerelease · decision · Pre-release in scope, on demand, if the issue asks

→ R24 (with r2q6).

<!-- fr:journal kind=decision scope=spec id=q5-ship-scope created=2026-10-06T11:05:13+00:00 -->
### q5-ship-scope · decision · Ship candidate + client-live beyond mechanism and live

Staging/preview documented as a repo-authored example. → R3, R4.

<!-- fr:journal kind=decision scope=spec id=q6-row-issues created=2026-10-06T11:05:13+00:00 -->
### q6-row-issues · decision · Rows cite issues through a new issues: field

Matrix shape change. → R13.

<!-- fr:journal kind=decision scope=spec id=q7-close-on-flip created=2026-10-06T11:05:13+00:00 -->
### q7-close-on-flip · decision · set-status prints the close command; fr never closes

→ R16.

<!-- fr:journal kind=decision scope=spec id=q8-harness-model created=2026-10-06T11:05:13+00:00 -->
### q8-harness-model · decision · Structured walks list with harness and model; harness-wide rows need a pass per harness

→ R14.

<!-- fr:journal kind=decision scope=spec id=q9-awaiting-mark created=2026-10-06T11:05:13+00:00 -->
### q9-awaiting-mark · decision · fr:awaiting-live label; triage lists it separately

→ R17, R18.

<!-- fr:journal kind=decision scope=spec id=q10-retry-bound created=2026-10-06T11:05:13+00:00 -->
### q10-retry-bound · decision · Two conflict hand-backs, then needs-you

→ R22.

<!-- fr:journal kind=decision scope=spec id=q11-test-plan created=2026-10-06T11:05:13+00:00 -->
### q11-test-plan · decision · Dogfood: this PR is verified by its own candidate walk

Only the live herdr hand-back stays post-merge. → R25.

<!-- fr:journal kind=decision scope=spec id=r2q1-strategy-def created=2026-10-06T11:05:13+00:00 -->
### r2q1-strategy-def · decision · A strategy is a YAML manifest resolved repo > shipped like workflows

→ R1, R2.

<!-- fr:journal kind=decision scope=spec id=r2q2-default-from created=2026-10-06T11:05:13+00:00 -->
### r2q2-default-from · decision · The workflow manifest supplies the default strategy

→ R5.

<!-- fr:journal kind=decision scope=spec id=r2q3-per-issue created=2026-10-06T11:05:13+00:00 -->
### r2q3-per-issue · decision · Spec ## Verification section, row override via verify:

→ R6, R7.

<!-- fr:journal kind=decision scope=spec id=r2q4-last-resort created=2026-10-06T11:05:13+00:00 -->
### r2q4-last-resort · decision · A post-merge strategy needs a stated reason

→ R6, R12.

<!-- fr:journal kind=decision scope=spec id=r2q5-operator-walk created=2026-10-06T11:05:13+00:00 -->
### r2q5-operator-walk · decision · An operator pre-merge walk blocks the ready box, not deliver

→ R12.

<!-- fr:journal kind=decision scope=spec id=r2q6-prerelease created=2026-10-06T11:05:13+00:00 -->
### r2q6-prerelease · decision · Ship a prerelease strategy with an on-demand pre-release workflow

→ R3, R24.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-06T11:05:20+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 Q1 replaced the proposed live/candidate/preview enum with an extensible, per-issue strategy vocabulary defaulted by shape; round 2 settled what a strategy is, where its default and per-issue choice live, how post-merge stays last resort, whether an operator walk blocks deliver, and what ships for pre-release.
