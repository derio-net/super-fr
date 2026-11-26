<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-batch-merge-readiness

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-24T22:27:42+00:00 input=true -->
### brief · discovery · Operator brief — batch merge-readiness (super-fr#1578, super-fr#1581)

/fr-goal batch merge-readiness. Batch `merge-readiness` of derio-net/super-fr: 2 issues, delivered as ONE pull request.
Batch title: Merge only what delivered: the driver reads deliver from the cursor, and the Batches page shows one readiness verdict per PR.
super-fr#1578: Wave driver merges an approved draft batch PR before its run resolved deliver. Observed 2026-11-19 (#1560): the driver readies and merges an approved green draft whose run is still at `deliver: running`; gc then reaped the workspace under the running suite. Expected: merge only after the run resolved deliver (cursor at PR head); approved green undelivered draft held as "approved, not delivered"; gc should not reap a workspace whose run step is running.
super-fr#1581: Batches page: a readiness verdict per PR (delivered, CI at head, mergeable, approval, whose move), from the same function the driver merges by; also close-out and export PRs.
Delivery rules: branch feat/batch-merge-readiness; draft PR once the spec is committed with "Closes derio-net/super-fr#1578" and "Closes derio-net/super-fr#1581"; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no fr pr settle loop); never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=d1-delivered-rule created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d1-delivered-rule · decision · Delivered is read from the run cursor only; fr-debugging gets a cursor

Q1 answer: 'Cursor. And add cursor to fr-debugging (see #1655)'. Delivered iff the cursor at the live head records deliver done; no cursor or an unreadable head is not delivered. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-early-approval created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d2-early-approval · decision · Approval stays pinned; an approval before delivery is voided by the deliver commit

Q2 answer: keep it voided (recommended). The page tells the operator to re-label once Ready for approval. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-gc-guard created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d3-gc-guard · decision · gc guard for a running run is in scope

Q3 answer: in scope (recommended). gc keeps a merged workspace whose worktree cursor has a step or unit running. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-coverage created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d4-coverage · decision · Verdict covers batch, close-out, archive and export PRs

Q4 answer: batch, close-out, export (recommended). Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d5-verification created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d5-verification · decision · CI tests verify; gate reviewer (holds nothing)

Q5 answer: CI tests, gate reviewer (recommended). Strategy candidate (smoke walk), every row none (CI), one live post-merge observation gated reviewer. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d6-debug-cursor-scope created=2026-11-24T22:27:42+00:00 decided_by=operator -->
### d6-debug-cursor-scope · decision · Minimal fr-debugging workflow now; stations and staffing stay with

Round 2 answer: minimal cursor now (recommended): a shipped fr-debugging manifest (debug, review, deliver) the skill starts and resolves; #1655 referenced, not closed. Decider: operator.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-24T22:27:42+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · The change moves the gate that decides what the driver lands on main

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-24T22:27:42+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · One readiness function must be proven to drive both the queue and the page

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-24T22:27:42+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. The operator's round-1 answer to the no-cursor question asked to add a run cursor to fr-debugging (see #1655); #1655 is a multi-step epic item, so its size in this batch needed the operator's decision.

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R1's no-cursor / unread / head-mismatch split cannot be computed from what facts store today, and the spec names no facts change

model.py:362-364 and cursor.py:61-84: a None cursor means not read, unreachable or no cursor alike; triage_batch_cmd.py:4221-4232 returns None with no clone. Fix: name head_oid as the read head, add a read status with a FACTS_SCHEMA bump, make no-clone a visible verdict.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · R5 makes mergeable / not behind / not conflicting conditions of readiness, but the queue's admission does not and should not require them, so R4 contradicts R5

wave_queue.py:364-378 reads no mergeable state; conflicts are met at build and ejected (wave_queue.py:893-906); the queue rebuilds on a moved main. Decide whether merge facts change admits, and align R5.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · One function over different inputs: the board's snapshot lacks the required-checks, patch-id, base and mergeable reads the driver judges by, so R4's promise does not hold as written

views.py:149-162 vs triage_batch_cmd.py:4518-4542. Narrow R4 to the same function over the same inputs and say where the page lags, or carry the reads into facts; wire mergeable/merge_state into the board's LivePr; test equal verdicts over equal inputs.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · `batch_drive.py` `_queue_members` does not exist; the member classification is `_member_reports` over a `Snapshot`, which also needs the cursor map

batch_drive.py:1590-1624, 1756-1795; views.py:140-162. Fix the name; Snapshot needs the cursor map from both builders; _member_reports calls batch_readiness on queue_snapshot.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · The voiding sha is not in the approval verdict: `Void` carries the approved head, and the existing `voided_at()` helper also returns the approved head

