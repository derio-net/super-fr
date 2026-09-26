# Journal: 2026-09-26-one-phase-plans

<!-- fr:journal kind=decision scope=spec id=gate-on-two-agentic-phases created=2026-09-26T11:23:25 -->
### gate-on-two-agentic-phases · decision · Skeleton rule applies only with 2+ agentic phases

One agentic phase has no later part for a skeleton to protect, so both the unmarked and sole-marked errors drop; the misplaced-marker error and the override stay for 2+. Manual phases do not count. A marker on a sole phase is still accepted and still floor-probed.

<!-- fr:journal kind=decision scope=spec id=fold-662 created=2026-09-26T11:23:25 -->
### fold-662 · decision · Fold gh#662 into this batch

It is one assertion (spec bytes unchanged after the no-table pre-flight raises) in the same plan_ops tests.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T11:23:25 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Operator's batch brief fixed every decision (gate on 2+ agentic phases, rewrite fr-plan/fr-goal prose, both mirrors, one agentic phase, fold #662 only if one assertion, override authorized for this plan); no operator-owned choice remained.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T11:25:04 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Spec never says the sole-skeleton override test is retired

check: consistency. tests/unit/test_v2_plan_ops.py:1655 becomes vacuous; :601 name is stale. State in spec.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T11:25:04 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Docstring and comment surfaces describing the old rule are not in Scope

check: consistency. plan_ops.py _skeleton_issues docstring, skeleton_override.py docstring, test_run_cli.py comments.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T11:25:04 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Matrix row to retire is described vaguely; line-anchored refs go stale

check: consistency. Row plan-skeleton-is-not-the-whole-plan, refs L1554/L1567.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T11:25:04 state=open review_scope=out -->
### s4 · finding [open] (reviewer: out of scope) · plan_cmd.py help text still says marker is for the first agentic phase

check: codebase. plan_cmd.py:153; wording stays accurate for 2+ phase plans.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T11:25:04 -->
### spec-review · review · independent spec review: 4 findings

Decisions honoured; every named file/helper verified with file:line; 3 in scope (fixed in spec), 1 out of scope.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T11:25:04 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Spec never says the sole-skeleton override test is retired

Spec §3 items 2-3 now name the retired and renamed tests.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T11:25:04 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Docstring and comment surfaces describing the old rule are not in Scope

Spec §2.D and §4 list the docstring/comment surfaces.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T11:25:04 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Matrix row to retire is described vaguely; line-anchored refs go stale

Spec §4 names the row id and the set-status --drop-level re-pointing.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T11:25:04 state=open resolves=s4 out_of_scope=true -->
### s4-resolved · finding [out-of-scope] · resolves s4: plan_cmd.py help text still says marker is for the first agentic phase

Wording remains accurate for 2+ agentic phases; this change did not make it wrong.
