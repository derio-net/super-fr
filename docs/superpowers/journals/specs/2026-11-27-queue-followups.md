<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-queue-followups

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-27T14:26:16+00:00 input=true -->
### brief · discovery · Operator brief (batch dispatch), verbatim

/fr-goal batch queue-followups

Batch `queue-followups` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

> Batch title: Queue follow-ups: approval revive, conflict probe, close-out wait, case-insensitive repo names
>
> #### super-fr#1680
> Queue: a re-added approved-fr revives the stale approval and is voided at once (label removed without a recorded void)
> `_live_index` (`packages/fr/src/fr/triage/approval.py:138`) treats an approval with no `voided_at` as live even when the label was removed, so a re-added `approved-fr` is judged against the old head's patch-id and voided at once; fr also removes labels without a recorded void or reason.
> Note: Batches with #1702 and #1677 (queue approval and merge path).
>
> #### super-fr#1676
> The early conflict probe resolves only version and lock files, so a stamp or generated conflict outside a queue slot still costs a hand-back
> `batch_merge.trial_conflicts` (`packages/fr/src/fr/triage/batch_merge.py:236`) resolves only version and lock files; it does not call `regen.classify_conflicts` with the repo's mirrors and generated globs, so those conflicts outside a queue slot still cost a hand-back.
> Note: Batches with #1677 (hand-back avoidance).
>
> #### super-fr#1663
> Queue: a wave's close-out always waits out the 10-minute release fallback, and quiet passes delay it further
> `closeout_due` (`packages/fr/src/fr/triage/batch_drive.py:706`) is due only on `released` or after `CLOSEOUT_FALLBACK` (`:71`, 10 min), and the queue hold keeps `released` false, so every queued wave pays the fallback; quiet passes add delay.
> Note: batches with #1667 (triage-drive)
>
> #### super-fr#1695
> overlaps() compares repo names case-sensitively
> `overlaps` (`packages/fr/src/fr/triage/plan_overlap.py:195`) compares `a.repo != b.repo` as exact strings, so two spellings of one repo would not overlap; it relies on `batch_repo`'s single spelling.
> Note: Follow-up to #1694 (shipped today): batch with the queue fixes, a few characters plus a test.
>
> #### Why these belong together
> All in queue_exec/batch_drive; lands after #1688 and landing-method.

Delivery rules: branch `feat/batch-queue-followups`; draft PR as soon as the spec is committed, body with one `Closes derio-net/super-fr#<n>` line per member (1680, 1676, 1663, 1695); batch `closeout-state` also changes triage_batch_cmd.py and batch_drive.py (second to land resolves the hand-back); no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=q1-conflicting-head-approval created=2026-11-27T14:26:16+00:00 decided_by=operator -->
### q1-conflicting-head-approval · decision · A label on a conflicting head is held unrecorded until a conflict-free head

Q: #1680 ask 2 — the operator labels approved-fr while the PR head conflicts.
Answer (operator): "the approved-fr is applied to the delivered work. A head conflict must be repaired by a competent agent but it shouldn't need to be approved again. So I'd tend towards 2" — option 2, hold unrecorded.
Spec R2: Held, label kept, nothing recorded, recorded as First at the first non-conflicting head; a live approval keeps R12's void rules (recorded in the spec's Out of scope).

<!-- fr:journal kind=decision scope=spec id=q2-void-comment created=2026-11-27T14:26:16+00:00 decided_by=operator -->
### q2-void-comment · decision · A void posts one new marked PR comment per voided head

Q: #1680 ask 3 — where fr says why it removed approved-fr. Answer (operator): New comment (recommended). Spec R3.

<!-- fr:journal kind=decision scope=spec id=q3-ended-approval-schema created=2026-11-27T14:26:16+00:00 decided_by=operator -->
### q3-ended-approval-schema · decision · An ended approval is recorded in the existing judgements schema

Q: #1680 ask 1 — how a label-gone approval is ended. Answer (operator): existing schema, voided_at at the live head, reason only in drive output; no judgements schema bump. Spec R1.

<!-- fr:journal kind=decision scope=spec id=q4-verification created=2026-11-27T14:26:16+00:00 decided_by=operator -->
### q4-verification · decision · strategy none, gate developer, one acceptance row per issue at ci

