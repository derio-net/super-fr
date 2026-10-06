# Journal: 2026-10-06-triage-dedupe

<!-- fr:journal kind=discovery scope=spec id=brief-971 created=2026-10-06T07:41:40+00:00 input=true -->
### brief-971 · discovery · Operator brief: batch triage-dedupe (super-fr#971), verbatim

/fr-goal Triage owns duplicates: a sweep proposes duplicate open issues, judgements record duplicate_of

Batch `triage-dedupe` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#971: Triage owns duplicates: a sweep that finds duplicate open issues and records them structurally
No sweep finds duplicate open issues; #781 (check before filing) was closed not planned because a run must not search the backlog. Triage owns it: candidates from the engine, judgement from the skill, `duplicate_of` in judgements.
Note: Operator 2026-10-05: finding duplicates is our responsibility.

## Why these belong together
Wave 4: operator 2026-10-05, finding duplicates is our job. After state-integrity: both touch the judgement model and keys.

## Delivery rules
- Work on branch `feat/batch-triage-dedupe`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#971
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-surface created=2026-10-06T07:41:40+00:00 -->
### q1-surface · decision · Sweep lives in check sets plus a board section; no new verb

Operator chose the recommended option: `check` gains `duplicate candidates` and `duplicates` sets, the board a Possible duplicates section. The refresh loop already runs check, so the sweep runs on every refresh.

<!-- fr:journal kind=decision scope=spec id=q2-dismissals created=2026-10-06T07:41:40+00:00 -->
### q2-dismissals · decision · Dismissals are per-issue distinct_from, read symmetrically

Operator chose `distinct_from: [keys]` on a judgement, beside `duplicate_of`.

<!-- fr:journal kind=decision scope=spec id=q3-board created=2026-10-06T07:41:40+00:00 -->
### q3-board · decision · A judged duplicate nests under its original on the board

Operator chose nesting: the duplicate leaves its tier and is never unplaced; a closed or missing original keeps it in its tier with a warning tag.

<!-- fr:journal kind=decision scope=spec id=q4-close-command created=2026-10-06T07:41:40+00:00 -->
### q4-close-command · decision · Print gh issue close --duplicate-of; no --yes executor

Operator chose printing GitHub's native duplicate close command and never running it; nothing in this change writes to the forge.

<!-- fr:journal kind=decision scope=spec id=q5-driver created=2026-10-06T07:41:40+00:00 -->
### q5-driver · decision · Driver reports candidates once when a wave finishes

Operator chose one warn line after a wave's close-out completes (spec §3.E makes it the pass whose archive merge finishes the wave, stateless).

<!-- fr:journal kind=decision scope=spec id=d-no-schema-bump created=2026-10-06T07:41:40+00:00 -->
### d-no-schema-bump · decision · duplicate_of/distinct_from are optional on every judgements schema

Follows the `kind`/`features` precedent (wave-driver R9): no engine verb writes them, and judgements.yaml is not an artifact kind.

<!-- fr:journal kind=decision scope=spec id=d-calibration created=2026-10-06T07:41:40+00:00 -->
### d-calibration · decision · Signal thresholds calibrated on this repo's 438 issues

Prototype recovered all three known duplicate groups (4 of 5 pairs directly, the fifth by connectivity) and flags 4 pairs among 61 open issues; spec §2.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · §3.E's warn Action names batch "wave-<w>", and the driver's _act exits on it

Spec reviewer finding sr-1; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · §3.E never fires when two batches of a wave archive in the same pass

Spec reviewer finding sr-2; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · §3.E's "never repeats" claim is false: the warn is planned before the archive merge runs

Spec reviewer finding sr-3; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · §3.E: a wave with a cancelled, abandoned, partial or unselected batch never counts as finished

Spec reviewer finding sr-4; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The warn line's `fr triage check` has no scope arguments

Spec reviewer finding sr-5; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · §3.D nests an already-closed duplicate under its original and prints a close command for it

Spec reviewer finding sr-6; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · A duplicate_of that names a PR, or a target added since the last collect, gets a misleading missing reason

Spec reviewer finding sr-7; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R6 adds unjudged keys to collect's view list; collect's unviewed report and the Unviewed docstring still say "judged"

Spec reviewer finding sr-8; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · §3.B title rule contradicts its own example: `p0`/`p1` are dropped, not kept

Spec reviewer finding sr-9; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · §3.B identifier exclusion "appears as a path or module segment anywhere in the scope" does not say which text

Spec reviewer finding sr-10; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · R5 and §3.C disagree on the --duplicate-of argument

Spec reviewer finding sr-11; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-06T07:47:32+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · R11 has no acceptance row, and the Test Plan does not exercise R3, R6 or R10

Spec reviewer finding sr-12; see the review entry spec-review-r1 for evidence.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-06T07:47:32+00:00 -->
### spec-review-r1 · review · Spec review of 2026-10-06-triage-dedupe-design

Independent fr-spec-reviewer checked the spec against brief-971 and decisions q1-q5, d-no-schema-bump, d-calibration (all honoured) and against the codebase (every cited file:line verified). Findings raised, all in scope: sr-1, sr-2, sr-3, sr-4, sr-5, sr-6, sr-7, sr-8, sr-9, sr-10, sr-11, sr-12. Driver trigger (sr-1..sr-5) redesigned as an observed wave transition with a dedicated `dedupe` action kind.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: §3.E's warn Action names batch "wave-<w>", and the driver's _act exits on it

New `dedupe` ActionKind with an empty batch; _act handles it before _find (spec §3.E).

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: §3.E never fires when two batches of a wave archive in the same pass

Trigger redefined as the observed unfinished→finished wave transition across passes (spec §3.E).

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: §3.E's "never repeats" claim is false: the warn is planned before the archive merge runs

No longer inferred from a planned archive action: it is based on observed is_finished across passes; --once/plan behaviour stated (spec §3.E).

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: §3.E: a wave with a cancelled, abandoned, partial or unselected batch never counts as finished

Wave members defined: not cancelled or abandoned, global regardless of selection; an empty wave is never finished (spec §3.E).

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The warn line's `fr triage check` has no scope arguments

Snapshot.dedupe_command carries the scope-qualified check command built by the command (spec §3.E, R10).

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: §3.D nests an already-closed duplicate under its original and prints a close command for it

Closed duplicate nested with a `closed` tag and no command (R8, §3.D).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: A duplicate_of that names a PR, or a target added since the last collect, gets a misleading missing reason

Missing-reason order: PR, unviewed, skipped, added-since-collect, not-collected (spec §3.C).

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R6 adds unjudged keys to collect's view list; collect's unviewed report and the Unviewed docstring still say "judged"

Spec §3.C states the view list is judged ∪ duplicate_targets and that the report and docstring are reworded.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: §3.B title rule contradicts its own example: `p0`/`p1` are dropped, not kept

Example corrected to the calibration's `…-0-agentic`/`…-1-agentic`.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: §3.B identifier exclusion "appears as a path or module segment anywhere in the scope" does not say which text

Text set and module-name extraction named exactly, matching the calibration (spec §3.B).

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: R5 and §3.C disagree on the --duplicate-of argument

R5 now says <original url>.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-06T07:47:32+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: R11 has no acceptance row, and the Test Plan does not exercise R3, R6 or R10

Added row triage-dedupe-skill (R11); Test Plan step 4 covers R6; R3/R10 stated unit-level.
