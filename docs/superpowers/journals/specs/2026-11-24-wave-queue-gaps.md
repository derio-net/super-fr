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
