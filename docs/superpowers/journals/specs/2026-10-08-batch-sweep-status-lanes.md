# Journal: 2026-10-08-batch-sweep-status-lanes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-09T04:36:03+00:00 input=true -->
### operator-brief · discovery · Operator brief

Implement derio-net/super-fr#1086 end to end: add Needs you start/review lanes driven by run cursors at the batch PR head; never call conflicting or dirty PRs merge ready; relay conflicts and red CI to the batch session once per head; verify through the candidate strategy; deliver a draft PR and never merge it.

<!-- fr:journal kind=decision scope=spec id=d1-human-lanes created=2026-10-09T04:36:03+00:00 -->
### d1-human-lanes · decision · Two explicit operator-attention lanes

Add Needs you · start for pre-PR gates and idle unfinished runs, and Needs you · review for completed draft delivery, manual phases, exhausted merge stops, and operator close-out work. Conflict and red CI remain agent work while a session can be prompted. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-cursor-source created=2026-10-09T04:36:03+00:00 -->
### d2-cursor-source · decision · Read run state from the PR head

Use the batch PR's changed docs/superpowers/runs/*.yaml files and Checkout.show(head_oid, path); do not inspect the host triage cache or infer questions from session prose. Missing or malformed cursor data fails soft to existing lifecycle behavior. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-session-relay created=2026-10-09T04:36:03+00:00 -->
### d3-session-relay · decision · Relay through the canonical optional runner protocol

Use fr_dispatch.protocols.SessionMessenger with the existing batch WorkItem, once per head OID, and retain the standing batch-branch, push, and never-merge boundaries. Do not add a harness-specific messaging path. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-verification created=2026-10-09T04:36:03+00:00 -->
### d4-verification · decision · Candidate verification

Verify all acceptance rows with a candidate walk and tests/scenarios/triage-batch-status-lanes.sh; there is no post-merge-only test plan. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d5-mechanical-model created=2026-10-09T04:36:03+00:00 -->
### d5-mechanical-model · decision · OpenCode mechanical model binding

Old: unbound. New: openai/gpt-6.1-sol-fast. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=d6-standard-model created=2026-10-09T04:36:03+00:00 -->
### d6-standard-model · decision · OpenCode standard model binding

Old: unbound. New: openai/gpt-6.1-sol. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=d7-hard-model created=2026-10-09T04:36:03+00:00 -->
### d7-hard-model · decision · OpenCode hard model binding

Old: unbound. New: openai/gpt-6.1-sol. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-09T04:36:12+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. The operator supplied replacement OpenCode model choices after the first selection was rejected by the provider; that unannounced follow-up was recorded as round 2.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-09T04:41:05+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Pre-PR cursor signals have no readable source

R2 required pre-PR gates while the original R4 read only a PR head that does not yet exist. Review evidence: d1-human-lanes, d2-cursor-source, R2/R4, Design B.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-09T04:41:05+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · The board has no defined way to obtain each repository checkout

The original command design supplied neither checkout mappings nor fetch behavior, so group/org cursor reads were undefined. Review evidence: triage_kanban_cmd.write_board, DriveCheckoutOpt, _checkout_map, Checkout.show.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-09T04:41:05+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Operator-owned close-out work has no classification rule

R3/R6 promised operator close-out placement without naming an authoritative event or test.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-09T04:41:05+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Acceptance rows omit required status and regression behavior

The original four rows did not cover specific hints, manual phases, exhausted merge stops, hand close-out, or preserved board behavior from R6/R10.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-10-09T04:41:05+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · The delivery boundary from the operator brief is absent

The operator brief requires a draft delivery PR that this run never merges, but the original spec did not state that pipeline boundary.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-09T04:41:05+00:00 -->
### spec-review · review · independent spec review — 5 findings

Reviewed the spec against the operator decisions, issue acceptance, board/driver/checkout code, optional dispatch protocols, import direction, and candidate verification contract. All five findings are in scope.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-09T04:41:05+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Pre-PR cursor signals have no readable source

R4 and Design B now use the immutable PR head when one exists and the freshly fetched remote batch branch before a PR exists, preserving the remote-head decision without requiring an impossible PR.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-09T04:41:05+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: The board has no defined way to obtain each repository checkout

R5 and Design B now specify the repeatable drive-compatible checkout map, repo/group validation, fetch-before-read behavior, propagation through board/watch/write_board, and reuse of the driver's validated map.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-09T04:41:05+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Operator-owned close-out work has no classification rule

R6 and Designs A/B now define an unarchived CloseoutEvent with runner hand as the authoritative review-lane state, terminal once archived, with explicit tests.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-09T04:41:05+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Acceptance rows omit required status and regression behavior

Automated verification now names every missing state and preserved behavior, and a new candidate acceptance row covers the specific hints, manual/merge-stop/hand-closeout states, and regressions.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-10-09T04:41:05+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: The delivery boundary from the operator brief is absent

The front matter and Delivery Boundary now require one draft PR, no ready transition, and no merge by this run.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-08-batch-sweep-status-lanes-p2 created=2026-10-09T04:43:51+00:00 -->
### phase-split-2026-10-08-batch-sweep-status-lanes-p2 · decision · ask: isolate merge automation and session relay

Phase 2 owns R7-R9 as an independently reviewable ask: merge eligibility and runner messaging can regress automation even when the board UI is correct, so they receive their own executor and review after the board/run-signal phase.
