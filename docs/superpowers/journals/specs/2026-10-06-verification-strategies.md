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

<!-- fr:journal kind=finding scope=spec id=sr-r1-1 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-1 · finding [open] (reviewer: in scope) · R15 refuses this PR's own Closes lines for #959/#818

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-2 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-2 · finding [open] (reviewer: in scope) · Two post-merge rows contradict R25 and decision q11

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-3 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-3 · finding [open] (reviewer: in scope) · Run-level candidate makes R10 demand a scenario for every row

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-4 · finding [open] (reviewer: in scope) · No per-subcommand migration-gate exemption exists

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-5 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-5 · finding [open] (reviewer: in scope) · Earlier matrix hops still use the live parser

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-6 · finding [open] (reviewer: in scope) · Other verify == post-merge consumers go unnamed

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-7 · finding [open] (reviewer: in scope) · Record AcceptanceItem needs a 7→8 shape change

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-8 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-8 · finding [open] (reviewer: in scope) · Wheel copy made canonical, the reverse of workflows

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-9 · finding [open] (reviewer: in scope) · Omitting walk contradicts _verified_evidence rule 2

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-10 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-10 · finding [open] (reviewer: in scope) · Slug and issue-close rendering do not exist in the forge adapter

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-11 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-11 · finding [open] (reviewer: in scope) · Walk model has no detection source

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-12 · finding [open] (reviewer: in scope) · candidate-install omits the runner packages

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-13 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-13 · finding [open] (reviewer: in scope) · R22 conflict counting is ambiguous

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-14 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-14 · finding [open] (reviewer: in scope) · A blocked session may get the brief; R23 says capability

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-15 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-15 · finding [open] (reviewer: in scope) · R7 and §B precedence differ; row-level verify has no reason source

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=finding scope=spec id=sr-r1-16 created=2026-10-06T11:14:23+00:00 state=open review_scope=in -->
### sr-r1-16 · finding [open] (reviewer: in scope) · Test Plan reserved for post-merge while this spec's Test Plan is pre-merge

See the reviewer's return (independent spec review, spec-review-r1). Evidence and file:line refs are as reported.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-06T11:14:23+00:00 -->
### spec-review-r1 · review · Independent spec review: 16 findings, all in scope

fr-spec-reviewer raised sr-r1-1..16, all in scope; all fixed in the spec. Decisions q1–q11 and r2q1–r2q6 were otherwise honoured, and the reviewer verified every named file:line it checked.

<!-- fr:journal kind=finding scope=spec id=sr-r1-1-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-1 -->
### sr-r1-1-resolved · finding [fixed] · resolves sr-r1-1: R15 refuses this PR's own Closes lines for #959/#818

§I: this PR's rows carry no issues:; the operator's Closes rule stands and #822 is not dogfooded on its own closing lines, stated in the PR body.

<!-- fr:journal kind=finding scope=spec id=sr-r1-2-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-2 -->
### sr-r1-2-resolved · finding [fixed] · resolves sr-r1-2: Two post-merge rows contradict R25 and decision q11

R25 now says only behaviour that cannot run pre-merge stays live, each with its reason; prerelease's pre-merge part is the new candidate row prerelease-command-shape (--dry-run argv + non-GitHub refusal); Test Plan lists both live rows.

<!-- fr:journal kind=finding scope=spec id=sr-r1-3-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-3 -->
### sr-r1-3-resolved · finding [fixed] · resolves sr-r1-3: Run-level candidate makes R10 demand a scenario for every row

Added the reserved override none (with a reason) to R6/R7/§B; ## Verification now maps every row: six candidate rows with scenarios, the rest live or none with reasons.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-4 -->
### sr-r1-4-resolved · finding [fixed] · resolves sr-r1-4: No per-subcommand migration-gate exemption exists

§A: the verification group stays under the gate as a whole, citing trigger.py:82-92/:223; walk reads the matrix with the live parser.

<!-- fr:journal kind=finding scope=spec id=sr-r1-5-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-5 -->
### sr-r1-5-resolved · finding [fixed] · resolves sr-r1-5: Earlier matrix hops still use the live parser

§B: guard_matrix (shared by 1→2 and 2→3) is re-pointed at the frozen MatrixV3 reader; the chain [2,3,4] is asserted.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-6 -->
### sr-r1-6-resolved · finding [fixed] · resolves sr-r1-6: Other verify == post-merge consumers go unnamed

§B lists pr_body._post_merge_owed, run/visual.py:67, acceptance_cmd.py:430-432 and record/template.py:109, all switched to effective.is_post_merge.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-7 -->
### sr-r1-7-resolved · finding [fixed] · resolves sr-r1-7: Record AcceptanceItem needs a 7→8 shape change

§B adds Record kind 7→8: widened verify, new fields, a frozen RecordV7 reader, a stamp migration and a validator.

