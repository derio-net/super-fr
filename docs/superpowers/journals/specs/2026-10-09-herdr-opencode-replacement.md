# Journal: 2026-10-09-herdr-opencode-replacement

<!-- fr:journal kind=discovery scope=spec id=operator-brief-1089 created=2026-10-09T20:26:36+00:00 input=true -->
### operator-brief-1089 · discovery · Support OpenCode sessions in the herdr runner and live batch migration

User request: Use the `fr-goal` skill to handle this request. #1089

Issue #1089: Support OpenCode sessions in the herdr runner and live batch migration

## Problem

`fr-herdr` cannot launch or relaunch an OpenCode-backed batch. In fr 5.17.1, `fr_herdr.runner.HARNESSES` contains only `claude`, while herdr itself recognizes OpenCode agents. A dispatched batch also cannot change `launch.harness` or `launch.model`: `fr triage batch edit` correctly freezes those fields after `proposed`, but there is no replacement/migration verb for an intentional harness change.

This blocks moving an active triage sweep from Claude to OpenCode without leaving the durable batch metadata stale.

## Live evidence

A delivered draft batch was replaced in place successfully:

- exited the idle Claude process in its existing herdr pane
- started OpenCode with `openai/gpt-5.6-sol` in the same fr-isolation worktree
- restored the existing fr-derived herdr agent name
- prompted the replacement with the batch status and HOLD contract
- refreshed `fr triage board`; fr still observed the session

The live session works because runner messaging addresses the preserved agent name. The batch still records `harness: claude` and `model: opus`, so a later fresh launch/relaunch can revert or fail.

## Expected support

1. Register OpenCode in `fr-herdr` with its model argument.
2. Cover dispatch, status, messaging, focus, conflict hand-back, close-out, and restart paths with an OpenCode batch.
3. Add an explicit, audited way to replace the launch harness/model of an already-dispatched, unmerged batch without fabricating a second dispatch.
4. Preserve the existing batch branch, isolation workspace, herdr tab, and fr-derived agent name during an in-place replacement.
5. Make partial replacement fail visibly and leave a recoverable shell/session.

## Test plan

- Dispatch a herdr batch with `harness: opencode` and an explicit model; assert the process arguments and ready agent identity.
- Replace an idle Claude batch with OpenCode; assert durable launch metadata, same handle/name, and successful runner messaging.
- Exercise conflict hand-back and close-out after replacement.
- Refuse replacement while the source agent is working or blocked.
- Assert a failed target startup does not lose the source session or batch handle.

Follow-up comment (2026-10-09):
Follow-up from the live runner migration audit: an OpenCode/Herdr control session must be launched from the stable base checkout, never from the disposable fr worktree. The session should then reach branch state through `fr isolation up/status/exec`. Launching or resuming the harness in the worktree couples the terminal process and persisted session metadata to a directory that `fr isolation down` legitimately removes, leaving a dead CWD and making later close-out appear hung. Safe replacement is: stop the old harness, return the pane shell to the repo base checkout, start a fresh harness session there, and reconstruct context from the durable fr cursor/record rather than resuming the old harness session. The active sweep was restarted from the base checkout and can still execute against `feat/batch-sweep-status-lanes` through `fr isolation exec`.

<!-- fr:journal kind=decision scope=spec id=replace-scope created=2026-10-09T20:26:36+00:00 -->
### replace-scope · decision · Bidirectional explicit replacement

Operator chose both directions and model-only replacement; preview first, --yes and an audited reason.

<!-- fr:journal kind=decision scope=spec id=restart-scope created=2026-10-09T20:26:36+00:00 -->
### restart-scope · decision · Fresh fr-owned OpenCode sessions

Operator chose fresh base-checkout reconstruction for fr-owned OpenCode batch/conflict/close-out sessions; unrelated OpenCode stays untouched and existing Claude resume behavior remains.

<!-- fr:journal kind=decision scope=spec id=replacement-failure created=2026-10-09T20:26:36+00:00 -->
### replacement-failure · decision · Recoverable shell on failure

Operator chose preservation and explicit recovery, without automatic source restart; effective launch settings move only after successful target startup.

<!-- fr:journal kind=decision scope=spec id=verification-strategy created=2026-10-09T20:26:36+00:00 -->
### verification-strategy · decision · Candidate plus client-live verification

Operator chose candidate scenarios/CI plus an operator pre-merge herdr walk using the PR build before Ready.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-09T20:31:33+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Compare-before-write is not an exclusive transaction claim

Spec lines 66-82 and batch.py:446-466: competing callers can mutate the same pane; require exclusive locking.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-09T20:31:33+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Repair lacks confirmed reconstruction uptake

Spec lines 71-80 and 106-115: kind/model alone cannot prove a fresh target received its context.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-09T20:31:33+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Descriptor and batch writes need coordinated recovery

Spec lines 75-82 and 102-126: restart must skip unresolved replacement and repair both stores.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-09T20:31:33+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Replacement needs draft and background-work checks

restart.py:257-262 and captured fixture README:48-50: idle/done alone does not prove safe exit input.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-10-09T20:31:33+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · Delivered HOLD can lose original-batch conflict hand-back

triage_batch_cmd.py:3695-3714: conflict messages may target the original batch agent without changing its role.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-09T20:31:33+00:00 -->
### spec-review · review · Independent spec review: five findings

Reviewer checked all four operator decisions and named runner, protocol, lifecycle, schema, isolation, pickup, and verification helpers against actual code. Five in-scope transaction/recovery defects identified; no operator-decision contradiction. Candidate versus client-live evidence remains correctly distinguished. File:line evidence accompanies each finding.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-09T20:31:33+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Compare-before-write is not an exclusive transaction claim

Specified scope then server/pane exclusive OS locks, ownership and contention/crash tests; restart shares pane lock.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-09T20:31:33+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Repair lacks confirmed reconstruction uptake

Specified durable submission checkpoints; repair requires persisted confirmed uptake and refuses uncertain submission without blind replay.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-09T20:31:33+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Descriptor and batch writes need coordinated recovery

Specified cross-store authority/write order, repair of both stores and unresolved-descriptor restart exclusion.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-09T20:31:33+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Replacement needs draft and background-work checks

Replacement now requires and rechecks the same prompt/draft/background/dialog checks as restart for both harnesses.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-10-09T20:31:33+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: Delivered HOLD can lose original-batch conflict hand-back

Original-batch conflict message updates reconstruction metadata; outstanding current hand-back precedes HOLD and obsolete work is not replayed.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-09-herdr-opencode-replacement-p1 created=2026-10-09T20:33:28+00:00 -->
### tier-2026-10-09-herdr-opencode-replacement-p1 · decision · tier: process lifecycle and crash-safe managed restart require hard

Phase 1 changes a live-process eligibility gate and durable descriptor recovery; hard tier is justified by the safety and concurrency paths.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-09-herdr-opencode-replacement-p2 created=2026-10-09T20:33:32+00:00 -->
### phase-split-2026-10-09-herdr-opencode-replacement-p2 · decision · ask: audited batch replacement is independently reviewable

Phase 2 serves R4-R9 and R12: a new replacement command and batch transaction, separate from phase 1's OpenCode lifecycle. Hard tier because pane locks, uncertain submission and cross-store repair form a concurrency gate.
