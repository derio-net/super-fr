<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-tester-gate-auto-pass

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-28T11:47:16+00:00 input=true -->
### operator-brief · discovery · Batch tester-gate-auto-pass brief (super-fr#1764)

Batch title: Pass a tester gate whose rows are walked, for PRs outside a batch

super-fr#1764 — triage: a gate-labelled PR outside a batch stays in Needs you · Tester after its rows are walked.
A merged `gate:tester` PR outside any batch reaches the board through `gated_pr_lane` (`lanes.py:68`), which reads labels only; the rows-walked auto-pass (`_gate_actions`, `batch_drive.py:1222`) runs only over a batch's ledger. So walked rows never move the card, and the hint (`lanes.py:83`) names a remedy that cannot work for it.
Note: Operator priority 2026-11-28: clears the Needs you · Tester column.
Why these belong together: Operator priority: most Needs you · Tester cards are non-batch PRs whose rows are already walked.

<!-- fr:journal kind=decision scope=spec id=q1-pass-route created=2026-11-28T11:47:16+00:00 decided_by=operator -->
### q1-pass-route · decision · The wave driver's pass is the route for non-batch PRs

Operator chose: each drive pass reads the rows of every non-batch gated PR via gated_rows_at keyed on head_ref and plans the same gate-pass. Not set-status --walk.

<!-- fr:journal kind=decision scope=spec id=q2-selection created=2026-11-28T11:47:16+00:00 decided_by=operator -->
### q2-selection · decision · Whole-scope drives only

Operator chose: a drive narrowed with --batch plans nothing for non-batch PRs.

<!-- fr:journal kind=decision scope=spec id=q3-awaiting-live created=2026-11-28T11:47:16+00:00 decided_by=operator -->
### q3-awaiting-live · decision · Label row issues fr:awaiting-live, same as batches

Operator chose: share _gate_actions so a non-batch PR's row issues get fr:awaiting-live too.

<!-- fr:journal kind=decision scope=spec id=q4-verification created=2026-11-28T11:47:16+00:00 decided_by=operator -->
### q4-verification · decision · candidate strategy, gate developer, no Test Plan

Operator chose: candidate walk plus CI unit tests per row; gate developer so the merge holds nothing.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Closed-out batches' gated PRs fall through both routes; the spec's 'keeps going through its batch' is false

batch_drive.py:1484 skips a batch with a close-out before is_gated; _ledgers skips it too (triage_batch_cmd.py:4783); lanes.unlisted_gated_prs lists its PR outside its batch. loose_prs must take it.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Matching a run cursor on head_ref alone can pass a gate with another run's walked rows

find_run (batch_drive.py:817) takes the first cursor whose branch matches; RunState.pr (run/model.py:397) records the PR url. Require it to name this PR when set; >1 cursor is unreadable.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Design shape and Design disagree on the LooseLedger shape and on how gate_actions can set Action.repo

Shape returned 2-tuples, Design a 3-field LooseLedger; gate_actions had no repo argument.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · pr_gates <-> batch_drive import cycle: GateLedger lives in batch_drive.py

GatedRow/GateLedger at batch_drive.py:166/177; pr_gates must not import batch_drive, which calls it.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · _gated_rows takes a Batch; the spec says loose PRs reuse it unchanged

triage_batch_cmd.py:4798 derives the branch from recorded_branch(batch) and names batch.id in its warning.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · R5 says 'reported once per pass'; the reused reporter reports once per drive

_report_once (triage_batch_cmd.py:5503) keys self.warned, which persists across passes.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · R2's guards have no acceptance row or named test for loose PRs

batch_drive.py:1239-1244 guards; no row covered them on the new route.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-28T11:53:01+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · The board hint stays false for gated PRs with no run cursor

lanes.py:82-84 still says 'walk its gated rows' for a gated PR no fr run delivered; the spec left it implied.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-28T11:53:01+00:00 -->
### spec-review · review · independent spec review (fr-spec-reviewer): 8 findings

Verified every named file:line (lanes.py:33/68/83/91, batch_drive.py:136/177/222/240/254/1222/1410/1479/1533, batch_drive_types.py:105, ledger.py:60/104, triage_batch_cmd.py:4762/4798/6051/6162/6180, gate_cmd.py:303, test_tripwire_module_budget.py:33/40, model.py:834, run/model.py:397). Decisions q1-q4 honoured. Findings s1-s8.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-28T11:53:01+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · a new automated path swaps gate labels on merged PRs no batch delivered, matched by branch and cursor (s2)

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-28T11:53:01+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R2's no-pass guards, the cursor-mismatch refusal and the closed-out-batch case need explicit negative tests on the new route

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Closed-out batches' gated PRs fall through both routes; the spec's 'keeps going through its batch' is false

R1 now defines a loose PR as any gated PR not the merged PR of a batch without a close-out event; new R8 and row closed-out-batch-gated-pr-pass.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Matching a run cursor on head_ref alone can pass a gate with another run's walked rows

New R5: the cursor's recorded pr must name this PR when set; a cursor naming another PR is no rows; >1 cursor on the branch is unreadable. gated_rows_at gains pr; row 3 reworded to cover both.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Design shape and Design disagree on the LooseLedger shape and on how gate_actions can set Action.repo

One LooseLedger(repo, number, head_ref, ledger) in batch_drive_types.py; gate_actions(owner, repo, ledger, ...).

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: pr_gates <-> batch_drive import cycle: GateLedger lives in batch_drive.py

GatedRow/GateLedger move to batch_drive_types.py, re-exported from batch_drive; pr_gates imports only batch_drive_types and fr.labels.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: _gated_rows takes a Batch; the spec says loose PRs reuse it unchanged

_gated_rows(repo, branch, label, pr=None); the batch caller passes recorded_branch(batch); counted in the budget paragraph.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: R5 says 'reported once per pass'; the reused reporter reports once per drive

R6 now says 'reports it once, as it does for a batch'; the Design says once per drive process per read and error.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-28T11:53:01+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: R2's guards have no acceptance row or named test for loose PRs

New row loose-gated-pr-batch-guards (origin R2) with its own CI tests line in ## Verification.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-28T11:53:01+00:00 state=open resolves=s8 out_of_scope=true -->
### s8-resolved · finding [out-of-scope] · resolves s8: The board hint stays false for gated PRs with no run cursor

The hint on a gated PR no fr run delivered (gate-backfill adoptions, hand-labelled PRs) was wrong before this change and is not made worse by it; fixing it needs a new facts-level cursor signal. The spec now says so explicitly under 'What does not change', and deliver files it as a follow-up.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T11:53:11+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  closed-out-batch-gated-pr-pass: none
  loose-gated-pr-awaiting-live: none
  loose-gated-pr-batch-guards: none
  loose-gated-pr-no-pass-without-evidence: none
  loose-gated-pr-rows-walked-pass: none
row_kinds:
  closed-out-batch-gated-pr-pass: none
  loose-gated-pr-awaiting-live: none
  loose-gated-pr-batch-guards: none
  loose-gated-pr-no-pass-without-evidence: none
  loose-gated-pr-rows-walked-pass: none
run_gate: developer
run_kind: candidate
```
