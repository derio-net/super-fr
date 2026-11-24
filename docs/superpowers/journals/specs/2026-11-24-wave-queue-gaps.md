<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-wave-queue-gaps

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-24T22:39:40+00:00 input=true -->
### operator-brief · discovery · Operator brief: the /fr-goal text and issue #1677

## Goal as typed

/fr-goal Build derio-net/super-fr#1677 (read it in full with gh issue view 1677 --repo derio-net/super-fr): the wave merge queue's three remaining gaps. (1) A conflict hand-back brief names the combination commit ahead of the PR (fr-queue/<scope>/slot-<k-1>) for the session to merge instead of origin/main, and is re-issued after an ejection rebuilds the slot. (2) Waves composed by file overlap: batch suggest and batch create/edit --wave report overlapping batches in one wave outside generated files. (3) An operator verb to put any open PR of the repo into the queue (fr triage queue add/remove --pr N), under the same approval (approved-fr pinned to the patch-id) and trust rules, recorded as a queue event, included in the wave's drain and release. Start by reading the bridge and queue code end to end (AGENTS.md's bridge audit rule): packages/fr/src/fr/triage/wave_queue.py, queue_exec.py, batch_drive.py, batch_merge.py, approval.py, commands/triage_batch_cmd.py, and the spec docs/superpowers/implemented/specs/2026-11-19-wave-merge-queue-design.md. Coordinate with open PR #1669 (CI economy for #1647): it edits the same queue modules (queue_exec.py, batch_drive.py, batch_merge.py, gitseam.py, model.py, triage_batch_cmd.py, the conflict brief, .fr/triage.yaml's mirrors/generated keys). Read its diff first, design on top of it, and merge its branch into yours once it lands on main. Mind the module line budgets (tests/unit/test_tripwire_module_budget.py): batch_drive.py and triage_batch_cmd.py are within a few lines of theirs, so new code goes in new modules. Deliver one PR that Refs #1677; do not label it.

## Issue #1677

# Queue: hand-backs merge the slot ahead, waves composed by file overlap, and the operator can queue any PR

## Problem

