# Journal: 2026-10-04-drive-merge-train

<!-- fr:journal kind=discovery scope=spec id=merge-train-brief created=2026-10-04T07:29:36+00:00 input=true -->
### merge-train-brief · discovery · Operator brief (batch drive-merge-train, super-fr#942)

Drive merges ready PRs as a merge train: only the head is updated

Batch `drive-merge-train` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#942: Drive: merge ready PRs as a merge train (only the head is updated)
Follow-up to #927, decided by the operator on 2026-10-04: the driver merges ready PRs as a **merge train**.

#927's fix stops release commits and archive merges from forcing updates. Each real merge still moves `main`, and today the driver then updates **every** ready PR that is behind, each re-running CI at once. In the bugfix wave, PRs were updated up to eight times without merging; one was merged by hand to get it through.

**Merge train.** In each pass:
- Take the ready, non-draft batch PRs in merge order (wave, then `order`, then id, as `drive_pass` already sorts).
- Only the **head** of the train is acted on: merged if it is green and up to date (or behind only by release commits and archive merges, per #927), updated if it is behind, waited on if CI is pending.
- PRs behind it are not updated until they become the head; a PR whose CI fails is reported (once per head sha, as today) and stepped over, so it does not block the train.
- Each merge then costs one CI cycle for the next PR, not one for every ready PR.

The plan print and summary should show the train: the head, and the queue behind it.

## Why these belong together
Operator decision (#942): a merge train. Same merge step as drive-release-behind (#927), so it builds on it.

## Delivery rules
- Work on branch `feat/batch-drive-merge-train`.
- Open a draft PR as soon as the spec is committed. Its body contains: Closes derio-net/super-fr#942
- Do not name any member issue as a phase `tracking_issue` in the plan.

<!-- fr:journal kind=decision scope=spec id=train-advances-same-pass created=2026-10-04T07:29:36+00:00 -->
### train-advances-same-pass · decision · After the head merges, the next PR becomes the head in the same pass (R3)

Operator, round 1 Q1 — "1" (advance same pass). The train stops at the first head that did not merge.

<!-- fr:journal kind=decision scope=spec id=train-refusal-steps-over created=2026-10-04T07:29:36+00:00 -->
### train-refusal-steps-over · decision · A refused head is stepped over like failing CI (R4)

Operator, round 1 Q2 — step over it; reported once, the next PR becomes the head.

<!-- fr:journal kind=decision scope=spec id=train-rejoin-merge-order created=2026-10-04T07:29:36+00:00 -->
### train-rejoin-merge-order · decision · A fixed stepped-over PR rejoins at its merge-order place; no stored train state (R5)

Operator, round 1 Q3 — its merge-order place.

<!-- fr:journal kind=decision scope=spec id=train-output-line created=2026-10-04T07:29:36+00:00 -->
### train-output-line · decision · One train line per repo plus `queued N` in the summary (R6)

Operator, round 1 Q4 — one train line per repo.

<!-- fr:journal kind=decision scope=spec id=train-ignores-closeouts created=2026-10-04T07:29:36+00:00 -->
### train-ignores-closeouts · decision · The train never waits on a close-out; close-out shapes belong to

Operator, round 2 — option 1, noting an issue likely existed already. Found it: #818 (verification kinds,
a pre-merge candidate walk for software repos). The operator's framing was added there as a comment:
the close-out Test Plan came from derio-net/frank (infrastructure, applied to real devices); for a library
it has become integration/smoke tests needing an installed version, which a terminal and repo make easier
to drive/mock than a cluster.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-04T07:29:38+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. The operator's round-1 answer to question 1 asked to talk about the close-out (post-merge Test Plans finding defects already in main); round 2 settled how the merge train relates to it.
