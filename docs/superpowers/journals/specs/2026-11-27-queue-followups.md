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
