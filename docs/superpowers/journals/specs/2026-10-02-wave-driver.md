# Journal: 2026-10-02-wave-driver

<!-- fr:journal kind=discovery scope=spec id=wave-driver-brief created=2026-10-02T17:48:22+00:00 -->
### wave-driver-brief · discovery · Operator brief: make the wave-driving and report-page work fr verbs and skills

Operator, verbatim (2026-10-02): "so, remind me, are these 3 artifacts already created via a super-fr skill or are they adhoc? Also, what about the dispatching? What about the monitoring and merging when PRs are mergeable (green CI and not draft)?" — answered: the triage board is fr triage render output patched by hand; the architecture and defect-origins pages are hand-built HTML; the scheduling (4 in flight, dependencies, wave order, merge when ready and green, close-out launch) is an ad-hoc script. Operator: "good, yes, let's make everything skills and/or fr verbs." Answers to the scoping questions: scope = all three parts (driver, board section, skills for the architecture and defect-origins pages); verb = fr triage batch drive with a loop and --once; close-out started through the runner; waves and dependencies as fields on each batch.

<!-- fr:journal kind=decision scope=spec id=scope-all-three created=2026-10-02T18:54:04+00:00 -->
### scope-all-three · decision · One spec for the driver, the board views and the page skills

Operator: the three parts fit together, so one spec.

<!-- fr:journal kind=decision scope=spec id=verb-drive-loop-once created=2026-10-02T18:54:04+00:00 -->
### verb-drive-loop-once · decision · fr triage batch drive, a loop with --once

Operator chose the foreground loop plus a single-pass --once over a single-pass-only verb or a daemon.

<!-- fr:journal kind=decision scope=spec id=closeout-through-runner created=2026-10-02T18:54:04+00:00 -->
### closeout-through-runner · decision · Close-out starts through the runner

Operator chose a runner work item (unit run, payload kind closeout) over printing the command or running the steps in-process.

<!-- fr:journal kind=decision scope=spec id=waves-as-batch-fields created=2026-10-02T18:54:04+00:00 -->
### waves-as-batch-fields · decision · wave and after are fields on each batch

Operator chose fields on Batch (judgements schema 3) over a separate plan file; the in-flight cap is a drive flag.

<!-- fr:journal kind=decision scope=spec id=post-merge-config created=2026-10-02T18:54:04+00:00 -->
### post-merge-config · decision · The host install is a per-repo post_merge command

Raised by the operator: without install.sh the harnesses on the host run a stale fr. The driver runs a post_merge command from .fr/triage.yaml once per merge, before the close-out.

<!-- fr:journal kind=decision scope=spec id=scope-groups-and-views created=2026-10-02T18:54:04+00:00 -->
### scope-groups-and-views · decision · Comma-separated repo groups; three new board views; nothing removed

Operator asked for a comma-separated repo list as one group, wave tabs with the latest preselected, and a reorganisation around what changed and what to do next. Operator: the same three artifacts, nothing removed, just reordered, plus three new views (Since last report, Needs you now, Next up).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-02T18:58:38+00:00 -->
### spec-review-1 · review · independent spec review: 14 findings (12 in scope, 2 out of scope)

All 7 recorded decisions are honoured. The review checked the spec against the codebase (merge_one, batch dispatch, herdr runner, facts and judgements schemas, closeout.py), against itself, and the acceptance rows. Findings sr-1 to sr-14; every in-scope one is fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · The pass reads stale facts; nothing in the design re-collects each pass

derive_batch_stage reads facts.json, written only by collect; the spec never says a pass re-collects (batch.py:163-179, model.py:276-298).

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · merge_one is not blocking-free, and it can push to the PR branch

merge_one blocks in wait_required_checks and pushes an update when behind its base or off its version slot (batch_merge.py:185-236); R4's 'never waits' cannot be met by it. Check vocabulary also differs from facts.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · 'Existing dispatch/merge path' is inline in Typer commands; per-repo checkouts unspecified

batch dispatch and merge bodies are inline (triage_batch_cmd.py:764-1016); --checkout is one path; R15 groups repos.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Where a goal batch's run id for fr pickup comes from is unspecified

Neither Batch nor DispatchEvent stores the run id (model.py:350-358); pickup --run needs it (pickup_cmd.py:59-92).

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The herdr agent_name and can_dispatch changes are unnecessary

agent_name's removeprefix is a no-op for closeout-<id> and the hash already makes it unique; can_dispatch ignores payload.kind (runner.py:82-88,131); payload.model and checkout still need a source.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · closed-out contradicts 'stage derivation unchanged'; partial is an unhandled dependency state

Design says derivation is unchanged yet derives closed-out; a merged PR with open members derives partial, which is neither satisfiable nor unsatisfiable (batch.py:43-57,163-179).

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · Definition of 'unplaced' differs between R9/R18 and Design D