approval.py:79-84, 291-313, 586-594. Read ApprovalEvent.voided_at from batch.events; before settlement Void reports the live head; pin with a test.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · R5 says 'exactly one' verdict but gives no precedence when several conditions hold

Approved+undelivered+red, voided+undelivered, queue-held are undecided. Write the check order and add every reason from the design to R5.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · `other_readiness(entry, qs)` cannot say why a trust rule did not admit an entry: `QueueSnapshot.others` holds admitted entries only

wave_queue.py:186-202; batch_drive.py:1773, 1792, 2080-2109. Pass refused candidates with reasons into QueueSnapshot, or source the reason from the pass's actions.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · §D is wrong for external gc (it never reaps) and leaves out where in local gc the guard sits, given that `down` must stay unchanged

external.py:291-315 never reaps; local.py:2226-2346: guard in _reap_or_classify on dry-run and live, merged and merged-by-content, not in _reap_hazard/_down_worktree_tail; build on preserve.branch_runs with a running predicate.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · A `journal:debug` step is a valid token, but the record engine, the review evidence target and deliver's PR body and leftovers gate have no way to find the run's debug journal

record/apply.py:236-249, 391-397; run_cmd.py:1767, 1778-1792; record/pr_body.py:876-923. Say how a run names its debug journal and cover every reader, including the finding-id grammar.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · fr-debugging reusing an fr-goal workspace would put two cursors on one branch, and `read_cursor` takes the first, which reopens the #1560 hole

fr-debugging SKILL.md:32-35; cursor.py:61-81. The reuse case starts no run; R1 fails closed when several cursors name the branch.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · R6's 'failing job' link has no source: facts and `LivePr` carry check names and counts, not job URLs

model.py:353; batch_drive.py:164-165. Link the PR's checks tab, or add check URLs to facts.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · Open PRs whose runs carry no cursor (every in-flight fr-debugging PR) are held forever once this ships, and the spec names no way out

R1/R2 hold an old debug PR with no path forward. State the intended answer so the hold is designed.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-24T22:37:11+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · The Test Plan lists only the post-merge observation; the design's CI-proven behaviour (R4, R8, R9, R10/R11) has no Test Plan step

Add a Test Plan step per Verification row, or say the rows are the Test Plan for CI behaviour.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-24T22:37:11+00:00 -->
### spec-review-1 · review · independent spec review: 13 findings

Findings raised: s-r1 … s-r13 (all tagged in scope). Decisions d1–d6 honoured. Verified file:line for every named function (wave_queue.py:364 _ready, :206 QueueSnapshot, :269 QueuePlan, :422 _other_ready; batch_drive.py:157 LivePr, :1590 _member_reports; triage_batch_cmd.py:6882-6899 the only pr_ready calls; queue_exec.py:551 the only pr_merge; cursor.py:33,61; collect.py:1003; kanban.py:456,620,793; approval.py:179,232; local.py:2166,2226,2268; external.py:291; preserve.py:202; run_cmd.py:1778, 2441, 8076-8095; workflow/artifacts.py:106-140; spec_section.py:46-53). Suggested lenses: security, tests, errors.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-24T22:37:11+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · No-cursor, unread and no-clone states must each give a distinct visible verdict, never a silent hold

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R1's no-cursor / unread / head-mismatch split cannot be computed from what facts store today, and the spec names no facts change

R1 lists each not-delivered reason; Design §A adds PullRequest.cursor_read (read|unread|no-clone), head_oid as the read head, FACTS_SCHEMA 16 → 17.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: R5 makes mergeable / not behind / not conflicting conditions of readiness, but the queue's admission does not and should not require them, so R4 contradicts R5

R5: merge state never changes admits; conflicting is a verdict only for an unapproved PR, behind is a fact only. §B: admits is today's conditions plus delivered.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: One function over different inputs: the board's snapshot lacks the required-checks, patch-id, base and mergeable reads the driver judges by, so R4's promise does not hold as written

R4 narrowed to the same function over the same inputs, with the page showing its facts' collection time where it lags; §C wires mergeable/merge_state into the board's LivePr and adds the equal-verdicts test.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: `batch_drive.py` `_queue_members` does not exist; the member classification is `_member_reports` over a `Snapshot`, which also needs the cursor map

§B names _member_reports, adds the cursor map to Snapshot from both builders, and routes it through queue_snapshot.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: The voiding sha is not in the approval verdict: `Void` carries the approved head, and the existing `voided_at()` helper also returns the approved head

§B: the voiding sha is ApprovalEvent.voided_at after settlement, the live head while Void; approval.voided_at() not used for it.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: R5 says 'exactly one' verdict but gives no precedence when several conditions hold

