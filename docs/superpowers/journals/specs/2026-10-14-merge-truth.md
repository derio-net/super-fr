<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-merge-truth

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-13T22:53:06+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch merge-truth (verbatim)

/fr-goal Post-merge truth: stale labels and claims, stuck archive PRs, claim-take ordering

Batch `merge-truth` of derio-net/super-fr: 6 issues, delivered as ONE pull request.

## super-fr#1190: Post-merge truth: stale fr:in-progress, stuck archive PRs and claim-take ordering after a batch merges
206 closed issues still carry fr:in-progress (release() no-ops without a standing marker, claim_writes.py:236); a conflicting archive PR (#1146) stalls close-out for days; claim take writes the forge before claim_taken; #1123's retire→sync untested.

## super-fr#1172: drive: a ready archive PR found only by its close-out head is 'pending' forever, so it is never merged and nothing is printed
A ready archive PR found only by its close-out head reads 'pending' forever, so it is never merged; likely why archive PR #1146 is stuck.

## super-fr#1161: release-pending also covers an own claim a still-running batch owes
release-pending also covers an own claim that a still-running batch owes.

## super-fr#1160: Test gaps: claim_sync unlabel via one release, no untrusted-author closed-hit case, board note only as a function
Test gaps: claim_sync unlabel via one release, no untrusted-author closed-hit case, board note tested only as a function.

## super-fr#1176: a repo without origin/HEAD and an approved green PR aborts every pass at merge_ctx
A repo without origin/HEAD and an approved green PR aborts every pass at merge_ctx; likely already fixed by #1141's default_branch() fallback, to reconcile.

## super-fr#1178: host wait_out renewal retries a GraphQL visibility read every 60s inside the exhausted window until R12 lands
host wait_out renewal retries a GraphQL visibility read every 60s inside the exhausted window; quota-pacing's PR said nothing to file, so reconcile or fix.

## Why these belong together
Re-created from post-merge-truth with the claim/close-out follow-ups; #1172 is the likely cause of the stuck archive PR #1146; #1176/#1178 to reconcile.

## Delivery rules
- Work on branch `feat/batch-merge-truth`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1190
  Closes derio-net/super-fr#1172
  Closes derio-net/super-fr#1161
  Closes derio-net/super-fr#1160
  Closes derio-net/super-fr#1176
  Closes derio-net/super-fr#1178
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=q1-cleanup-reach created=2026-10-13T22:53:06+00:00 -->
### q1-cleanup-reach · decision · Driver cleans every stale closed issue in scope

Operator (round 1, Q1): every drive --yes pass (and claim sync --yes) unlabels every closed in-scope issue with no trusted un-released foreign claim — batch members and the stale backlog alike, so the 206 clear themselves; clean-labels stays the manual equivalent and also drops fr:claimed. Spec R1–R3.

<!-- fr:journal kind=decision scope=spec id=q2-release-at-close created=2026-10-13T22:53:06+00:00 -->
### q2-release-at-close · decision · A closed issue's own claim is released when it closes

Operator (round 1, Q2): claim sync releases and unlabels any own claim on a closed issue, owed or not; release-pending becomes true by construction (fixes #1161). Spec R1, R4.

<!-- fr:journal kind=decision scope=spec id=q3-conflict-handback created=2026-10-13T22:53:06+00:00 -->
### q3-conflict-handback · decision · Conflicting archive PR is handed back, then Needs you

Operator (round 1, Q3): detect via mergeable; hand to the batch's close-out session (message if idle, else fresh close-out item) as conflict_decision does for batch PRs; once hand-backs are spent, an archive-conflict Need and a recorded stop. Spec R12.

<!-- fr:journal kind=decision scope=spec id=q4-draft-archive-ready created=2026-10-13T22:53:06+00:00 -->
### q4-draft-archive-ready · decision · The driver marks a draft archive PR ready, then merges it

Operator (round 1, Q4) chose 'driver marks it ready', noting draft is not what ultimately decides a merge and asking whether a special label exists. Code check: the label is approved-fr and gates only batch PRs, where an approved draft is already enqueued (batch_drive.py:1038); archive PRs are gated by attribution, and `not p.draft` (batch_drive.py:1318) is the only reason a draft stalls. So: drop the draft term, pr_ready before pr_merge, no approved-fr. Spec R11.

<!-- fr:journal kind=decision scope=spec id=q5-take-record-first created=2026-10-13T22:53:06+00:00 -->
### q5-take-record-first · decision · claim take records claim_taken before writing the forge

Operator (round 1, Q5): append claim_taken first; a failed forge write leaves a recorded take the next sync re-claims, and take exits non-zero. Spec R5.

<!-- fr:journal kind=decision scope=spec id=q6-retire-updates-facts created=2026-10-13T22:53:06+00:00 -->
### q6-retire-updates-facts · decision · scope retire updates the stored facts in place

Operator (round 1, Q6): retire marks released claims in facts so check and claim sync work without a collect; a scenario runs retire → check → sync. Spec R6.

<!-- fr:journal kind=decision scope=spec id=q7-default-branch-guard created=2026-10-13T22:53:06+00:00 -->
### q7-default-branch-guard · decision · Guard every merge_ctx caller; --yes tests for both cases

Operator (round 1, Q7): every merge_ctx caller holds the repo for the pass with one warn line instead of aborting; --yes drive tests for a self-healing clone without origin/HEAD and for an unreachable origin. Spec R13.

<!-- fr:journal kind=decision scope=spec id=q8-waitout-pin-close created=2026-10-13T22:53:06+00:00 -->
### q8-waitout-pin-close · decision · #1178 pinned by a test and closed as resolved by #1153

Operator (round 1, Q8): add a test proving wait_out renewal spends no GraphQL in an exhausted GraphQL window; leave the 60s retry for a failed REST read as is. Spec R14.

<!-- fr:journal kind=decision scope=spec id=q9-verification created=2026-10-13T22:53:06+00:00 -->
### q9-verification · decision · Verification: candidate, plus one post-merge live row

Operator (round 1, Q9): run strategy candidate (scenarios incl. retire → check → sync); one post-merge live row: after the next drive pass on super-fr no closed issue carries fr:in-progress unheld, and #1146 is handed back or under Needs you. Spec ## Verification, ## Test Plan.