The wave merge queue (#1602) avoids merging `main` into waiting PRs only when git can stack them on its own. Three gaps remain after #1647 (CI economy: cancel superseded runs, skip landed combinations, regenerate generated files in the combination, light lane; PR #1669):

- a real conflict between entries is handed back with a brief to merge `origin/main`, so the PR conflicts again when the entries ahead land;
- waves are composed without looking at which files their batches change, so overlapping batches share a wave and serialise through hand-backs;
- a PR outside the open wave (an fr-arch feature, a hand-started fix) cannot join the queue: it is merged by hand, which re-conflicts every queued PR, or waits as a between-waves entry until no waved batch is unfinished.

## Asks

1. **A hand-back merges the combination ahead of the PR, not `origin/main`.** Today a real conflict found while building a combination is handed back with a brief to merge `origin/main`. When entries ahead of the PR are still in the queue, the session resolves against a main that is about to move, and the PR conflicts again as soon as they land (a second hand-back, budget spent). The brief names the slot commit the PR was being stacked on (`fr-queue/<scope>/slot-<k-1>`, the exact sha `land: push` will fast-forward `main` to) and tells the session to merge that commit. Once the entries ahead land, the PR already contains `main`'s head: no further merge, and its patch-id against `main` is its own change only, so an approval given after those landings stays valid. If an entry ahead is ejected, the slot is rebuilt and the brief is re-issued against the new slot. Seen on 2026-11-24 with #1628 (in the queue) and #1630 (same wave, same 11 files): merging the slot commit `24130aa17` by hand made #1630 land-ready the moment #1628 landed at that very sha.
2. **Compose waves by file overlap.** `fr triage batch suggest`, `batch create --wave` and `batch edit --wave` report pairs of batches in one wave whose expected change sets overlap outside generated files (by the issues' named paths, or, once PRs exist, by the PRs' changed files), and suggest either one batch or different waves. Batches that do not overlap stack in the queue and land together; batches that do are serialised by conflict hand-backs whatever the queue does.
3. **The operator (the orchestrating session) can put any PR into the queue.** Today the queue takes only the open wave's batch PRs, and a stray PR (an fr-arch feature, a hand-started fix) can join only by being merged by hand, which re-conflicts every queued PR (as on 2026-11-24 morning), or as a between-waves entry, which waits until no waved batch is unfinished. Add a verb, e.g. `fr triage queue add --pr <n> [--repo R]`, that admits any open PR of the repo into the open queue (or opens a between-waves queue for it when none is open) as an entry of the current queue, stacked and tested like any other, under the same approval rule (`approved-fr` pinned to the patch-id) and the same trust rules (same-repo branch, allowed author). It records a queue event naming who added it; `fr triage queue remove --pr <n>` takes it out. The wave's drain and release then include it, so a stray change ships in the next release without a hand merge.

Tests per ask: a hand-back brief names the slot commit and is re-issued after an ejection; `suggest`/`--wave` report an overlapping pair; `queue add` admits a non-wave PR under the approval and trust rules, records who added it, and the wave's drain waits for it.

Refs #1602, #1647, #1669. Moved here from #1647 so that PR #1669 stays scoped to CI economy.

<!-- fr:journal kind=decision scope=spec id=q1-stale-slot created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q1-stale-slot · decision · An entry carrying a stale slot commit is held; its brief resets and force-with-lease pushes

Operator chose: structural guard (head reaches a recorded combination commit outside the lineage → never built), re-issued brief: reset to the pre-merge head, push --force-with-lease, merge the new slot commit. Spec R4.

<!-- fr:journal kind=decision scope=spec id=q2-reissue-free created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q2-reissue-free · decision · A re-issued brief does not spend the hand-back budget

Operator chose: free; recorded as a conflict event marked reissue. Spec R3.

<!-- fr:journal kind=decision scope=spec id=q3-overlap-warn created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q3-overlap-warn · decision · Overlap at create/edit --wave warns and writes; the later batch's session is told to watch for the hand-back

Operator answered: warn and write anyway, and instruct the batch session that comes second to watch for conflicts and repair (or the orchestrator watches, per the queue's mechanics). Spec R8, R9: the queue's conflict hand-back is the orchestrator's watch; the later batch's dispatch brief names the overlap.

<!-- fr:journal kind=decision scope=spec id=q4-idle-add-opens created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q4-idle-add-opens · decision · An added PR opens a between-waves queue at once when the lowest unfinished wave has nothing ready

Operator chose: open now. Spec R14.

<!-- fr:journal kind=decision scope=spec id=q5-drain-waits-preapproved created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q5-drain-waits-preapproved · decision · The drain waits for an added PR (stall Need); --preapproved lets the driver add approved-fr

Operator answered: the drain waits with a stall Need, and any PR can be declared preapproved to the orchestrator, which then adds the approved-fr label when the PR is on the queue with no conflicts or CI errors. Spec R13, R15.

<!-- fr:journal kind=decision scope=spec id=q6-who-added created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q6-who-added · decision · queue_add/queue_remove name the forge login the command authenticates as

Operator chose: forge login (GhClient.viewer_login). Spec R10, R11.

<!-- fr:journal kind=decision scope=spec id=q7-verification created=2026-11-24T22:39:40+00:00 decided_by=operator -->
### q7-verification · decision · CI suite proves every row; one post-merge live row gated tester

Operator chose: CI suite + live row. Spec ## Verification.

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · Lineage is exact-sha membership, so a combination that landed in the middle of a push reads as stale and triggers R4's forced reset

evidence: spec §A lineage; queue_exec.py:497,522 (land_push records main = the LAST landing's commit only); wave_queue.py:638-651 (replay drops every landed combo)
When slot-1 and slot-2 land in one push, queue_land.main is slot-2's sha and slot-1 is neither base, standing nor a recorded main, so an entry that merged slot-1 gets held and told to force-push. A fresh-commit rebuild (queue_exec.py:257-267) has the same effect. Define "leads to main" by ancestry, or include every combination of each landed chain.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Under queue.land: merge the slot commit never becomes main, so R1's brief is wrong and R4 fires on every merged slot

evidence: model.py:550; queue_exec.py:530-570 (land_merge: forge merges each PR's head)
Under land: merge main is a forge merge commit, never the slot sha; a PR that merged a slot commit carries a commit never reachable from main. State R1/R4 per land mode.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · Under method rebase, merging the slot commit does not stop the second conflict R1 promises to avoid

evidence: queue_exec.py:192-206 (rebase replays the non-merge commits), :222-245 (p3-r9 ejection)
Rebase cherry-picks the PR's original conflicting commits; the session's merge resolution is not replayed. Scope R1 to merge/squash or say what a rebase repo's brief says.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · R1 names slot-(k-1), but the ejected entry re-enters behind the entries that were behind it

evidence: wave_queue.py:457-470 (_by_readiness with ejection floor); approval.py:10-29
Entries k+1.. are rebuilt on slot-(k-1) and k comes back later, so slot-(k-1) is not what main becomes ahead of it; R1 and R2 name different targets. Name R2's stack target in R1 too, or pin the re-entry position.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · R4's reset to the last hand-back head can discard work, and does not remove a stale commit carried from an earlier hand-back

evidence: spec R4; decision q1-stale-slot
(a) commits after the hand-back are thrown away silently; (b) a second hand-back at a head that already carries a stale combination makes the reset target keep it, repeating forever. Target the newest hand-back head that reaches no stale combination and tell the session to cherry-pick its later non-merge commits.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · The stale-carry check reads only the current record's queue_built shas, so a requeued or deferred batch carries an ejected change out undetected

evidence: spec §A; wave_queue.py:282-289 (effective_wave), :668-680 (slot_leases walks every record)
Compute carried over every queue_built sha of this scope's records for the repo.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · The carry ancestry read is quadratic per pass and does not say what happens when git cannot read it

evidence: spec §A; queue_exec.py:327-334
entries × every built sha is-ancestor calls per pass, growing; filter and cache, or one rev-list per head. A missing object must hold the entry, never read as not carried.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · The brief's `git fetch origin <onto_ref>` cannot fetch the sha once the slot was rebuilt

evidence: spec §A; queue_exec.py:309-333 (slots rebuilt in place)
Say what to do when the fetched ref no longer holds the sha: stop and wait for the re-issued brief.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · R9 tells the second batch the queue builds it after the first, but queue order is readiness order, not dispatch order

evidence: wave_queue.py:439-470 (readiness order); batch_drive.py:1574 (_dispatch_key)
Say "whichever lands second gets the conflict hand-back", or order overlapping entries by dispatch order.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · A preapproved batch PR (or an R32 entry's PR) becomes a second, operator-kind entry

evidence: spec R10, §C, R12, R15; model.py:1109; triage_batch_cmd.py:7241-7296
added() returns a preapproved batch PR, so it is admitted twice; R10 never refuses an R32 entry PR. Exclude existing entries, say where a batch PR's driver-made approval is recorded, and whether remove withdraws a batch PR's preapproval.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · Preapproval re-approves every future head and trusts a self-reported login; the spec should bound it

evidence: decision q5; spec R10, R13; approval.py:10-29; batch.py:250-263
Any push to a preapproved branch by anyone with write access is approved and landed once green, cancelling the patch-id pin; the trust root moves to the `by` field in the state file. At minimum check `by` against the allowed authors at use; consider bounding re-approval; state the consequence.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · R15 on a between-waves queue lets one unready added PR block the next wave and every release

evidence: spec R14, R15, §C; wave_queue.py:531-563, :1043-1078
A between-waves queue held open by an ejected or red added PR keeps the hold open and the next wave closed. Exclude those for between-waves queues; measure the stall from when the drain would otherwise fire, not the add time.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · Schema 14: `_EVENT_SCHEMAS` never sees a top-level `queue_requests`, and the writer stamps unconditionally

evidence: model.py:1598-1628, :104, :1494; batch.py:533
Add explicit refusals below 14 for queue_requests and ConflictEvent onto/reissue; JUDGEMENTS_SCHEMA moves to 14 and the read literal widens; update AGENTS.md.

<!-- fr:journal kind=finding scope=spec id=s-r14 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r14 · finding [open] (reviewer: in scope) · batch_drive.py has 4 lines of budget; the design needs more than the one step-3 loop there

evidence: tests/unit/test_tripwire_module_budget.py:25; batch_drive.py:433-435, :461, :934, :1783, :2106-2109
Snapshot fields, Admitted kind, QueueSnapshot wiring and conflict_decision's skip rule all live in batch_drive.py. Name the move, or plan the budget bump with its reason.

<!-- fr:journal kind=finding scope=spec id=s-r15 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r15 · finding [open] (reviewer: in scope) · `queue add|remove` does not say how it resolves the scope and its state, or how it coexists with a running driver

evidence: spec R10/R11, §C; batch.py:505-542
The verb needs the scope arguments, the state ref sync, and a stated behaviour for a refused write.

<!-- fr:journal kind=finding scope=spec id=s-r16 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r16 · finding [open] (reviewer: in scope) · The Test Plan has one live line and no case for the five CI-proven rows

evidence: spec ## Verification vs ## Test Plan; issue #1677 "Tests per ask"
Number the CI cases and cite the R's so each row's evidence is checkable.

<!-- fr:journal kind=finding scope=spec id=s-r17 created=2026-11-24T22:50:30+00:00 state=open review_scope=in -->
### s-r17 · finding [open] (reviewer: in scope) · Small citation errors: MergeConflictError's home and `_conflict`'s line

evidence: batch_merge.py:42-49; queue_exec.py:152-158; triage_batch_cmd.py:6315, :6979
Cite both places; the rebuilt exception in _queue_hand_back must carry the new fields too.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-24T22:50:30+00:00 -->
### spec-review-1 · review · independent spec review: 17 findings

Findings s-r1..s-r17, all in scope; heaviest: lineage and land modes (s-r1..s-r3), re-entry position (s-r4), the R4 reset target (s-r5..s-r7), preapproval trust (s-r11), drain liveness (s-r12), schema 14 (s-r13). Decisions q1-q7 are each reflected. Verified citations listed by the reviewer (queue_exec.py:270, :1258-1275; batch_merge.py:42; wave_queue.py:175, :868, :896-906, :243-265, :206, :613, :439, :531, :1043, :668; batch_dispatch.py:279; batch_drive.py:891, :919, :934, :2106-2109, :453, :1574; triage_batch_cmd.py:914, :964, :6315, :6602, :6966, :7241; approval.py:318; batch.py:250, :352, :770, :775, :780, :845; model.py:1109, :1164, :866, :1362, :550, :555, :395; ghclient.py:469, :303). PR #1669's generated/regen/Regen not verifiable read-only. Suggested lenses: security, errors.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-24T22:50:30+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · R13 lets the driver apply approved-fr itself and R4 briefs a force-push

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-24T22:50:30+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · the carry and lineage reads must fail closed on unreadable git state

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: Lineage is exact-sha membership, so a combination that landed in the middle of a push reads as stale and triggers R4's forced reset

Lineage is now ancestry (R2): a commit leads to main when it is an ancestor of the last standing combination or the base; a mid-push landed or fresh-rebuilt combination stays in lineage.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Under queue.land: merge the slot commit never becomes main, so R1's brief is wrong and R4 fires on every merged slot

R1/R4 scoped to queue.land: push; under land: merge the brief names origin/<default> as today and no carry check applies.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: Under method rebase, merging the slot commit does not stop the second conflict R1 promises to avoid

R1/R4 scoped to methods merge and squash; under rebase the brief names origin/<default>.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: R1 names slot-(k-1), but the ejected entry re-enters behind the entries that were behind it

R1 and R2 name one target, the stack target computed after the ejection (last standing combination, else base).

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: R4's reset to the last hand-back head can discard work, and does not remove a stale commit carried from an earlier hand-back

R4 resets to the newest hand-back head that reaches no stale combination and re-applies later non-merge commits by cherry-pick; none free → held with a Need.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: The stale-carry check reads only the current record's queue_built shas, so a requeued or deferred batch carries an ejected change out undetected

carries reads every queue_built sha of this scope's records for the repo (R4, §A).

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: The carry ancestry read is quadratic per pass and does not say what happens when git cannot read it

One `git rev-list <head> ^<target>` per entry, intersected with the built set, cached per (head, target); unreadable holds the entry (R5).

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: The brief's `git fetch origin <onto_ref>` cannot fetch the sha once the slot was rebuilt

R1's brief: fetch the ref; if it no longer contains the sha, stop and wait for the re-issued brief.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: R9 tells the second batch the queue builds it after the first, but queue order is readiness order, not dispatch order

R10 now says whichever of the two lands second gets the hand-back.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: A preapproved batch PR (or an R32 entry's PR) becomes a second, operator-kind entry

R11 refuses R32 entry PRs; added() excludes PRs that are already entries; a batch PR's preapproval records only the preapproval, the driver adds the label and the batch's own settle records the ApprovalEvent; remove withdraws it.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: Preapproval re-approves every future head and trusts a self-reported login; the spec should bound it

R13 bounded and stated: the adder must be an allowed author at use time, each auto-approval comments head and patch-id on the PR, and the widening is stated with queue remove as its end.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: R15 on a between-waves queue lets one unready added PR block the next wave and every release

R15 applies to wave queues only; a between-waves queue drains by its existing rule; the stall counts from the later of the add and the last landing.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r13 -->
### s-r13-resolved · finding [fixed] · resolves s-r13: Schema 14: `_EVENT_SCHEMAS` never sees a top-level `queue_requests`, and the writer stamps unconditionally

§D: JUDGEMENTS_SCHEMA moves to 14, read literal 1–14, explicit refusals for queue_requests and conflict onto/reissue below 14, AGENTS.md line updated.

<!-- fr:journal kind=finding scope=spec id=s-r14-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r14 -->
### s-r14-resolved · finding [fixed] · resolves s-r14: batch_drive.py has 4 lines of budget; the design needs more than the one step-3 loop there

§E: conflict_decision/handbacks_since/red_decision move to fr.triage.handback_rules and _housekeeping_reads to fr.triage.operator_entries; no budget raised.

<!-- fr:journal kind=finding scope=spec id=s-r15-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r15 -->
### s-r15-resolved · finding [fixed] · resolves s-r15: `queue add|remove` does not say how it resolves the scope and its state, or how it coexists with a running driver

R11: the verbs take the scope options and write through _load_state/_write and the state sync; a refused write exits 2 and says to re-run.

<!-- fr:journal kind=finding scope=spec id=s-r16-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r16 -->
### s-r16-resolved · finding [fixed] · resolves s-r16: The Test Plan has one live line and no case for the five CI-proven rows

§F lists the CI cases per requirement and the Verification rows cite them; the Test Plan keeps only the post-merge row, as fr-goal prescribes.

<!-- fr:journal kind=finding scope=spec id=s-r17-resolved created=2026-11-24T22:50:30+00:00 state=fixed resolves=s-r17 -->
### s-r17-resolved · finding [fixed] · resolves s-r17: Small citation errors: MergeConflictError's home and `_conflict`'s line

Background cites batch_merge.py:42 for MergeConflictError, queue_exec.py:152 for its builder, and triage_batch_cmd.py:6315 for _conflict.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-24T22:50:32+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  wave-queue-gaps-live: tester
  wave-queue-handback-carry: none
  wave-queue-handback-slot: none
  wave-queue-operator-entry: none
  wave-queue-operator-preapproval: none
  wave-queue-overlap-report: none
row_kinds:
  wave-queue-gaps-live: live
  wave-queue-handback-carry: none
  wave-queue-handback-slot: none
  wave-queue-operator-entry: none
  wave-queue-operator-preapproval: none
  wave-queue-overlap-report: none
run_gate: none
run_kind: candidate
```