R5 now lists the verdicts in check order, first match wins, including queue held, gate and base reasons.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: `other_readiness(entry, qs)` cannot say why a trust rule did not admit an entry: `QueueSnapshot.others` holds admitted entries only

R8 and §C: drive_pass keeps trust-rule refusals with their reason as QueueSnapshot.refused; other_readiness reads admitted and refused.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: §D is wrong for external gc (it never reaps) and leaves out where in local gc the guard sits, given that `down` must stay unchanged

R9 and §D: guard in local.py _reap_or_classify on both paths and both merged verdicts, on preserve.branch_runs with a running predicate; external gc needs no change; down untouched.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: A `journal:debug` step is a valid token, but the record engine, the review evidence target and deliver's PR body and leftovers gate have no way to find the run's debug journal

R11 and §E: the debug record emits debug: <journal path> (new artifact token); apply.py slug resolution, _EvidenceTarget scope debug, the findings gate (ids d-r<k>) and pr_body._journals/unaccounted read it.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: fr-debugging reusing an fr-goal workspace would put two cursors on one branch, and `read_cursor` takes the first, which reopens the #1560 hole

R10: the reuse case starts no run and fr run start keeps refusing a second run on a branch; R1: delivered only when every cursor naming the branch has deliver done.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: R6's 'failing job' link has no source: facts and `LivePr` carry check names and counts, not job URLs

R6 links the PR's checks tab; job URLs in facts are out of scope.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-24T22:37:11+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: Open PRs whose runs carry no cursor (every in-flight fr-debugging PR) are held forever once this ships, and the spec names no way out

New R12: a PR that can never carry a cursor is held with Next action 'merge it by hand after review, or deliver it through a run'; new row batch-readiness-no-cursor-hold.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-24T22:37:11+00:00 state=refuted resolves=s-r13 -->
### s-r13-resolved · finding [refuted] · resolves s-r13: The Test Plan lists only the post-merge observation; the design's CI-proven behaviour (R4, R8, R9, R10/R11) has no Test Plan step

fr-goal's rule (skill §1, the standing verification question) keeps only post-merge rows that no pre-merge strategy can exercise in the Test Plan; CI-proven behaviour is carried by the Verification rows, each naming its CI proof, and by acceptance rows. Adding CI steps to the Test Plan would contradict that rule.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-24T22:37:13+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  batch-merge-live-drive: reviewer
  batch-merge-needs-deliver: none
  batch-readiness-no-cursor-hold: none
  batch-readiness-other-entries: none
  batch-readiness-verdict: none
  fr-debugging-run-cursor: none
  gc-keeps-running-run: none
row_kinds:
  batch-merge-live-drive: live
  batch-merge-needs-deliver: none
  batch-readiness-no-cursor-hold: none
  batch-readiness-other-entries: none
  batch-readiness-verdict: none
  fr-debugging-run-cursor: none
  gc-keeps-running-run: none
run_gate: reviewer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-24-batch-merge-readiness-p1 created=2026-11-24T22:40:00+00:00 -->
### tier-2026-11-24-batch-merge-readiness-p1 · decision · hard: phase 1 changes the merge gate every queue admission and driver merge relies on, and the facts schema

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-batch-merge-readiness-p2 created=2026-11-24T22:40:02+00:00 -->
### phase-split-2026-11-24-batch-merge-readiness-p2 · decision · ask: the Batches page verdict (R5-R8) is its own reviewable ask

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-batch-merge-readiness-p3 created=2026-11-24T22:40:05+00:00 -->
### phase-split-2026-11-24-batch-merge-readiness-p3 · decision · ask: gc keeping a running run (R9) is its own ask in isolation code

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-batch-merge-readiness-p4 created=2026-11-24T22:40:08+00:00 -->
### phase-split-2026-11-24-batch-merge-readiness-p4 · decision · ask: the fr-debugging workflow and its debug journal readers (R10, R11) are their own ask

<!-- fr:journal kind=owed scope=spec id=test-plan-step-1 created=2026-11-26T16:32:39+00:00 -->
### test-plan-step-1 · owed · Test Plan step 1 owed

what: post-merge — operator-driven: on the next live `fr triage batch drive`, an approved, green batch PR whose run is not at `deliver: done` stays on the Batches page as "Approved, not delivered" and is neither marked ready nor merged; once its run delivers and the operator re-labels, it merges.
why: needs a live fr triage batch drive that meets an approved, green batch PR whose run is not at deliver: done; no such batch is in flight at closeout
how: fr journal resolve --scope spec --slug 2026-11-24-batch-merge-readiness --id test-plan-step-1 --state fixed --note "<evidence>"
owed_key: spec:2026-11-24-batch-merge-readiness#step1
