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