<!-- fr:journal kind=finding scope=spec id=sr-r1-8-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-8 -->
### sr-r1-8-resolved · finding [fixed] · resolves sr-r1-8: Wheel copy made canonical, the reverse of workflows

§A: the plugin directory is canonical and the wheel copy is generated; author docs move to docs/verification-strategies.md and the fr-acceptance skill.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-9 -->
### sr-r1-9-resolved · finding [fixed] · resolves sr-r1-9: Omitting walk contradicts _verified_evidence rule 2

§C: the owed predicate runs before rule 2, and an absent walk is satisfied when not owed; Risks restated.

<!-- fr:journal kind=finding scope=spec id=sr-r1-10-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-10 -->
### sr-r1-10-resolved · finding [fixed] · resolves sr-r1-10: Slug and issue-close rendering do not exist in the forge adapter

§D uses resolve_identity and states how URLs normalise; §E widens hostclient's command table with issue-close/unlabel/label per backend and a manual line where tea lacks one.

<!-- fr:journal kind=finding scope=spec id=sr-r1-11-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-11 -->
### sr-r1-11-resolved · finding [fixed] · resolves sr-r1-11: Walk model has no detection source

R9/§C: --model is required on walk; the harness comes from detect_harness or --harness.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-12 -->
### sr-r1-12-resolved · finding [fixed] · resolves sr-r1-12: candidate-install omits the runner packages

§I: super-fr's contract mirrors install.sh's --with set for both source forms.

<!-- fr:journal kind=finding scope=spec id=sr-r1-13-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-13 -->
### sr-r1-13-resolved · finding [fixed] · resolves sr-r1-13: R22 conflict counting is ambiguous

R22/§G: at most 2 hand-backs per dispatch (session|fresh events since the latest dispatch); held events never count; needs-you clears on merge, cancel or a new dispatch; the message target is the latest fresh item, else the dispatch item.

<!-- fr:journal kind=finding scope=spec id=sr-r1-14-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-14 -->
### sr-r1-14-resolved · finding [fixed] · resolves sr-r1-14: A blocked session may get the brief; R23 says capability

R20/§G: message only an idle session; working or blocked waits for a later pass; R23/§G call it an optional protocol, not a CAPABILITIES entry.

<!-- fr:journal kind=finding scope=spec id=sr-r1-15-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-15 -->
### sr-r1-15-resolved · finding [fixed] · resolves sr-r1-15: R7 and §B precedence differ; row-level verify has no reason source

R7 matches §B (verify, override, strategy, shape); a spec line may give a reason for a matrix-level verify; the PR body prints 'no reason recorded (legacy)'; self-review refuses a run row without a reason.

<!-- fr:journal kind=finding scope=spec id=sr-r1-16-resolved created=2026-10-06T11:14:23+00:00 state=fixed resolves=sr-r1-16 -->
### sr-r1-16-resolved · finding [fixed] · resolves sr-r1-16: Test Plan reserved for post-merge while this spec's Test Plan is pre-merge

§I restated: the Test Plan lists post-merge rows with reasons, pre-merge walks live in ## Verification; this spec's Test Plan follows that.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p2 created=2026-10-06T11:17:05+00:00 -->
### phase-split-2026-10-06-verification-strategies-p2 · decision · ask: matrix/record shape changes and walk recording (R7, R13, R14, R16) reviewed apart from the vocabulary

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p3 created=2026-10-06T11:17:06+00:00 -->
### phase-split-2026-10-06-verification-strategies-p3 · decision · ask: the walk and deliver gates (R9, R11, R12, R15)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p4 created=2026-10-06T11:17:06+00:00 -->
### phase-split-2026-10-06-verification-strategies-p4 · decision · ask: awaiting-live label and triage set (R17, R18), #822's backlog half

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p5 created=2026-10-06T11:17:07+00:00 -->
### phase-split-2026-10-06-verification-strategies-p5 · decision · ask: drive conflict hand-back (R19-R23), #959

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p6 created=2026-10-06T11:17:08+00:00 -->
### phase-split-2026-10-06-verification-strategies-p6 · decision · ask: on-demand pre-release (R24)

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-verification-strategies-p7 created=2026-10-06T11:17:09+00:00 -->
### phase-split-2026-10-06-verification-strategies-p7 · decision · ask: dogfood install contract and scenarios (R25) plus skills and docs

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-06-verification-strategies-p2 created=2026-10-06T11:17:10+00:00 -->
### tier-2026-10-06-verification-strategies-p2 · decision · hard: two artifact shape changes with a body-rewriting migration and frozen readers every caller relies on

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-06-verification-strategies-p5 created=2026-10-06T11:17:11+00:00 -->
### tier-2026-10-06-verification-strategies-p5 · decision · hard: changes the drive executor's merge-stop path and adds persisted event semantics every batch passes through
