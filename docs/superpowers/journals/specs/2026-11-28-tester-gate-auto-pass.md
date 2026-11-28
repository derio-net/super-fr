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
