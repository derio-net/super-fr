<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-plan-ops-split

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T09:07:31+00:00 input=true -->
### operator-brief · discovery · Batch arch-plan-ops-split: super-fr#1518, split self-review, the spec table and the refactor-gate read out of plan_ops.py

Batch `arch-plan-ops-split` of derio-net/super-fr, one issue, one PR.
#1518 "Split self-review, the spec table and the refactor-gate read out of plan_ops.py":
decomposition plan from the #1318 review (section 5.4); P3 refactor, no behaviour change.
Slices: (1) `_refactor_justifications` with `_TASK_ID_RE` to `fr/record/gates.py`;
(2) lint vocabulary, `self_review` and sub-checks to `fr/plan/review/`, re-exporting
`self_review`, `ReviewIssue`, `_trailing_manual_block`, `_manual_placement_issues`, and
merging the two journal reads into one helper; (3) `PlanEditError` to a leaf
`fr/plan_errors.py`, then the spec "Implementation Plans" table to `fr/spec_table.py`;
(4) rework after the plumbing moves to a private I/O module (a test patches
`plan_ops.space_for`). Excluded: the raw write_text calls (#1524); retiring
tick/complete_phase. Preserved: every public name importable from fr.plan_ops;
self-review's issues and their order unchanged. Lower the budget; slice 2 edits
docs/explainers/01-fr-goal.md. Delivery: branch feat/batch-arch-plan-ops-split,
draft PR with `Closes derio-net/super-fr#1518`, no member issue as a tracking_issue,
no `fr pr settle` loop (the wave driver owns it), never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=scope-slices created=2026-11-27T09:07:31+00:00 decided_by=operator -->
### scope-slices · decision · Scope: slices 1-4 of #1518 in this one PR

Operator chose slices 1-4 (refactor-gate read, self-review, spec table, rework with its plumbing move) over 1-3.

<!-- fr:journal kind=decision scope=spec id=review-home created=2026-11-27T09:07:31+00:00 decided_by=operator -->
### review-home · decision · Self-review goes to a new fr/plan_review/ package

Not fr/plan/review/: fr/plan/ is the legacy v1 reader slated for deletion. Package split into several modules.

<!-- fr:journal kind=decision scope=spec id=private-imports created=2026-11-27T09:07:31+00:00 decided_by=operator -->
### private-imports · decision · Tests and src callers import moved private names from their new homes

plan_ops re-exports public names plus _trailing_manual_block and _manual_placement_issues only.

<!-- fr:journal kind=decision scope=spec id=verification created=2026-11-27T09:07:31+00:00 decided_by=operator -->
### verification · decision · Verification: strategy none, suite only, no acceptance rows, gate developer

A no-behaviour refactor: the unchanged suite in CI is the evidence. No Test Plan.

<!-- fr:journal kind=finding scope=spec id=s-r1-1 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-1 · finding [open] (reviewer: in scope) · OPS_FR_FLOOR is a public plan_ops name but is missing from the re-export list

R9 omitted OPS_FR_FLOOR (plan_ops.py:1865), imported by tests/unit/test_ops_artifacts.py:33.

<!-- fr:journal kind=finding scope=spec id=s-r1-2 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-2 · finding [open] (reviewer: in scope) · R10 caller list misses apply_cmd.py and undispatch_cmd.py (PlanEditError) and stale docstrings

apply_cmd.py:47, undispatch_cmd.py:32 import PlanEditError; docstrings run_cmd.py:798, :5123, cli.py:7 name old paths.

<!-- fr:journal kind=finding scope=spec id=s-r1-3 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-3 · finding [open] (reviewer: in scope) · The plain write_text guard covers only plan_ops.py, so moving writers out narrows it

test_run_durability.py:105 parametrizes plan_ops.py and run/model.py only.

<!-- fr:journal kind=finding scope=spec id=s-r1-4 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-4 · finding [open] (reviewer: in scope) · R14 ignores pages whose covers match the edited caller files

Pages covering plan_cmd.py, run_cmd.py, apply_cmd.py, undispatch_cmd.py and fr-dispatch src will be reported by fr docs check.

<!-- fr:journal kind=finding scope=spec id=s-r1-5 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-5 · finding [open] (reviewer: in scope) · Background's 'raw write_text calls stay raw' does not match plan_ops.py, which has none

Every plan_ops write is write_text_atomic; the raw write in scope is migrate.py:761.

<!-- fr:journal kind=finding scope=spec id=s-r1-6 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-6 · finding [open] (reviewer: in scope) · _scan is a nested function of _next_rework_number

_scan is a closure at plan_ops.py:840.

<!-- fr:journal kind=finding scope=spec id=s-r1-7 created=2026-11-27T09:13:33+00:00 state=open review_scope=in -->
### s-r1-7 · finding [open] (reviewer: in scope) · The design shape and import picture leave out edges and files

Missing migrate/plan_cmd/apply_cmd/undispatch_cmd/fr_dispatch edges, duplicated gates.py, missing change fragment.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-11-27T09:13:33+00:00 -->
### spec-review-r1 · review · independent spec review: 7 findings (s-r1-1..s-r1-7)

fr-spec-reviewer found 7 in-scope findings, all fixed in the spec. Decisions scope-slices, review-home, private-imports and verification checked as honoured.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T09:13:33+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · about 30 test imports and one patch move, and a write guard widens: check what still covers the moved writers

<!-- fr:journal kind=lens scope=spec id=lens-simplicity-1 created=2026-11-27T09:13:33+00:00 lens=simplicity step=spec-review -->
### lens-simplicity-1 · lens · a five-module split with re-exports: check no shim or helper is duplicated across homes

<!-- fr:journal kind=finding scope=spec id=s-r1-1-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-1 -->
### s-r1-1-resolved · finding [fixed] · resolves s-r1-1: OPS_FR_FLOOR is a public plan_ops name but is missing from the re-export list

R9 now lists the full public set, OPS_FR_FLOOR included; plan_ops and plan_review/__init__ re-export it.

<!-- fr:journal kind=finding scope=spec id=s-r1-2-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-2 -->
### s-r1-2-resolved · finding [fixed] · resolves s-r1-2: R10 caller list misses apply_cmd.py and undispatch_cmd.py (PlanEditError) and stale docstrings

Callers paragraph names both files (module import kept for the set_tracking_issue patch); R10 covers docstrings and names the three.

<!-- fr:journal kind=finding scope=spec id=s-r1-3-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-3 -->
### s-r1-3-resolved · finding [fixed] · resolves s-r1-3: The plain write_text guard covers only plan_ops.py, so moving writers out narrows it

R11 widens the parameter list to _plan_io.py, spec_table.py and plan_rework.py; design shape names the test.

<!-- fr:journal kind=finding scope=spec id=s-r1-4-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-4 -->
### s-r1-4-resolved · finding [fixed] · resolves s-r1-4: R14 ignores pages whose covers match the edited caller files

R14 now owes a reviewed-stamp move (import-only change) for every page fr docs check reports.

<!-- fr:journal kind=finding scope=spec id=s-r1-5-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-5 -->
### s-r1-5-resolved · finding [fixed] · resolves s-r1-5: Background's 'raw write_text calls stay raw' does not match plan_ops.py, which has none

Background now states plan_ops has no raw write and names migrate.py:761 as the one that stays raw.

<!-- fr:journal kind=finding scope=spec id=s-r1-6-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-6 -->
### s-r1-6-resolved · finding [fixed] · resolves s-r1-6: _scan is a nested function of _next_rework_number

Move list now says _scan moves with _next_rework_number; 'other private rework helpers' dropped.

<!-- fr:journal kind=finding scope=spec id=s-r1-7-resolved created=2026-11-27T09:13:33+00:00 state=fixed resolves=s-r1-7 -->
### s-r1-7-resolved · finding [fixed] · resolves s-r1-7: The design shape and import picture leave out edges and files

Picture and tree updated; R15 adds the change fragment.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T09:13:35+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates: {}
row_kinds: {}
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-plan-ops-split-p1 created=2026-11-27T09:15:47+00:00 -->
### phase-split-2026-11-27-plan-ops-split-p1 · decision · tier: the plan's one standard-tier phase; the spec carries no acceptance rows (operator decision 'verification': a no-behaviour refactor), so no row can name its ask

R1-R15 are all served by this single phase.
