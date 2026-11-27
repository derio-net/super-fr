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
