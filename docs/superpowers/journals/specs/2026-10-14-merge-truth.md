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

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-13T23:03:26+00:00 -->
### spec-review-r1 · review · independent spec review: 14 findings, all in scope

Decisions q1–q9 are reflected in R1–R15. q3 drifted on the busy-session case (sr-3), and q5 and q6 could not work as written (sr-6, sr-1).
Member coverage: #1190 .1–.4 → R1–R3, R12, R5, R6, and #1190 .5 (reconcile #1176/#1178) → R13/R14. #1172 asks → R7–R10, and its draft note → R11. #1161 → R4. #1160 → §G. #1176 → R13. #1178 → R14.
Every named file, function and line was verified (the reviewer's verified list covers claim_writes, claim_sync, claims, collect, triage_claim_cmd, triage_cmd, triage_batch_cmd, batch_drive, batch_merge, probe, kanban, views, render, check, gitseam, gh, real_ghclient, real_ghrestclient).

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Retire's facts rewrite sets `released` on IssueClaim, a field that does not exist; no atomic facts writer exists

model.py:315-326 IssueClaim has no released field (extra=forbid), and facts hold only un-released claims (claims.py:213-225). collect writes facts.json with a bare write_text (triage_cmd.py:529-532). Fix: remove the released signer's entries and write through write_text_atomic.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · The archive-conflict hand-back cannot reuse ConflictEvent / conflict_decision / _hand_back as written

ConflictEvent.paths has min_length=1 (model.py:741-756). conflict_decision counts every ConflictEvent since dispatch (batch_drive.py:569-598). _hand_back targets the batch items with a MergeConflictError (triage_batch_cmd.py:5233-5271). A held ConflictEvent raises merge-conflict (views.py:316-325), and record_stop is keyed by batch id. Fix: a distinct event and counter, a close-out target, the export source and key, and clear_stop on merge.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · R12 starts a fresh close-out item whenever the session is not idle; existing hand-back waits while it is working

triage_batch_cmd.py:5290-5304: idle → message; working/blocked → retry next pass; absent/done → fresh. q3 asked for the batch-PR behaviour.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Dropping the closed-member refresh must not also drop it for a member facts do not hold (issue None)

claim_sync.py:121-124 covers `issue is None or issue.state != open` together. Dropping both would let open members' claims lapse when a read fails.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The driver's settle path is unspecified past plan_sync: Snapshot field, Action kind, carried filter, batch-less ops

claim_sync.py:33 OpKind, :84-88 batch required, :152-153 released counts release only. triage_batch_cmd.py:3838-3852 and :4455 filter by repos.get(op.batch). kanban.py:101-111 phrase map.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R5: a recorded take the forge then refuses (live rival or Held) is never claimed by sync, and the event stays

claim_writes.py:290-296 may_displace raises ClaimError, and claim can return Held. claim_sync.py:126-128 lists a held member and never claims it. Fix: withdraw the event on refusal, keep it on transport failure.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · batch_merge.live_checks takes a MergeContext; _archive_prs has none and should not build one

batch_merge.py:254-262. merge_ctx costs a fetch, a config read, merge methods and base rules. Fix: split into pr_checks_verdict(client, repo, number, ci_none).

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · DefaultBranchUnknown is raised for every ForgeReadError from merge_ctx, not only a default-branch failure

triage_batch_cmd.py:3493-3508 also raises for a merge-methods read failure. Fix: raise it only from the fetch and default_branch().

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · clean-labels' target set is stated two ways, and the existing row triage-closed-in-progress-set contradicts R2

tests/scenarios/triage-closed-in-progress.sh:21-24 and test_triage_clean_labels.py:50 pin the stale-only target set. Fix: pick one set and name the existing row.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · triage-closed-issues-unclaimed is verify: candidate but no scenario is named for it

Only the retire scenario was named. A fake REST forge can exercise this row. Fix: name tests/scenarios/triage-closed-settle.sh.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · `claims_of` does not exist, and widening the closed query to "either label" needs two reads (gh labels AND)

collect.py:917-923 lists with labels=[fr:in-progress], and gh.py:268 ANDs repeated --label flags. The reader is read_claims (claims.py:190).

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · R9's reasons do not match §D's rule: drafts get an archive action, and wrong base already emits `blocked`

batch_drive.py:1321-1331 already blocks a wrong-base PR every pass, and §D gave drafts an archive action, so the draft warn would never print.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · R8: plan_pass has no batch input, and forcing a read every pass conflicts with quiet and essential passes

probe.py:189-223 receives repos/changed/live only, and pacing.py:127-138 is the caller. Fix: a new closing parameter, with the quiet and essential behaviour stated.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-13T23:03:26+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · R15's trigger and the post-merge Test Plan check a narrower set than R1/R2 settle

triage_kanban_cmd.py:359-367 counts stale only and names clean-labels only. The post-merge step checked fr:in-progress only.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Retire's facts rewrite sets `released` on IssueClaim, a field that does not exist; no atomic facts writer exists

§C/R6: retire removes the retired signer's entries from Issue.claims (what a fresh collect writes) and writes facts.json through write_text_atomic, with no schema change. State-ref publication follows collect's path.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: The archive-conflict hand-back cannot reuse ConflictEvent / conflict_decision / _hand_back as written

§E: a new judgements event archive_conflict (schema 9→10) with its own counter since the close-out event and no paths. It gets archive_conflict_decision, a close-out-targeted hand-back with item id archive-conflict-<batch>-<n>, its own Need kind archive-conflict, an export source and stop key export:<repo>, and clear_stop on merge.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: R12 starts a fresh close-out item whenever the session is not idle; existing hand-back waits while it is working

R12/§E: idle → message; working or blocked → nothing sent, retry next pass; absent or done → a fresh archive-conflict item.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Dropping the closed-member refresh must not also drop it for a member facts do not hold (issue None)

R1/§A: only a member the facts show closed drops the refresh. issue None keeps the due-only refresh.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The driver's settle path is unspecified past plan_sync: Snapshot field, Action kind, carried filter, batch-less ops

§A names OpKind settle, an optional ClaimOp.batch for settle ops only, Snapshot.settles_owed, Action settle, the kanban phrase, and the carried filter by the key's repo. released()/record_releases count settle ops on members.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R5: a recorded take the forge then refuses (live rival or Held) is never claimed by sync, and the event stays

R5/§B: a refusal (ClaimError/Held) withdraws the just-recorded event and exits 2. A transport failure keeps it, and sync claims the member. The row text and verification line cover all three failures.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: batch_merge.live_checks takes a MergeContext; _archive_prs has none and should not build one

§D: pr_checks_verdict(client, repo, number, *, ci_none) holds the rule, and live_checks delegates to it. _live_head_prs calls pr_checks_verdict.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: DefaultBranchUnknown is raised for every ForgeReadError from merge_ctx, not only a default-branch failure

§F/R13: DefaultBranchUnknown is raised only by the fetch and default_branch(). Every other ForgeReadError behaves as today.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: clean-labels' target set is stated two ways, and the existing row triage-closed-in-progress-set contradicts R2

R2/§A: clean-labels keeps the stale-only target set, so the existing scenario and unit test stand. It now removes both labels. Row triage-closed-in-progress-set is named under Acceptance rows as moving to both labels.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: triage-closed-issues-unclaimed is verify: candidate but no scenario is named for it

§G names tests/scenarios/triage-closed-settle.sh, with a fake REST forge, for triage-closed-issues-unclaimed.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: `claims_of` does not exist, and widening the closed query to "either label" needs two reads (gh labels AND)

§A names read_claims and specifies two closed reads, one per label, deduplicated by number, each warning on truncation. The StaleInProgress docstring and copy name both labels.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: R9's reasons do not match §D's rule: drafts get an archive action, and wrong base already emits `blocked`

R9 rewritten: a waiting line for pending or failing checks, the R12 conflict line, the existing blocked line for a wrong base, and the archive action's own 'marked ready, merged' line for drafts. §D emits the warn only when no archive, archive-conflict or blocked action applies.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: R8: plan_pass has no batch input, and forcing a read every pass conflicts with quiet and essential passes

R8/§D: plan_pass gains closing from pacing.py and adds it to only on partial and essential passes. A would-be quiet pass with a non-empty closing becomes a partial pass over closing. live_repos includes closing. The cost is stated.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-13T23:03:26+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: R15's trigger and the post-merge Test Plan check a narrower set than R1/R2 settle

R15: the note fires on stale or release-pending entries and names claim sync or the drive pass, with clean-labels as the stale-only manual route. The Test Plan adds the fr:claimed check.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-merge-truth-p2 created=2026-10-13T23:05:43+00:00 -->
### phase-split-2026-10-14-merge-truth-p2 · decision · ask: archive PRs (#1172, #1190.2) are an independently reviewable ask, R7-R12

Phase 2 serves its own ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-14-merge-truth-p3 created=2026-10-13T23:05:46+00:00 -->
### phase-split-2026-10-14-merge-truth-p3 · decision · ask: drive robustness (#1176, #1178) is an independently reviewable ask, R13-R14

Phase 3 serves its own ask.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-14-merge-truth-p2 created=2026-10-13T23:05:49+00:00 -->
### tier-2026-10-14-merge-truth-p2 · decision · hard: judgements schema 9→10 migration plus a new hand-back path the whole merge train's stop/Need machinery relies on

Phase 2 changes a closed-world judgements schema every triage reader loads and extends the conflict hand-back and stop recording used by every drive pass.

<!-- fr:journal kind=owed scope=spec id=test-plan-step-1 created=2026-10-14T13:13:54+00:00 -->
### test-plan-step-1 · owed · Test Plan step 1 owed

what: post-merge — operator-driven: after release, run one `fr triage batch drive --yes` pass over derio-net/super-fr. Then `gh issue list --state closed --label fr:in-progress` and `gh issue list --state closed --label fr:claimed` list only issues another scope's claim holds (today, none). Archive PR #1146 has been handed to a close-out session or is listed under Needs you now as an archive conflict, and is not reported as "stopped again".
why: post-merge operator-driven live drive pass (fr triage batch drive --yes writes to the forge); only v5.27.0-rc.2 is cut, the final release has not shipped yet
how: fr journal resolve --scope spec --slug 2026-10-14-merge-truth --id test-plan-step-1 --state fixed --note "<evidence>"
owed_key: spec:2026-10-14-merge-truth#step1