R9 flags every open unplaced issue; Design D only those with a kind.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · post_merge 'once per merge' conflicts with 'no driver state' and has no crash-safe record

A kill between post_merge and the closeout event repeats the command; trust boundary of a host command from .fr/triage.yaml; TriageConfig is extra=forbid (check_config_fresh, batch_dispatch.py:128).

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · Schema rules for judgements schema 3 and the facts schema change for R15 are unspecified

schema_ is Literal[1,2], JUDGEMENTS_SCHEMA is 2, save_batches stamps it (model.py:36-40,437,490); R15 needs a third ScopeKind and facts schema 4 (Facts is extra=forbid).

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · One spec carries three independent deliverables of very different size

The Design spans driver, runner contract, judgement model, origins, architecture, snapshots, tabs, groups and page reordering; delivery order must be fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Requirements without Test Plan coverage

R2's --yes gate, R13, R12's gutter and theme variant, R18's six kinds, R17's retention and corrupt snapshot, R20's orderings, the clock seam and the exit-code vocabulary.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-02T18:58:38+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Archive-PR lookup and the close-out's end are left to guess

Real heads are chore/archive-<plan>, chore/closeout-<run-id>, chore/closeout-<branch-slug> (closeout.py:169-178); 'naming the batch' matches only the last.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-02T18:58:38+00:00 state=open review_scope=out -->
### sr-13 · finding [open] (reviewer: out of scope) · The herdr runner dispatches only inside a herdr session; the loop inherits this

preflight needs HERDR_ENV=1 and HERDR_WORKSPACE_ID (runner.py:106-116); pre-existing.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-02T18:58:38+00:00 state=open review_scope=out -->
### sr-14 · finding [open] (reviewer: out of scope) · Verified-correct claims: soft point, single-repo --repo today, no schema clash

triage_batch_cmd.py is the _SOFT_POINTS entry; --repo takes one OWNER/REPO (triage_cmd.py:67-90); git and process starts belong to seam/command modules.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: The pass reads stale facts; nothing in the design re-collects each pass

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: merge_one is not blocking-free, and it can push to the PR branch

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: 'Existing dispatch/merge path' is inline in Typer commands; per-repo checkouts unspecified

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Where a goal batch's run id for fr pickup comes from is unspecified

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The herdr agent_name and can_dispatch changes are unnecessary

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: closed-out contradicts 'stage derivation unchanged'; partial is an unhandled dependency state

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: Definition of 'unplaced' differs between R9/R18 and Design D

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: post_merge 'once per merge' conflicts with 'no driver state' and has no crash-safe record

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: Schema rules for judgements schema 3 and the facts schema change for R15 are unspecified

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: One spec carries three independent deliverables of very different size

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Requirements without Test Plan coverage

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-02T18:58:38+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Archive-PR lookup and the close-out's end are left to guess

Fixed in the spec (revision committed after the review).

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-02T18:58:38+00:00 state=open resolves=sr-13 out_of_scope=true -->
### sr-13-resolved · finding [out-of-scope] · resolves sr-13: The herdr runner dispatches only inside a herdr session; the loop inherits this

True, but not caused by this change.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-02T18:58:38+00:00 state=open resolves=sr-14 out_of_scope=true -->
### sr-14-resolved · finding [out-of-scope] · resolves sr-14: Verified-correct claims: soft point, single-repo --repo today, no schema clash

Informational; no change needed.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-wave-driver-p2 created=2026-10-02T19:00:19+00:00 -->
### phase-split-2026-10-02-wave-driver-p2 · decision · ask: the driver is its own ask (R2-R8, R13, R14) after the schema ask of phase 1

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-wave-driver-p3 created=2026-10-02T19:00:19+00:00 -->
### phase-split-2026-10-02-wave-driver-p3 · decision · ask: repo groups are their own ask (R15); they change collect and Facts, so they land before any view

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-wave-driver-p4 created=2026-10-02T19:00:20+00:00 -->
### phase-split-2026-10-02-wave-driver-p4 · decision · ask: the decision views are their own ask (R9, R16-R20) and reuse the driver's pure functions

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-wave-driver-p5 created=2026-10-02T19:00:21+00:00 -->
### phase-split-2026-10-02-wave-driver-p5 · decision · ask: defect origins is its own ask (R10): a new engine, verbs and skill

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-wave-driver-p6 created=2026-10-02T19:00:22+00:00 -->
### phase-split-2026-10-02-wave-driver-p6 · decision · ask: the architecture page is its own ask (R11, R12) and reuses the snapshots and tabs

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-02-wave-driver-p2 created=2026-10-02T19:00:22+00:00 -->
### tier-2026-10-02-wave-driver-p2 · decision · hard: the driver changes the merge and dispatch path every batch relies on, and adds an unattended loop that merges PRs