Q: verification. Answer (operator): strategy none, gate developer, settle report lines; one acceptance row per issue proven by this PR's unit tests; no Test Plan. Spec ## Verification.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-27T14:26:16+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · R2 changes when an operator approval is recorded; R3 posts PR comments

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T14:26:16+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · every requirement is proven only by unit tests (strategy none)

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · R2 + R4 together leave a labelled PR with only queue-resolvable conflicts held forever

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · R1's ended event renders as a push-void and the board asks for a re-label

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · R2's Held renders as 'held unreadable' and the board asks to label an already-labelled PR

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · R3's forge.comments read cites the wrong source

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · R5 names queue_landed(snap, repo) and landed_keys wrongly

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R5 also moves post_merge for queued batches, unstated

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · R6 holds only for not-due members; other skipped members still split the wave, and a blocked wave has no Need

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R7 needs pacing.py; planned_at's fail-open unspecified against pacing_state's parser

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R7 has no rule for a landed batch with no merged_at

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · R4 claims 'exactly' the queue's refusals

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · R2's UNKNOWN does not hold leaves the #1680 window open

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-27T14:35:52+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Five rows for four issues, against q4's one row per issue

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T14:35:52+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings, all in scope, all fixed in the spec

Dispatched fr-spec-reviewer checked the spec against q1-q4 and the named code (approval, batch_merge, regen, queue_exec, batch_drive, probe, pacing, pacing_state, plan_overlap, mergeability, queue_comment, wave_queue, readiness, views, operator_entries, triage_batch_cmd) with file:line evidence. Main risk sr-1 (R2+R4 deadlock). It verified the R4 stage swap is correct. Findings sr-1..sr-12 raised.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T14:35:52+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · R3 fail-soft comment, R7 fail-open pacing and R2's UNKNOWN handling are new error-path decisions

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: R2 + R4 together leave a labelled PR with only queue-resolvable conflicts held forever

R2 now waits only while a ConflictEvent the probe recorded names the live head (a conflict the queue cannot resolve); a queue-resolvable conflict is recorded First and the queue's build resolves it.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: R1's ended event renders as a push-void and the board asks for a re-label

R1 states an ended approval is no fr removal (no facts rewrite, no comment); Design splits board/readiness wording on voided_at == approved head; the voided set counts only fr's removals.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: R2's Held renders as 'held unreadable' and the board asks to label an already-labelled PR

R2 uses a new Waiting verdict with its own readiness fact; the approve-pr Need skips it; said once per head, not a warning.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: R3's forge.comments read cites the wrong source

Design names _comments_off beside _labels_off in approval.py (client_policy(...).block('comments'), unreadable blocks), re-exported by operator_entries; R3 says an unreadable policy posts nothing.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: R5 names queue_landed(snap, repo) and landed_keys wrongly

Design uses wave_queue.queue_landed over the repo's records for both the pass and the command's due list; landed_keys dropped.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R5 also moves post_merge for queued batches, unstated

R5 states the post_merge action shares the due value and that this is intended (the hold blocks a release; the landing normally runs post_merge itself).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: R6 holds only for not-due members; other skipped members still split the wave, and a blocked wave has no Need

R6 names the blocking members (not due, unverified, ledger-unread), the ones that do not block (verb-held, unselected), and emits a held action naming them.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R7 needs pacing.py; planned_at's fail-open unspecified against pacing_state's parser

pacing.py added to Design and shape; planned_at joins _TIMES and is parsed on its own so a bad value is None without resetting the state.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R7 has no rule for a landed batch with no merged_at

R7: a landed batch with no readable merged_at reads its repo (fail open); queue-landed batches have no deadline (R5).

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: R4 claims 'exactly' the queue's refusals

R4 reworded to the queue's classification for a merge onto the default branch, and names what it does not model.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: R2's UNKNOWN does not hold leaves the #1680 window open

R2 states the trade-off (a label read before mergeability is computed or the probe ran is recorded as today).

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-27T14:35:52+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Five rows for four issues, against q4's one row per issue

queue-approval-waits-conflict-free retired into queue-approval-label-lifecycle, which now cites R1-R3; spec Verification updated.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T14:35:54+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  conflict-probe-matches-queue-resolution: none
  queue-approval-label-lifecycle: none
  queue-closeout-due-at-landing: none
  wave-overlap-repo-case: none
row_kinds:
  conflict-probe-matches-queue-resolution: none
  queue-approval-label-lifecycle: none
  queue-closeout-due-at-landing: none
  wave-overlap-repo-case: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-queue-followups-p2 created=2026-11-27T14:38:23+00:00 -->
### phase-split-2026-11-27-queue-followups-p2 · decision · ask: #1680's approval lifecycle (R1-R3) is its own reviewable ask, separate from the driver timing and probe fixes
