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

<!-- fr:journal kind=finding scope=spec id=spr-order-unstable created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-order-unstable · finding [open] (reviewer: in scope) · merge_order is not stable when a merged PR leaves the queue, so the train head can change between passes and update a second PR

target: spec. batch.py:619-631: merge_order's overlap counts and adjacency search depend on which entries are in the queue (and the queue is already filtered to the selection, triage_batch_cmd.py:1472-1476). When head A merges and B is updated, the next pass recounts without A and may put C ahead of B. C is then updated too, the churn #942 is meant to remove.

<!-- fr:journal kind=finding scope=spec id=spr-stop-member-unplaced created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-stop-member-unplaced · finding [open] (reviewer: in scope) · A non-head member that stops the walk (pending or moved after a green candidate) is in no Train field and is not counted

target: spec. For green A, pending B, green C, B was neither head, candidate, queued nor stepped over.

<!-- fr:journal kind=finding scope=spec id=spr-train-line-fields created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-train-line-fields · finding [open] (reviewer: in scope) · The Train record cannot produce the specified train line, and the line has no slot for the green candidates after the head

target: spec. train_line needed PR numbers that Train did not carry; candidates[1:] had no part in the line; §B's _stopped was a set where the queued outcome names the head.

<!-- fr:journal kind=finding scope=spec id=spr-mergestop-head-moved created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-mergestop-head-moved · finding [open] (reviewer: in scope) · A head-moved or closed MergeStopError from merge_ready is stepped over as a refusal, which contradicts R3 (a moved head stops the train)

target: spec. batch_merge.py:236-249 (_open_head raises MergeStopError for a non-OPEN state and for a moved head).

<!-- fr:journal kind=finding scope=spec id=spr-skill-prose-stale created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-skill-prose-stale · finding [open] (reviewer: in scope) · The fr-triage skill still says each pass merges every green PR; neither the spec nor the plan updates it or its mirrors

target: plan. plugins/super-fr/skills/fr-triage/SKILL.md:96.

<!-- fr:journal kind=finding scope=spec id=spr-snap-helper-repos created=2026-10-04T07:36:19+00:00 state=open review_scope=in -->
### spr-snap-helper-repos · finding [open] (reviewer: in scope) · The two-repo pure test cannot be written with the `_snap` helper as it is

target: plan. tests/unit/test_triage_batch_drive.py:89-96: _snap hard-codes repos= and forwards **kw, so passing repos raises TypeError.

<!-- fr:journal kind=review scope=spec id=spr-review created=2026-10-04T07:36:19+00:00 -->
### spr-review · review · Independent spec+plan review: 6 findings, all in scope, all fixed

Read-only fr-spec-reviewer checked all six spec-journal decisions against the spec and the code it names (file:line verified across batch_drive.py, batch.py, batch_merge.py, triage_batch_cmd.py and the drive tests). It confirmed one agentic phase with a TDD shape and the three CI rows linked. Six findings were raised (4 spec, 2 plan), all in scope, all fixed in the spec and the plan.

<!-- fr:journal kind=finding scope=spec id=spr-order-unstable-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-order-unstable -->
### spr-order-unstable-resolved · finding [fixed] · resolves spr-order-unstable: merge_order is not stable when a merged PR leaves the queue, so the train head can change between passes and update a second PR

The train is now ordered by wave, then `order`, then id (`_dispatch_key`, the order the operator's brief names), which does not change when a member leaves. merge_order is no longer used by the drive's merge step (R1, §A step 1). Plan T1 adds an order-stability test.

<!-- fr:journal kind=finding scope=spec id=spr-stop-member-unplaced-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-stop-member-unplaced -->
### spr-stop-member-unplaced-resolved · finding [fixed] · resolves spr-stop-member-unplaced: A non-head member that stops the walk (pending or moved after a green candidate) is in no Train field and is not counted

§A step 2 now says the member that stops the walk is the head when no candidate came before it, and otherwise the first queued member. The Train docstring and plan case (e) match (queued == (b, c)).

<!-- fr:journal kind=finding scope=spec id=spr-train-line-fields-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-train-line-fields -->
### spr-train-line-fields-resolved · finding [fixed] · resolves spr-train-line-fields: The Train record cannot produce the specified train line, and the line has no slot for the green candidates after the head

Train gains `numbers`. The line gains a `then` part for candidates[1:]. §B's `_stopped` is a dict from repo to the batch that stopped the train.

<!-- fr:journal kind=finding scope=spec id=spr-mergestop-head-moved-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-mergestop-head-moved -->
### spr-mergestop-head-moved-resolved · finding [fixed] · resolves spr-mergestop-head-moved: A head-moved or closed MergeStopError from merge_ready is stepped over as a refusal, which contradicts R3 (a moved head stops the train)

A new `HeadMovedError(MergeStopError)`, raised by _open_head for a moved head, stops the train. A no-longer-OPEN PR is not a member. A conflict, version or forge refusal is stepped over (§B table; plan T3/T4). Existing MergeStopError catches are unchanged (R8).

<!-- fr:journal kind=finding scope=spec id=spr-skill-prose-stale-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-skill-prose-stale -->
### spr-skill-prose-stale-resolved · finding [fixed] · resolves spr-skill-prose-stale: The fr-triage skill still says each pass merges every green PR; neither the spec nor the plan updates it or its mirrors

Added R9 and plan task T6 to edit SKILL.md's driver sentence and regenerate both mirrors. The phase `files` list them, and §D lists them as changed.

<!-- fr:journal kind=finding scope=spec id=spr-snap-helper-repos-resolved created=2026-10-04T07:36:19+00:00 state=fixed resolves=spr-snap-helper-repos -->
### spr-snap-helper-repos-resolved · finding [fixed] · resolves spr-snap-helper-repos: The two-repo pure test cannot be written with the `_snap` helper as it is

Plan T1.S1 first gives `_snap` an optional `repos` override, then writes the two-repo test with it.
